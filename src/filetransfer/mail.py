"""Mail module."""

import logging
import textwrap
from smtplib import SMTP, SMTP_SSL, SMTPException

from . import config, utils
from .const import SMTP_PORT
from .exceptions import ConfigError

_logger = logging.getLogger(__name__)


def _get_addrs(cfg, key):
    addrs = set(utils.str_to_tuple(config.mail_cfg['done'], ','))
    addrs.update(utils.str_to_tuple(config.mail_cfg[key], ','))
    if 'notify' in cfg:
        addrs.update(utils.str_to_tuple(cfg['notify'].get('done', ''), ','))
        addrs.update(utils.str_to_tuple(cfg['notify'].get(key, ''), ','))
    return ', '.join(addrs)


def send(job_cfg, args, err):
    """Send email.

    :param job_cfg: job configuration
    :type job_cfg: configparser.ConfigParser
    :param dict args: arguments for email template
    :param str err: error string
    """
    user = config.mail_cfg['user']
    passwd = config.mail_cfg['password']
    from_addr = config.mail_cfg['from_addr']
    addrs = _get_addrs(job_cfg, 'error' if err else 'success')
    args['fromaddr'] = from_addr
    args['logfile'] = config.log_file
    args['error'] = err or 'No errors'
    args['status'] = 'ERROR' if err else 'OK'
    args['toaddrs'] = addrs
    text = template.format(**args).encode(errors='replace')
    host, port = utils.split_host_port(config.mail_cfg['host'], SMTP_PORT)
    _logger.debug('mail host: %s:%d', host, port)
    security = config.mail_cfg.get('security', '').upper()
    if security and security not in ('STARTTLS', 'TLS'):
        raise ConfigError('security must be "STARTTLS" or "TLS"')
    _logger.debug('mail security: %s', security)
    smtp_cls = SMTP_SSL if security == 'TLS' else SMTP
    if config.mail_cfg.getboolean('test', False):
        print('\nMAIL: %s:%d\n' % (host, port))
        print(text.decode())
    else:
        try:
            with smtp_cls(host, port) as smtp:
                if security == 'STARTTLS':
                    smtp.starttls()
                smtp.login(user, passwd)
                smtp.sendmail(from_addr, addrs, text)
            _logger.info('Notification sent')
            if _logger.isEnabledFor(logging.DEBUG):
                _logger.debug('%s:%d\n%s', host, port,
                              textwrap.indent(text.decode(), ' >'))
        except (OSError, SMTPException):
            _logger.exception('Notification not sent:\n%s' %
                              textwrap.indent(text.decode(), ' >'))


template = '''From: {fromaddr}
To: {toaddrs}
Subject: Job "{jobname}" finished [{status}]
Content-Type: text/plain; Charset = UTF-8

Job "{jobname}" (ID: {jobid}):

From: {starttime:%x %X}
Until: {endtime:%x %X}
Duration: {duration}

Logfile: {logfile}

{error}
{msg}
'''
