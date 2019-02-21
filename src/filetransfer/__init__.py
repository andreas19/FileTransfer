"""Simple API to include ``filetransfer`` in a Python script.

.. attention::
   Changes in version 0.7.0:
    - There is no ``run()`` function any more. The required function is
      returned by :func:`configure`.
    - The function :func:`transfer` now returns a :class:`JobResult` object.
"""

import configparser

from . import config, job
from .exceptions import (Error, ConfigError, ConnectError,
                         TransferError, Terminated)
from .job import JobResult

__version__ = '0.7.3'

__all__ = ['Error', 'ConfigError', 'ConnectError', 'TransferError',
           'Terminated', 'JobResult', 'configure', 'transfer']


def configure(cfg_file, job_id, **kwargs):
    """Configure the application.

    This function returns a function that must be called
    to run the actual file transfer. The function may
    raise :exc:`~filetransfer.ConnectError`, :exc:`~filetransfer.TransferError`,
    :exc:`Terminated`, or :exc:`Exception` if another error occurs.
    The function takes one optional argument that must be an instance of a
    subclass of :exc:`BaseException`
    that will be reraised within ``run()``. The intended use for this is
    to handle an exception from code between ``configure`` and ``run`` in
    the usual way (logging and sending an email notification). The transfer
    itself will not be run. See :ref:`example <ref-configure-and-run>`.

    .. versionchanged:: 0.7.3 add exception parameter to run()

    You can put your own configuration sections in the application
    and job configuration files. The names of theses sections must
    start with ``x:``. If you define the same name in both configuration
    files the sections will be merged with the keys in the job
    configuration file taking precedence. The prefix ``x:`` will
    be stripped from the section names before putting them in a newly
    created :class:`~configparser.ConfigParser` object that will be returned.

    The logging configuration from ``cfg_file`` will only be used if
    logging was not configured before the call to this function.

    :param cfg_file: the application configuration file
    :type cfg_file: :term:`path-like object`
    :param str job_id: the Job-ID
    :param kwargs: :class:`~configparser.ConfigParser` arguments for
                   the extra configuration
    :return: run function and extra configuration
    :rtype: function(), configparser.ConfigParser
    :raises filetransfer.ConfigError: if there is a problem with
                                      the configuration
    :raises configparser.Error: if there is a problem while parsing
                                one of the configuration files
    :raises OSError: if there is a problem while reading one of the
                     configuration files
    """
    app_cfg, job_cfg = config.configure(cfg_file, job_id)
    cp = configparser.ConfigParser(**kwargs)
    with open(cfg_file) as fh:
        cp.read_file(fh)
    with job_cfg['job_cfg_file'].open() as fh:
        cp.read_file(fh)
    d = {}
    for sec in [sec for sec in cp.sections() if sec.startswith('x:')]:
        d[sec[2:]] = dict(cp.items(sec))
    cp.clear()
    cp.read_dict(d)

    def run(exc=None):
        job.run(app_cfg, job_cfg, exc)
    return run, cp


def transfer(src_cfg, tgt_cfg=None):
    """Transfer files.

    The first parameter (``src_cfg``) may be a :class:`dict` or a
    :class:`~configparser.ConfigParser` object.

    If it is a :class:`dict` the argument ``tgt_cfg`` must also be a
    dict and they must represent valid ``[source]`` and ``[target]``
    sections of a :ref:`ref-job-configuration`.

    Else the :class:`~configparser.ConfigParser` object must contain
    those sections and the second parameter can be omitted because
    it will be ignored.

    When using FTP, FTPS or SFTP the ``host_id`` option must be omitted
    and the options from the host configuration must be contained in the
    above configuration objects.

    :param src_cfg: the source or job configuration
    :type src_cfg: dict or configparser.ConfigParser
    :param tgt_cfg: the target configuration
    :type tgt_cfg: dict or None
    :return: job result
    :rtype: filetransfer.JobResult
    :raises filetransfer.ConfigError: if there is a problem with
                                      the configuration
    :raises filetransfer.ConnectError: if there is a connection problem
    :raises filetransfer.TransferError: if there is a fatal problem
                                        during transfer
    :raises Exception: if another error occurs
    """
    if not isinstance(src_cfg, configparser.ConfigParser):
        cp = configparser.ConfigParser()
        cp.read_dict({'source': src_cfg, 'target': tgt_cfg})
    else:
        cp = src_cfg
    job_cfg = config.get_job_cfg(cp)
    if 'type' in cp['source']:
        host_cfg = config.get_host_cfg(cp, 'source')
        job_cfg.add('source_host_cfg', host_cfg)
    if 'type' in cp['target']:
        host_cfg = config.get_host_cfg(cp, 'target')
        job_cfg.add('target_host_cfg', host_cfg)
    config.set_urls(job_cfg)
    return job.transfer(job_cfg)
