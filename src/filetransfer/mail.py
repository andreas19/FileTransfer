"""Mail module."""

import logging
import pprint
import string
import textwrap
from collections import defaultdict
from smtplib import SMTP, SMTP_SSL, SMTPException

from .const import ErrorsEnum
from .job import JobResult

_logger = logging.getLogger(__name__)

_msg_titles = {
    ErrorsEnum.NONE: 'No errors',
    ErrorsEnum.FILES: 'File error(s)',
    ErrorsEnum.CONFIG: 'Configuration error',
    ErrorsEnum.CONNECT: 'Connect error',
    ErrorsEnum.TRANSFER: 'Transfer error',
    ErrorsEnum.OTHER: 'Another error'
}
_completed_msg = '%d files transferred, %d source errors, %d target errors'
_status_strings = ('OK', 'ERROR')


def _get_addrs(app_cfg, err):
    status = 'success' if err is ErrorsEnum.NONE else 'error'
    addrs = app_cfg['notify', status] | app_cfg['notify', 'done']
    if not addrs:
        _logger.warning('No email addresses for status %r' % status)
        return
    return ', '.join(addrs)


def _add_args_from_app_cfg(app_cfg, args, err):
    args['fromaddr'] = app_cfg['mail', 'from_addr']
    args['logfile'] = app_cfg['log_file']
    args['starttime'] = app_cfg['start_time'].strftime('%x %X')
    args['toaddrs'] = _get_addrs(app_cfg, err)


def _add_args_from_job_cfg(job_cfg, args):
    if job_cfg:
        args['jobname'] = job_cfg['job', 'name']
        args['jobid'] = job_cfg['job_id']
        if 'source_url' in job_cfg:
            args['source'] = job_cfg['source_url']
        if 'target_url' in job_cfg:
            args['target'] = job_cfg['target_url']
        if job_cfg['job', 'info']:
            info = job_cfg['job', 'info']
        else:
            info = '-'
        args['info'] = textwrap.indent(info, ' ')


def _add_args_from_result(result, args):
    if isinstance(result, JobResult):
        msg = _completed_msg % result[:3]
        file_list = _create_file_list(result.file_list)
    else:
        msg = str(result)
        if not msg:
            msg = result.__class__.__name__
        file_list = ' -'
    args['message'] += ':\n' + textwrap.indent(textwrap.fill(msg), ' ')
    args['file_list'] = file_list


def _create_file_list(file_list):
    if file_list is None:
        return ' no data collected'
    if not file_list:
        return ' no data'
    lst = []
    for entry in file_list:
        lst.append(' {2} {0} ({1})'.format(*entry))
    return '\n'.join(lst)


def send(app_cfg, job_cfg, args, err, result):
    """Send email.

    :param app_cfg: application configuration
    :type app_cfg: salmagundi.config.Config
    :param job_cfg: job configuration
    :type job_cfg: salmagundi.config.Config
    :param dict args: arguments for email template
    :param str err: error string
    """
    _add_args_from_app_cfg(app_cfg, args, err)
    if not args['toaddrs']:
        return
    _add_args_from_job_cfg(job_cfg, args)
    args['status'] = (_status_strings[0] if err is ErrorsEnum.NONE
                      else _status_strings[1])
    if 'endtime' in args:
        args['duration'] = args['endtime'] - app_cfg['start_time']
        args['endtime'] = args['endtime'].strftime('%x %X')
    args['message'] = _msg_titles[err]
    _add_args_from_result(result, args)
    if _logger.isEnabledFor(logging.DEBUG):
        _logger.debug('mail template args:\n%s', pprint.pformat(args))
    templ = string.Template(template)
    text = templ.substitute(defaultdict(lambda: '-', args))
    host, port = app_cfg['mail', 'host']
    _logger.debug('mail host: %s:%d', host, port)
    _logger.debug('mail security: %s', app_cfg['mail', 'security'])
    smtp_cls = SMTP_SSL if app_cfg['mail', 'security'] == 'TLS' else SMTP
    if host == 'TEST':
        print('=====\nCLASS: %s\n' % smtp_cls.__name__)
        print('%s\n=====' % text)
    else:
        try:
            with smtp_cls(host, port) as smtp:
                if app_cfg['mail', 'security'] == 'STARTTLS':
                    smtp.starttls()
                smtp.login(app_cfg['mail', 'user'], app_cfg['mail', 'password'])
                smtp.sendmail(app_cfg['mail', 'from_addr'], args['toaddrs'],
                              text.encode(errors='replace'))
            _logger.info('Notification sent')
            if _logger.isEnabledFor(logging.DEBUG):
                _logger.debug('%s:%d\n%s', host, port,
                              textwrap.indent(text, ' >'))
        except (OSError, SMTPException):
            _logger.exception('Notification not sent:\n%s' %
                              textwrap.indent(text, ' >'))


template = '''From: ${fromaddr}
To: ${toaddrs}
Subject: Job "${jobname}" finished [${status}]
Content-Type: text/plain; Charset = UTF-8

Job "${jobname}" (ID: ${jobid}):

Start: ${starttime}
End: ${endtime}
Duration: ${duration}

Info:
${info}

Logfile: ${logfile}

${message}

Source: ${source}
Target: ${target}

Files: (= is transferred, > is source error, < is target error)
${file_list}
'''
