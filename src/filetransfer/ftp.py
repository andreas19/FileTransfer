"""Source and target implementations for FTP and FTPS."""

import ftplib
import logging
import threading
import time
from contextlib import suppress
from functools import partial

import ftputil

from .base import BaseSource, BaseTarget
from .exceptions import ConnectError

_logger = logging.getLogger(__name__)


def _keepalive(ftp_host, interval):
    while True:
        time.sleep(interval)
        try:
            ftp_host.keep_alive()
        except Exception:
            break


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

            ftp_host = ftputil.FTPHost(session_factory=SessFac)
            ftp_host.use_list_a_option = self._host_cfg[host_id, 'dir_a_option']
            if self._host_cfg[host_id, 'keep_alive']:
                threading.Thread(target=_keepalive,
                                 args=(ftp_host,
                                       self._host_cfg[host_id, 'keep_alive']),
                                 daemon=True).start()
            return ftp_host
        except (OSError, ftputil.error.FTPError) as ex:
            raise ConnectError(f'Connection to server "{host}:{port}"'
                               f' failed: {ex}')

    def _close(self):
        with suppress(Exception):
            self._conn.close()


class FTPSource(_Ftp, BaseSource):
    """Source implementation for FTP and FTPS.

    :param job_cfg: job configuration
    :type job_cfg: easimpconf.Config
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
    :type job_cfg: easimpconf.Config
    :param bool tls: if True FTPS will be used
    """

    def __init__(self, job_cfg, tls=False):
        super().__init__(job_cfg, job_cfg['target_host_cfg'], tls)
        self._path_base = self._conn.path.basename
        self._path_dir = self._conn.path.dirname
        self._path_exists = self._conn.path.exists
        self._makedirs = partial(self._conn.makedirs, exist_ok=True)
        self._rename = self._conn.rename
