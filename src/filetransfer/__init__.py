"""Simple API to include ``filetransfer`` in a Python script.

Either the functions :func:`configure` and :func:`run` must be
used together or only the function :func:`transfer`.
"""

import configparser

from . import config, job
from .exceptions import ConfigError, ConnectError

__version__ = '0.5.0'
__all__ = ['ConfigError', 'ConnectError', 'configure', 'run', 'transfer']
_job_cfg = None
_job_id = None


def configure(cfg_file, job_id):
    """Configure the application.

    You can put your own configuration sections in the application
    and job configuration files. The names of theses sections must
    start with ``x:``. If you define the same name in both configuration
    files the sections will be merged with the keys in the job
    configuration file taking precedence. The prefix ``x:`` will
    be stripped from the section names before putting them in a newly
    created :class:`configparser.ConfigParser` object that will be returned.

    :param cfg_file: the application configuration file
    :type cfg_file: :term:`path-like object`
    :param str job_id: the Job-ID
    :return: extra configuration
    :rtype: configparser.ConfigParser
    :raises filetransfer.ConfigError: if there is a problem with
                                      the configuration
    :raises configparser.Error: if there is a problem while parsing
                                one of the configuration files
    :raises OSError: if there is a problem while reading one of the
                     configuration files
    """
    global _job_id, _job_cfg
    _job_id = job_id
    app_cfg = configparser.ConfigParser(interpolation=None)
    with open(cfg_file) as fh:
        app_cfg.read_file(fh)
    config.configure(app_cfg, job_id)
    job_file = (config.jobs_dir / job_id).with_suffix('.cfg')
    _job_cfg = configparser.ConfigParser(interpolation=None)
    with job_file.open() as fh:
        _job_cfg.read_file(fh)
    extra_cfg = configparser.ConfigParser(interpolation=None)
    for cfg in (app_cfg, _job_cfg):
        for sec in [sec for sec in cfg.sections() if sec.startswith('x:')]:
            extra_cfg.read_dict({sec[2:]: cfg[sec]})
    return extra_cfg


def run():
    """Run a file transfer.

    The function :func:`configure` must be called before this function
    can be used.

    :raises filetransfer.ConfigError: if there is a problem with
                                      the configuration
    :raises filetransfer.ConnectError: if there is a connection problem
    :raises Exception: if another error occurs
    """
    if not _job_cfg:
        raise ConfigError('no configuration')
    job.run(_job_cfg, _job_id)


def transfer(src_cfg, tgt_cfg):
    """Transfer files.

    The ``src_cfg`` and ``tgt_cfg`` dicts must represent valid
    ``[source]`` and ``[target]`` sections of a :ref:`ref-job-configuration`.
    The values must all be strings even if they are boolean or numerical.

    :param dict src_cfg: the source configuration
    :param dict tgt_cfg: the target configuration
    :return: files count, source error count, target error count
    :rtype: (int, int, int)
    :raises filetransfer.ConfigError: if there is a problem with
                                      the configuration
    :raises filetransfer.ConnectError: if there is a connection problem
    :raises Exception: if another error occurs
    """
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read_dict({'source': src_cfg, 'target': tgt_cfg})
    return job.transfer(cfg)
