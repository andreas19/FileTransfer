"""Job module."""

import logging
import pprint
import textwrap
import traceback
from datetime import datetime

from . import config, mail
from .exceptions import ConfigError, ConnectError
from .local import LocalSource, LocalTarget
from .ftp import FTPSource, FTPTarget
from .sftp import SFTPSource, SFTPTarget

_logger = logging.getLogger(__name__)


def run(cfg, job_id):
    """Run a job.

    :param cfg: a job configuration
    :type cfg: configparser.ConfigParser
    :raises filetransfer.exceptions.ConfigError: if there is a problem with
                                                 the configuration
    :raises filetransfer.exceptions.ConnectError: if there is a connection
                                                  problem
    :raises Exception: if another error occurs
    """
    start_time = datetime.now()
    job_name = _get_job_name(cfg, job_id)
    try:
        config.host_configuration(cfg, 'source')
        config.host_configuration(cfg, 'target')
        files_cnt, src_error_cnt, tgt_error_cnt = transfer(cfg)
        if src_error_cnt or tgt_error_cnt:
            err = 'Transfer error(s)'
            msg = ('%d files transferred, %d source error(s), '
                   '%d target error(s)' %
                   (files_cnt, src_error_cnt, tgt_error_cnt))
            _logger.error('Transfer completed: %s', msg)
            msg += ' (see log)'
        else:
            err = None
            msg = '%d files transferred' % files_cnt
            _logger.info('Transfer completed: %s', msg)
    except ConfigError as ex:
        _logger.critical('Configuration error: %s', ex)
        err = 'Configuration error'
        msg = str(ex)
        raise ex
    except ConnectError as ex:
        _logger.critical('Connect error: %s', ex)
        err = 'Connect error'
        msg = str(ex)
        raise ex
    except Exception as ex:
        _logger.critical('Unexpected error\n%s', traceback.format_exc().strip())
        err = 'Unexpected error'
        msg = str(ex)
        raise ex
    finally:
        end_time = datetime.now()
        duration = end_time - start_time
        if config.mail_cfg:
            args = {
                'jobid': job_id,
                'jobname': job_name,
                'starttime': start_time,
                'endtime': end_time,
                'duration': duration,
                'msg': textwrap.indent(msg, '  ') if msg else ''
            }
            if _logger.isEnabledFor(logging.DEBUG):
                _logger.debug('mail args:\n%s', pprint.pformat(args))
            mail.send(cfg, args, err)
        _logger.info('Job "%s" finished: duration=%s', job_id, duration)


def _create_source(cfg):
    try:
        cfg = cfg['source']
        src_type = cfg['type'].upper()
        if src_type == 'LOCAL':
            return LocalSource(cfg)
        elif src_type == 'FTP':
            return FTPSource(cfg)
        elif src_type == 'FTPS':
            return FTPSource(cfg, True)
        elif src_type == 'SFTP':
            return SFTPSource(cfg)
        else:
            raise ConfigError('Unknown source type "%s"' % src_type)
    except KeyError as ex:
        raise ConfigError('"%s" is required' % ex.args[0])


def _create_target(cfg):
    try:
        cfg = cfg['target']
        tgt_type = cfg['type'].upper()
        if tgt_type == 'LOCAL':
            return LocalTarget(cfg)
        elif tgt_type == 'FTP':
            return FTPTarget(cfg)
        elif tgt_type == 'FTPS':
            return FTPTarget(cfg, True)
        elif tgt_type == 'SFTP':
            return SFTPTarget(cfg)
        else:
            raise ConfigError('Unknown target type "%s"' % tgt_type)
    except KeyError as ex:
        raise ConfigError('"%s" is required' % ex.args[0])


def transfer(cfg):
    """Transfer files.

    :param cfg: a job configuration
    :type cfg: configparser.ConfigParser
    :return: files count, source error count, target error count
    :rtype: (int, int, int)
    :raises filetransfer.ConfigError: if there is a problem with
                                      the configuration
    :raises filetransfer.ConnectError: if there is a connection problem
    :raises Exception: if another error occurs
    """
    with _create_source(cfg) as source, _create_target(cfg) as target:
        files_cnt = 0
        for file_path, reader in source.files():
            try:
                if target.store(file_path, reader):
                    files_cnt += 1
                    _logger.info('Transferred - file: %s', file_path)
            finally:
                reader.close()
    return files_cnt, source.error_cnt, target.error_cnt


def _get_job_name(cfg, job_id):
    if 'notify' in cfg:
        job_name = cfg['notify'].get('name')
        if job_name:
            _logger.info('Job name: %s', job_name)
        else:
            job_name = job_id
    else:
        job_name = job_id
    return job_name
