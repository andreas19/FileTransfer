"""Job module."""

import logging
import traceback
from collections import namedtuple
from datetime import datetime

from .const import ErrorsEnum
from .exceptions import ConnectError, TransferError, Terminated
from .local import LocalSource, LocalTarget
from .ftp import FTPSource, FTPTarget
from .sftp import SFTPSource, SFTPTarget

_logger = logging.getLogger(__name__)

JobResult = namedtuple('JobResult', 'files_cnt, src_error_cnt, '
                       'tgt_error_cnt file_list')
JobResult.__doc__ = """Class that contains job results.

This class has the following fields:

=================  ===
**files_cnt**      number of successfully transferred files
**src_error_cnt**  number of files that could not be read
**tgt_error_cnt**  number of files that could not be written
**file_list**      list of tuples: (path, info, tag)
                    - path: path relative to source/target directory
                    - info: duration of transfer or error text
                    - tag: > (source), < (target), = (transffered)

                   if data collection is disabled this will be ``None``
=================  ===
"""


def run(app_cfg, job_cfg, exc=None):
    """Run a job.

    :param app_cfg: the application configuration
    :type app_cfg: salmagundi.config.Config
    :param job_cfg: the job configuration
    :type job_cfg: salmagundi.config.Config
    :param Exception exc: Exception to be reraised
    :raises filetransfer.exceptions.ConnectError: if there is a connection
                                                  problem
    :raises filetransfer.TransferError: if there is a fatal problem
                                        during transfer
    :raises filetransfer.Terminated: if terminatated
    :raises Exception: if another error occurs
    """
    try:
        if exc and isinstance(exc, BaseException):
            raise exc
        result = transfer(job_cfg)
        _logger.info('Transfer completed: %d files transferred, %d source '
                     'errors, %d target errors' % result[:3])
        if result.src_error_cnt or result.tgt_error_cnt:
            err = ErrorsEnum.FILES
        else:
            err = ErrorsEnum.NONE
    except ConnectError as ex:
        _logger.critical('Connect error: %s', ex)
        err = ErrorsEnum.CONNECT
        result = ex
        raise ex
    except TransferError as ex:
        _logger.critical('Transfer error: %s', ex)
        err = ErrorsEnum.TRANSFER
        result = ex
        raise ex
    except (KeyboardInterrupt, Terminated) as ex:
        _logger.critical('Terminated')
        err = ErrorsEnum.OTHER
        result = ex
        raise Terminated
    except Exception as ex:
        _logger.critical('Another error\n%s', traceback.format_exc().strip())
        err = ErrorsEnum.OTHER
        result = ex
        raise ex
    finally:
        end_time = datetime.now()
        if app_cfg['mail_config_ok']:
            args = dict(endtime=end_time)
            from . import mail
            mail.send(app_cfg, job_cfg, args, err, result)
        _logger.info('Job "%s" finished: duration=%s',
                     job_cfg['job_id'], end_time - app_cfg['start_time'])


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


def transfer(job_cfg):
    """Transfer files.

    :param job_cfg: the job configuration
    :type job_cfg: salmagundi.config.Config
    :return: job result
    :rtype: JobResult
    :raises filetransfer.ConnectError: if there is a connection problem
    :raises filetransfer.TransferError: if there is a fatal problem
                                        during transfer
    :raises Exception: if another error occurs
    """
    transferred_files = [] if job_cfg['job', 'collect_data'] else None
    with _create_source(job_cfg) as source, _create_target(job_cfg) as target:
        files_cnt = 0
        try:
            for file_path, reader in source.files():
                try:
                    start_time = datetime.now()
                    if target.store(file_path, reader):
                        files_cnt += 1
                        duration = datetime.now() - start_time
                        if transferred_files is not None:
                            transferred_files.append((file_path, duration))
                        _logger.info('Transferred - file: %s (%s)',
                                     file_path, duration)
                finally:
                    reader.close()
        except Exception as ex:
            raise TransferError(ex)
    if job_cfg['job', 'collect_data']:
        file_lst = []
        for lst, tag in zip((transferred_files, source.error_files,
                             target.error_files), ('=', '>', '<')):
            for path, info in lst:
                file_lst.append((path, info, tag))
        file_lst.sort()
    else:
        file_lst = None
    return JobResult(files_cnt, source.error_cnt, target.error_cnt, file_lst)
