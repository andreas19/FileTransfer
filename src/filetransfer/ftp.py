"""Source and target implementations for FTP and FTPS."""

import ftplib
import logging
from contextlib import suppress

import ftputil
import ftputil.session

from .base import BaseSource, BaseTarget
from .exceptions import ConnectError

_logger = logging.getLogger(__name__)


class _Ftp:
    def __init__(self, job_cfg, host_cfg, tls):
        super().__init__(job_cfg)
        self._host_cfg = host_cfg
        self._tls = tls
        self._conn = self._connect()
        self._path_join = self._conn.path.join
        self._open = self._conn.open
        self._remove = self._conn.remove

    def _connect(self):
        host_id = self._host_cfg['host_id']
        host, port = self._host_cfg[host_id, 'host']
        user = self._host_cfg[host_id, 'user']
        passwd = self._host_cfg[host_id, 'password']
        timeout = self._host_cfg[host_id, 'timeout'] or None
        passive_mode = self._host_cfg[host_id, 'passive_mode']
        encrypt_data = self._host_cfg[host_id, 'encrypt_data']
        tls = self._tls
        try:
            class SessFac(ftplib.FTP_TLS if tls else ftplib.FTP):
                def __init__(self):
                    super().__init__()
                    self.connect(host, port, timeout)
                    self.login(user, passwd)
                    self.set_pasv(passive_mode)
                    if tls and encrypt_data:
                        self.prot_p()

            return ftputil.FTPHost(session_factory=SessFac)
        except (OSError, ftputil.error.FTPError) as ex:
            raise ConnectError('Connection to server "%s:%d" failed: %s' %
                               (host, port, ex))

    def _close(self):
        with suppress(Exception):
            self._conn.close()


class FTPSource(_Ftp, BaseSource):
    """Source implementation for FTP and FTPS.

    :param job_cfg: job configuration
    :type job_cfg: salmagundi.config.Config
    :param bool tls: if True FTPS will be used
    """

    def __init__(self, job_cfg, tls=False):
        super().__init__(job_cfg, job_cfg['source_host_cfg'], tls)
        self._listdir = self._conn.listdir
        self._isdir = self._conn.path.isdir
        self._isfile = self._conn.path.isfile


class FTPTarget(_Ftp, BaseTarget):
    """Target implementation for FTP and FTPS.

    :param job_cfg: job configuration
    :type job_cfg: salmagundi.config.Config
    :param bool tls: if True FTPS will be used
    """

    def __init__(self, job_cfg, tls=False):
        super().__init__(job_cfg, job_cfg['target_host_cfg'], tls)
        self._path_base = self._conn.path.basename
        self._path_dir = self._conn.path.dirname
        self._path_exists = self._conn.path.exists
        self._makedirs = self._conn.makedirs
        self._rename = self._conn.rename
