"""Configuration module."""

import configparser
import io
import logging
import os
import sys
from datetime import datetime
from email.utils import parseaddr
from pathlib import Path
from urllib.parse import urlunsplit

from salmagundi import config, strings

from . import const
from .exceptions import ConfigError
from .utils import read_resource, LogHandler

_LOG_FILE_FORMAT = '{:%Y%m%d-%H%M%S}.log'
_SFTP_KEY_TYPES = {
    'RSA': ('key_rsa_file', 'key_rsa_pass'),
    'DSA': ('key_dsa_file', 'key_dsa_pass'),
    'ECDSA': ('key_ecdsa_file', 'key_ecdsa_pass'),
    'ED25519': ('key_ed25519_file', 'key_ed25519_pass')
}
_CONFIG_ERRORS = (FileNotFoundError, configparser.Error, config.Error)

_logger = logging.getLogger(__name__)


def configure(cfg_file, job_id):
    """Configure the application.

    :param cfg_file: path to configuration file
    :type cfg_file: term:`path-like object`
    :param str job_id: the job id
    :returns: application and job configurations
    :rtype: (salmagundi.config.Config, salmagundi.config.Config)
    :raises ConfigError: if there is a problem with the configuration
    """
    mail_config_ok = False
    job_cfg = None
    log_enabled = False
    try:
        if not cfg_file:
            raise ConfigError('A config file is required!')
        cfg_file = Path(cfg_file).expanduser()
        app_config_spec = _load_spec('app_config_spec.ini')
        try:
            app_cfg = config.configure(cfg_file, io.StringIO(app_config_spec),
                                       create_properties=False,
                                       converters=_CONVS)
        except _CONFIG_ERRORS as ex:
            raise ConfigError(f'in app config: {ex}')
        _configure_logging(app_cfg, job_id)
        log_enabled = not app_cfg['logging', 'disabled']
        app_cfg.add('start_time', datetime.now())
        mail_config_ok = _check_mail_config(app_cfg)
        app_cfg.add('mail_config_ok', mail_config_ok)
        _logger.info('Job %r started', job_id)
        _set_default_port(app_cfg, ('mail', 'host'), 'smtp')
        _debug_config('APP CONFIG', app_cfg)
        try:
            job_cfg_file = (app_cfg['global', 'jobs_dir'] /
                            job_id).with_suffix(app_cfg['global',
                                                        'job_cfg_ext'])
            job_cfg = get_job_cfg(job_cfg_file, app_cfg)
        except _CONFIG_ERRORS as ex:
            raise ConfigError(f'in job config: {ex}')
        log_enabled = app_cfg['log_handler'].enabled
        job_cfg.add('job_id', job_id)
        job_cfg.add('job_cfg_file', job_cfg_file)
        if not job_cfg['job', 'name']:
            job_cfg['job', 'name'] = job_id
        _merge_notify_addrs(app_cfg, job_cfg, mail_config_ok)
        _debug_config('JOB CONFIG', job_cfg)
        _host_config('source', app_cfg, job_cfg)
        _host_config('target', app_cfg, job_cfg)
        set_urls(job_cfg)
        return app_cfg, job_cfg
    except Exception as ex:
        if mail_config_ok:
            from . import mail
            if not job_cfg:
                args = dict(jobid=job_id, jobname=job_id)
            else:
                args = {}
            mail.send(app_cfg, job_cfg, args, const.ErrorsEnum.CONFIG, ex)
        if log_enabled:
            app_cfg['log_handler'].activate()
            _logger.critical('Configuration error: %s', ex)
            _logger.info('Job "%s" finished', job_id)
        else:
            print(ex, file=sys.stderr)
        raise


def get_job_cfg(conf, app_cfg=None):
    """Return job configuration object."""
    job_config_spec = _load_spec('job_config_spec.ini')
    job_cfg = config.configure(conf, io.StringIO(job_config_spec),
                               create_properties=False, converters=_CONVS)
    if job_cfg['job', 'collect_data'] is config.NOTFOUND:
        if app_cfg:
            job_cfg['job', 'collect_data'] = app_cfg['global', 'collect_data']
        else:
            job_cfg['job', 'collect_data'] = False
    if (app_cfg and app_cfg['logging', 'disabled'] and
            job_cfg['job', 'log_disabled'] is config.NOTFOUND or
            job_cfg['job', 'log_disabled'] is True):
        app_cfg['log_handler'].disable()
    if job_cfg['job', 'single_instance']:
        if not app_cfg['global', 'locks_dir']:
            raise ConfigError('in job config: single_instance used but no'
                              ' locks_dir in app config')
        app_cfg['global', 'locks_dir'].mkdir(parents=True, exist_ok=True)
    return job_cfg


def _debug_config(title, cfg):
    if _logger.isEnabledFor(logging.DEBUG):
        lines = []
        for sec, opt, _, value, readonly in cfg.debug_info():
            if value and (opt.endswith('_pass') or opt == 'password'):
                value = '*' * len(value)
            row = 'RO' if readonly else 'RW'
            lines.append(f'  {row} ({sec}, {opt}) = {value!r}')
        _logger.debug('%s:\n%s', title, '\n'.join(lines))


def _check_mail_config(app_cfg):
    if any(t[2] is not config.NOTFOUND for t in app_cfg if t[0] == 'mail'):
        if (app_cfg['mail', 'security'] is None or
            not all(t[2] is not config.NOTFOUND
                    for t in app_cfg if t[0] == 'mail' and t[1] != 'security')):
            raise ConfigError('in app config: incomplete or invalid mail'
                              ' server configuration')
        return True
    return False


def _merge_notify_addrs(app_cfg, job_cfg, mail_config_ok):
    for cat in ('success', 'error', 'done'):
        app_cfg['notify', cat] = app_cfg['notify', cat] | job_cfg['notify', cat]
    if (not mail_config_ok and
            (app_cfg['notify', 'success'] or
             app_cfg['notify', 'error'] or
             app_cfg['notify', 'done'])):
        _logger.warning('notification addresses present but'
                        ' mail server not configured')


def _configure_logging(app_cfg, job_id):
    log_dir = app_cfg['logging', 'log_dir']
    if log_dir:
        if app_cfg['logging', 'use_subdirs']:
            log_file = _LOG_FILE_FORMAT.format(datetime.now())
            log_path = (log_dir / job_id / log_file).expanduser()
        else:
            log_file = job_id + '_' + _LOG_FILE_FORMAT.format(datetime.now())
            log_path = (log_dir / log_file).expanduser()
        log_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        log_file = '<STDERR>'
        log_path = None
    logging.getLogger('paramiko').setLevel(logging.WARNING)
    if app_cfg['logging', 'log_level'] == 'DEBUG':
        logging.captureWarnings(True)
    else:
        import warnings
        warnings.simplefilter('ignore')
    log_handler = LogHandler(log_path)
    logging.basicConfig(level=app_cfg['logging', 'log_level'],
                        format=app_cfg['logging', 'msg_format'],
                        handlers=[log_handler])
    app_cfg.add('log_handler', log_handler)
    app_cfg.add('log_file', log_file)


def _load_spec(specfile, host_id=None):
    s = read_resource(specfile)
    return s.replace('*HOST_ID*', host_id) if host_id else s


def get_host_cfg(conf, host_id, app_cfg=None):
    """Return host configuration object."""
    host_spec = _load_spec('host_config_spec.ini', host_id)
    host_cfg = config.configure(conf, io.StringIO(host_spec),
                                create_properties=False, converters=_CONVS)
    _set_default_port(host_cfg, (host_id, 'host'),
                      host_cfg[host_id, 'type'])
    if host_cfg[host_id, 'type'] == 'SFTP':
        _sftp_settings(app_cfg, host_cfg, host_id)
    elif host_cfg[host_id, 'password'] is config.NOTFOUND:
        raise ConfigError(f'in host config {host_id!r}: password required')
    host_cfg.add('host_id', host_id)
    return host_cfg


def set_urls(job_cfg):
    """Set source and target URLs in job configuration."""
    for host_kind in ('source', 'target'):
        host_id = job_cfg[host_kind, 'host_id']
        if host_id:
            host_cfg = job_cfg[f'{host_kind}_host_cfg']
            scheme = host_cfg[host_id, 'type'].lower()
            netloc = '%s:%s' % host_cfg[host_id, 'host']
            path = job_cfg[host_kind, 'path']
        else:
            scheme = 'file'
            netloc = ''
            path = os.path.abspath(job_cfg[host_kind, 'path'])
        job_cfg.add(f'{host_kind}_url',
                    urlunsplit((scheme, netloc, path, '', '')))


def _host_config(host_kind, app_cfg, job_cfg):
    host_id = job_cfg[host_kind, 'host_id']
    if host_id:
        hosts_cfg_file = app_cfg['global', 'hosts_cfg']
        if not hosts_cfg_file:
            raise ConfigError('no hosts configuration file')
        try:
            host_cfg = get_host_cfg(hosts_cfg_file, host_id, app_cfg)
            job_cfg.add(f'{host_kind}_host_cfg', host_cfg)
            _debug_config(f'{host_kind.upper()} HOST CONFIG', host_cfg)
        except _CONFIG_ERRORS as ex:
            raise ConfigError(f'in host config {host_id!r}: {ex}')
    else:
        _logger.debug('NO %s HOST CONFIG', host_kind.upper())


def _sftp_settings(app_cfg, host_cfg, host_id):
    if not host_cfg[host_id, 'known_hosts']:
        if app_cfg and app_cfg['sftp', 'known_hosts']:
            host_cfg[host_id, 'known_hosts'] = app_cfg['sftp', 'known_hosts']
        else:
            raise ConfigError(f'in host config {host_id!r}: no known_hosts')
    key_type = host_cfg[host_id, 'key_type']
    if key_type and not host_cfg[host_id, 'key_file']:
        key_file, key_pass = _SFTP_KEY_TYPES[key_type]
        if app_cfg and app_cfg['sftp', key_file]:
            host_cfg[host_id, 'key_file'] = app_cfg['sftp', key_file]
            host_cfg[host_id, 'key_pass'] = app_cfg['sftp', key_pass]
        else:
            raise ConfigError(f'in host config {host_id!r}: no key_file'
                              ' authentication key')
    if host_cfg[host_id, 'key_pass'] == config.NOTFOUND:
        host_cfg[host_id, 'key_pass'] = None
    if not key_type and host_cfg[host_id, 'password'] is config.NOTFOUND:
        raise ConfigError(f'in host config {host_id!r}: password or'
                          f' for {key_type!r} authentication key required')


def _set_default_port(host_cfg, key_host, hosttype):
    if host_cfg[key_host] and not host_cfg[key_host][1]:
        if hosttype == 'smtp':
            port = const.SMTP_PORT
        elif hosttype == 'sftp':
            port = const.SSH_PORT
        else:
            port = const.FTP_PORT
        host_cfg[key_host] = (host_cfg[key_host][0], port)


def _tempopts(s):
    t = s.split(':')
    opt = t[0].lower()
    if len(t) == 1 and opt == 'dot':
        return (opt,)
    elif len(t) == 2 and opt in ('ext', 'dir'):
        if opt == 'ext' and not t[1].startswith('.'):
            return opt, '.' + t[1]
        return opt, t[1]
    raise ValueError(f'unknown or invalid temp option: {s!r}')


_CONVS = {
    'path': Path,
    'abspath': lambda s: Path(s).resolve(),
    'loglevel': config.convert_loglevel('INFO'),
    'hostport': lambda s: strings.split_host_port(s, 0),
    'secopts': config.convert_choice(('STARTTLS', 'TLS'), converter=str.upper),
    'strtuple': strings.str2tuple,
    'addrs': lambda s: set(parseaddr(x) for x in strings.str2tuple(s) if x),
    'tempopts': _tempopts,
    'typeopts': config.convert_choice(('FTP', 'FTPS', 'SFTP'),
                                      converter=str.upper,
                                      default=ValueError),
    'posfloat': config.convert_predicate(lambda x: x > 0.0, converter=float,
                                         default=0.0),
    'posint': config.convert_predicate(lambda x: x > 0, converter=int,
                                       default=0),
    'keytype': config.convert_choice(_SFTP_KEY_TYPES, converter=str.upper,
                                     default=ValueError),
}
