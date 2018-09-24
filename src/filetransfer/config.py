"""Configuration module.

The following global variables will be set in this module:

In :func:`configure`:

* ``log_file``
* ``jobs_dir``
* ``sftp_cfg``
* ``mail_cfg``
* ``_hosts_cfg_file``

In :func:`host_configuration`:

* ``_hosts_cfg``
"""

import configparser
import logging
from datetime import datetime
from pathlib import Path

from .exceptions import ConfigError

_logger = logging.getLogger(__name__)
_hosts_cfg = None
_hosts_cfg_keys = ['type', 'host', 'user', 'password', 'timeout',
                   'passive_mode', 'encrypt_data', 'key_file',
                   'key_pass', 'known_hosts']
_log_file_format = '{:%Y%m%d-%H%M%S}.log'


def configure(cfg, job_id):
    """Configure the application.

    :param cfg: application configuration
    :type cfg: configparser.ConfigParser
    :param str job_id: job ID
    :raises ConfigError: if a required key or section is missing
    """
    global log_file, jobs_dir, sftp_cfg, mail_cfg, _hosts_cfg_file
    try:
        log_file = _configure_logging(cfg, job_id)
        _logger.info('Job "%s" started', job_id)
        _logger.debug('log_file=%s', log_file)
        jobs_dir = Path(cfg['global']['jobs_dir']).expanduser()
        _logger.debug('jobs_dir=%s', jobs_dir)
        _hosts_cfg_file = cfg['global'].get('hosts_cfg')
        if _hosts_cfg_file is not None:
            _hosts_cfg_file = Path(_hosts_cfg_file).expanduser()
        _logger.debug('hosts_cfg=%s', _hosts_cfg_file)
        sftp_cfg = cfg['sftp'] if 'sftp' in cfg else {}
        if 'mail' in cfg:
            mail_cfg = cfg['mail']
            if 'notify' in cfg:
                mail_cfg['done'] = cfg['notify'].get('done', '')
                mail_cfg['error'] = cfg['notify'].get('error', '')
                mail_cfg['success'] = cfg['notify'].get('success', '')
        else:
            mail_cfg = None
    except KeyError as ex:
        raise ConfigError('"%s" is required' % ex.args[0])


def host_configuration(cfg, section):
    """Set host configuration.

    The values from a host configuration indentified by ``host_id`` will be
    copied to the ``source`` or ``target`` section of a job configuration.

    :param cfg: job configuration
    :type cfg: configparser.ConfigParser
    :param str section: ``'source'`` or ``'target'``
    :raises ConfigError: if a key is missing, set in the job config or no
                         hosts config file is set in the application config
    """
    global _hosts_cfg
    try:
        cfg = cfg[section]
    except KeyError as ex:
        raise ConfigError('"%s" is required' % ex.args[0])
    if 'host_id' not in cfg:
        return
    if not _hosts_cfg:
        try:
            if _hosts_cfg_file:
                _hosts_cfg = configparser.ConfigParser(interpolation=None)
                with _hosts_cfg_file.open() as fh:
                    _hosts_cfg.read_file(fh)
            else:
                raise ConfigError('Hosts configuration: hosts_cfg not set in'
                                  ' application config')
        except (FileNotFoundError, configparser.Error) as ex:
            raise ConfigError('Hosts configuration: %s' % ex)
    for k in _hosts_cfg_keys:
        if k in cfg:
            raise ConfigError('Host configuration setting(s)'
                              ' in "%s" but host_id used' % section)
    for k, v in _hosts_cfg[cfg['host_id']].items():
        cfg[k] = v


def _configure_logging(cfg, job_id):
    if 'logging' in cfg:
        cfg = cfg['logging']
    else:
        cfg = {}
    log_dir = cfg.get('log_dir')
    if log_dir is None:
        log_file = '<STDERR>'
        log_path = None
    else:
        if cfg.getboolean('use_subdirs', True):
            log_file = _log_file_format.format(datetime.now())
            log_path = Path(log_dir, job_id, log_file).expanduser()
        else:
            log_file = job_id + '_' + _log_file_format.format(datetime.now())
            log_path = Path(log_dir, log_file).expanduser()
        log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.getLogger('paramiko').setLevel(logging.WARNING)
    log_level = cfg.get('log_level') or 'info'
    log_format = (cfg.get('msg_format') or
                  '%(asctime)s %(levelname)-8s %(message)s')
    logging.basicConfig(filename=log_path, level=log_level.upper(),
                        filemode='w', format=log_format)
    return log_file
