"""Job module."""

import logging
import os
import time
from contextlib import nullcontext, suppress
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from salmagundi.utils import ensure_single_instance, AlreadyRunning

from .const import ExitCodes, FileTags
from .exceptions import (ConnectError, TransferError, SingleInstanceError,
                         NotReadyError, Terminated, Error)
from .local import LocalSource, LocalTarget
from .ftp import FTPSource, FTPTarget
from .sftp import SFTPSource, SFTPTarget

_RETRY_MAX_INTERVAL = 60.0  # seconds
_RETRY_BACKOFF_FACTOR = 1.0
_RETRY_BACKOFF_BASE = 2.0

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class JobResult:
    """JobResult class; documented in api.rst."""

    files_cnt: int
    src_error_cnt: int
    tgt_error_cnt: int
    file_list: list = field(repr=False)

    def __str__(self):
        return (f'{self.files_cnt} file(s) transferred, '
                f'{self.src_error_cnt} source error(s), '
                f'{self.tgt_error_cnt} target error(s)')


def run(app_cfg, job_cfg, exc=None):
    """Run a job.

    :param app_cfg: the application configuration
    :type app_cfg: salmagundi.config.Config
    :param job_cfg: the job configuration
    :type job_cfg: salmagundi.config.Config
    :param Exception exc: Exception to be reraised
    :returns: job result and exit code (0: success, 1: with errors)
    :rtype: JobResult, bool
    :raises filetransfer.ConnectError: if there is a connection problem
    :raises filetransfer.TransferError: if there is a fatal problem
                                        during transfer
    :raises filetransfer.SingleInstanceError: if a single instance requirement
                                              is violated
    :raises filetransfer.Terminated: if terminatated
    :raises Exception: if parameter ``exc`` is set
    """
    ready_file = _check_ready_file(job_cfg)
    ctx = _create_context(app_cfg, job_cfg)
    collect_data = job_cfg['job', 'collect_data']
    files, exit_code, result = {}, None, None
    try:
        with ctx:
            app_cfg['log_handler'].activate()
            if exc and isinstance(exc, BaseException):
                raise exc
            for i in range(1 + job_cfg['job', 'retries']):
                try:
                    transfer(job_cfg, files)
                    result = create_result(files, collect_data)
                    _logger.info('Transfer completed: %s', result)
                    if result.src_error_cnt or result.tgt_error_cnt:
                        exit_code = ExitCodes.ERRORS
                    else:
                        exit_code = ExitCodes.SUCCESS
                        _remove_ready_file(ready_file)
                    return result, exit_code.code
                except Error as ex:
                    if i == job_cfg['job', 'retries']:
                        raise
                    t = min(_RETRY_MAX_INTERVAL,
                            _RETRY_BACKOFF_FACTOR * _RETRY_BACKOFF_BASE ** i)
                    _logger.error('Error: %s; retry in %.1f seconds', ex, t)
                    time.sleep(t)
    except AlreadyRunning as ex:
        raise SingleInstanceError(ex) from None
    except KeyboardInterrupt as ex:
        _log_critical('KeyboardInterrupt', ex)
        exit_code = ExitCodes.TERMINATED
        result = _add_result(Terminated('KeyboardInterrupt'),
                             files, collect_data)
        raise result
    except Terminated as ex:
        _log_critical('Terminated', ex)
        exit_code = ExitCodes.TERMINATED
        result = _add_result(ex, files, collect_data)
        raise result
    except (ConnectError, TransferError) as ex:
        _log_critical(ex.__class__.__name__, ex)
        exit_code = ExitCodes.FAILURE
        result = _add_result(ex, files, collect_data)
        raise result
    except Exception as ex:
        _log_critical('Error', ex)
        result = _add_result(ex, files, collect_data)
        raise result
    finally:
        if result is not None:
            end_time = datetime.now()
            if app_cfg['mail_config_ok']:
                from . import mail
                mail.send(app_cfg, job_cfg, end_time, exit_code, result)
            _logger.info('Job "%s" finished: duration=%s; exit_code=%s',
                         job_cfg['job_id'],
                         end_time - app_cfg['start_time'],
                         exit_code.code if exit_code else None)


def _add_result(ex, files, collect_data):
    ex.result = create_result(files, collect_data)
    return ex


def _log_critical(msg, exc):
    _logger.critical('%s: %s', msg, exc)
    _logger.debug(msg, exc_info=exc)


def _create_source(job_cfg):
    host_id = job_cfg['source', 'host_id']
    if host_id:
        src_type = job_cfg['source_host_cfg'][host_id, 'type']
        if src_type == 'FTP':
            return FTPSource(job_cfg)
        elif src_type == 'FTPS':
            return FTPSource(job_cfg, True)
        elif src_type == 'SFTP':
            return SFTPSource(job_cfg)
    else:
        return LocalSource(job_cfg)


def _create_target(job_cfg):
    host_id = job_cfg['target', 'host_id']
    if host_id:
        tgt_type = job_cfg['target_host_cfg'][host_id, 'type']
        if tgt_type == 'FTP':
            return FTPTarget(job_cfg)
        elif tgt_type == 'FTPS':
            return FTPTarget(job_cfg, True)
        elif tgt_type == 'SFTP':
            return SFTPTarget(job_cfg)
    else:
        return LocalTarget(job_cfg)


def transfer(job_cfg, files):
    """Transfer files.

    ``files``: path -> duration|(True|False, exc) -- True: src, False: tgt

    :param job_cfg: the job configuration
    :type job_cfg: salmagundi.config.Config
    :param dict files: files
    :return: job result
    :rtype: JobResult
    :raises filetransfer.ConnectError: if there is a connection problem
    :raises filetransfer.TransferError: if there is a fatal problem
                                        during transfer
    """
    with _create_source(job_cfg) as src, _create_target(job_cfg) as tgt:
        try:
            for file_path, obj in src.files():
                try:
                    if (isinstance(files.get(file_path), timedelta) or
                            file_path == job_cfg['job', 'ready_file']):
                        continue
                    if isinstance(obj, Exception):
                        files[file_path] = (True, obj)
                        continue
                    start_time = datetime.now()
                    exc = tgt.store(file_path, obj)
                    if exc is None:
                        duration = datetime.now() - start_time
                        files[file_path] = duration
                        _logger.info('Transferred - file: %s (%s)',
                                     file_path, duration)
                    else:
                        files[file_path] = (False, exc)
                finally:
                    with suppress(Exception):
                        obj.close()
        except Exception as ex:
            raise TransferError(ex)


def create_result(files, collect_data):
    """Create job result."""
    transf_cnt, srcerr_cnt, tgterr_cnt = 0, 0, 0
    if collect_data:
        file_lst = []
    else:
        file_lst = None
    for path, value in files.items():
        if isinstance(value, tuple):
            if value[0]:
                srcerr_cnt += 1
                tag = FileTags.SRCERR
            else:
                tgterr_cnt += 1
                tag = FileTags.TGTERR
            info = str(value[1]).split('\n')[0]
        else:
            transf_cnt += 1
            info = value
            tag = FileTags.TRANSF
        if file_lst is not None:
            file_lst.append((path, info, tag))
    if file_lst:
        file_lst.sort()
    return JobResult(transf_cnt, srcerr_cnt, tgterr_cnt, file_lst)


def _check_ready_file(job_cfg):
    if job_cfg['job', 'ready_file']:
        ready_file = os.path.join(job_cfg['source', 'path'],
                                  job_cfg['job', 'ready_file'])
        if not os.path.exists(ready_file):
            raise NotReadyError(f'ready_file {ready_file!r} does not exist')
    else:
        ready_file = None
    return ready_file


def _remove_ready_file(ready_file):
    if ready_file:
        with suppress(OSError):
            os.remove(ready_file)
            _logger.debug('ready_file removed: %s', ready_file)


def _create_context(app_cfg, job_cfg):
    if job_cfg['job', 'single_instance']:
        if job_cfg['job', 'single_instance'] is True:
            name = job_cfg['job_id']
        else:
            name = job_cfg['job', 'single_instance']
        msg = f'already running: job {job_cfg["job_id"]} (lock: {name})'
        ctx = ensure_single_instance(name,
                                     lockdir=app_cfg['global', 'locks_dir'],
                                     err_code=None,
                                     err_msg=msg)
    else:
        ctx = nullcontext()
    return ctx
