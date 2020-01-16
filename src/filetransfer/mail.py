"""Mail module."""

import email
import logging
import pprint
import string
import textwrap
from smtplib import SMTP, SMTP_SSL, SMTPException

from salmagundi.strings import format_timedelta

from .const import ErrorsEnum
from .job import JobResult
from .utils import read_resource

_logger = logging.getLogger(__name__)

_mail_default = 'default'
_mail_default_cfg = 'default.mail'
_names = ['datetime_format', 'duration_format', 'err_none', 'err_files',
          'err_config', 'err_connect', 'err_transfer', 'err_other',
          'status_ok', 'status_err', 'subject', 'result', 'message']
_indentables = ['info', 'result', 'filelist']
_msg_strings = {
    ErrorsEnum.NONE: 'err_none',
    ErrorsEnum.FILES: 'err_files',
    ErrorsEnum.CONFIG: 'err_config',
    ErrorsEnum.CONNECT: 'err_connect',
    ErrorsEnum.TRANSFER: 'err_transfer',
    ErrorsEnum.OTHER: 'err_other'
}


class _MailCfg:
    def __init__(self, content):
        names = _names[:]
        it = iter(content.splitlines())
        for line in it:
            line = line.strip()
            if line:
                name, value = line.split(':', 1)
                name = name.strip().lower()
                if name not in _names:
                    raise Exception(f'unknown name in mail config {name!r}')
                names.remove(name)
                if name == 'message':
                    value = '\n'.join(it)
                setattr(self, name, value.replace('\\n', '\n').strip())
        if names:
            raise Exception('incomplete mail config:'
                            f' missing {", ".join(names)}')


def _get_mail_cfg(app_cfg, job_cfg):
    mail_cfg = job_cfg['notify', 'mail_cfg'] or app_cfg['notify', 'mail_cfg']
    if mail_cfg != _mail_default:
        if not app_cfg['global', 'mail_cfgs_dir']:
            _logger.warning('No mail_cfgs_dir in application configuration;'
                            ' using default')
            mail_cfg = _mail_default
        else:
            mail_cfg = app_cfg['global', 'mail_cfgs_dir'] / mail_cfg
            if not mail_cfg.exists():
                _logger.warning('Mail configuration %s not found;'
                                ' using default', mail_cfg)
                mail_cfg = _mail_default
    if mail_cfg == _mail_default:
        content = read_resource(_mail_default_cfg)
    else:
        content = mail_cfg.read_text()
    _logger.info('Using mail configuration: %s', mail_cfg)
    try:
        return _MailCfg(content)
    except Exception as ex:
        _logger.error('Error "%s"; using default', ex)
        return _MailCfg(read_resource(_mail_default_cfg))


def _get_addrs(app_cfg, err):
    status = 'success' if err is ErrorsEnum.NONE else 'error'
    addrs = app_cfg['notify', status] | app_cfg['notify', 'done']
    if not addrs:
        _logger.warning('No email addresses for status %r', status)
        return
    return ', '.join(map(lambda a: '%s <%s>' % (a) if a[0] else a[1], addrs))


def _format_file_list(file_list, duration_format):
    lst = []
    for entry in file_list:
        try:
            s = format_timedelta(duration_format, entry[1])
        except TypeError:
            s = entry[1]
        lst.append(f'{entry[2]} {entry[0]} ({s})')
    return lst


def _indents(message, mapping):
    for line in message.splitlines():
        for s in _indentables:
            if line.lstrip().startswith('$' + s):
                prefix = ' ' * line.find('$')
                value = textwrap.indent(mapping[s], prefix)
                mapping[s] = value.lstrip(' ')


def _create_mapping(app_cfg, job_cfg, mail_cfg, endtime, err, result):
    mapping = {
        'jobid': job_cfg[None, 'job_id'],
        'jobname': job_cfg['job', 'name'],
        'starttime': app_cfg['start_time'].strftime(mail_cfg.datetime_format),
        'endtime': endtime.strftime(mail_cfg.datetime_format),
        'duration': format_timedelta(mail_cfg.duration_format,
                                     endtime - app_cfg['start_time']),
        'info': job_cfg['job', 'info'] or '-',
        'logfile': app_cfg['log_file'],
        'errstr': getattr(mail_cfg, _msg_strings[err]),
        'source': job_cfg['source_url'],
        'target': job_cfg['target_url'],
        'status': (mail_cfg.status_ok if err is ErrorsEnum.NONE
                   else mail_cfg.status_err),
    }
    file_list = '-'
    if isinstance(result, JobResult):
        res = _substitute(mail_cfg.result, result._asdict())
        if result.file_list:
            file_list = '\n'.join(_format_file_list(result.file_list,
                                                    mail_cfg.duration_format))
    else:
        res = str(result)
        if not res:
            res = result.__class__.__name__
    mapping['result'] = res
    mapping['filelist'] = file_list
    _indents(mail_cfg.message, mapping)
    return mapping


def _substitute(templ, mapping):
    return string.Template(templ).safe_substitute(mapping)


def send(app_cfg, job_cfg, endtime, err, result):
    """Send email.

    :param app_cfg: application configuration
    :type app_cfg: salmagundi.config.Config
    :param job_cfg: job configuration
    :type job_cfg: salmagundi.config.Config
    :param datetime.datetime endtime: end time of job
    :param err: error string
    :type err: filetransfer.const.ErrorsEnum
    :param result: job result
    :type result: :class:`filetransfer.job.JobResult` or :class:`Exception`
    """
    to_addrs = _get_addrs(app_cfg, err)
    if not to_addrs:
        return
    mail_cfg = _get_mail_cfg(app_cfg, job_cfg)
    mapping = _create_mapping(app_cfg, job_cfg, mail_cfg, endtime, err, result)
    if _logger.isEnabledFor(logging.DEBUG):
        _logger.debug('mail template mapping:\n%s', pprint.pformat(mapping))
    emailmsg = email.message.EmailMessage()
    emailmsg['From'] = app_cfg['mail', 'from_addr']
    emailmsg['To'] = to_addrs
    emailmsg['Subject'] = _substitute(mail_cfg.subject, mapping)
    emailmsg.set_content(_substitute(mail_cfg.message, mapping))
    host, port = app_cfg['mail', 'host']
    _logger.debug('mail host: %s:%d', host, port)
    _logger.debug('mail security: %s', app_cfg['mail', 'security'])
    smtp_cls = SMTP_SSL if app_cfg['mail', 'security'] == 'TLS' else SMTP
    if host == 'TEST':
        print(f'=====\nCLASS: {smtp_cls.__name__}\n')
        print(f'{emailmsg}\n=====')
    else:
        try:
            with smtp_cls(host, port) as smtp:
                if app_cfg['mail', 'security'] == 'STARTTLS':
                    smtp.starttls()
                smtp.login(app_cfg['mail', 'user'], app_cfg['mail', 'password'])
                smtp.send_message(emailmsg)
            _logger.info('Notification sent')
            if _logger.isEnabledFor(logging.DEBUG):
                _logger.debug('%s:%d\n%s', host, port,
                              textwrap.indent(str(emailmsg), ' >'))
        except (OSError, SMTPException):
            msg = textwrap.indent(str(emailmsg), ' >')
            _logger.exception(f'Notification not sent:\n{msg}')


if __name__ == '__main__':
    # check and print mail configs
    import sys
    if len(sys.argv) == 1:
        sys.exit(f'usage: python {__package__}.mail -m <filename>')
    try:
        file = sys.argv[1]
        if file == _mail_default:
            mail_cfg = _MailCfg(read_resource(_mail_default_cfg))
        else:
            with open(file) as fh:
                mail_cfg = _MailCfg(fh.read())
        for name in _names:
            print(f'{name.upper()}: {getattr(mail_cfg, name)}')
        print(f'===\nfile {file} OK', file=sys.stderr)
    except Exception as ex:
        sys.exit(ex)
