"""Source and target implementations for FTP and FTPS."""

import ftplib
import logging
from contextlib import suppress

import ftputil
import ftputil.session

from .base import BaseSource, BaseTarget, server_config
from .const import FTP_PORT
from .exceptions import ConnectError

_logger = logging.getLogger(__name__)


class FTPSource(BaseSource):
    """Source implementation for FTP and FTPS.

    :param cfg: source configuration
    :type cfg: :class:`configparser.ConfigParser` section
    :param bool tls: if True FTPS will be used
    """

    def __init__(self, cfg, tls=False):
        super().__init__(cfg)
        self._conn = _connect(self, cfg, tls)
        self._path_join = self._conn.path.join
        self._open = self._conn.open
        self._remove = self._conn.remove
        self._listdir = self._conn.listdir
        self._isdir = self._conn.path.isdir
        self._isfile = self._conn.path.isfile
        _logger.info('Source - FTP%s: %s:%d | %s', 'S' if tls else '',
                     self._host, self._port, self._path)

    def _close(self):
        with suppress(Exception):
            self._conn.close()


class FTPTarget(BaseTarget):
    """Target implementation for FTP and FTPS.

    :param cfg: target configuration
    :type cfg: :class:`configparser.ConfigParser` section
    :param bool tls: if True FTPS will be used
    """

    def __init__(self, cfg, tls=False):
        super().__init__(cfg)
        self._conn = _connect(self, cfg, tls)
        self._path_join = self._conn.path.join
        self._open = self._conn.open
        self._remove = self._conn.remove
        self._path_base = self._conn.path.basename
        self._path_dir = self._conn.path.dirname
        self._path_exists = self._conn.path.exists
        self._makedirs = self._conn.makedirs
        self._rename = self._conn.rename
        _logger.info('Target - FTP%s: %s:%d | %s', 'S' if tls else '',
                     self._host, self._port, self._path)

    def _close(self):
        with suppress(Exception):
            self._conn.close()


def _connect(obj, cfg, tls):
    server_config(obj, cfg, FTP_PORT)
    passive_mode = cfg.getboolean('passive_mode', True)
    encrypt_data = cfg.getboolean('encrypt_data''', True)
    try:
        class SessFac(ftplib.FTP_TLS if tls else ftplib.FTP):
            def __init__(self):
                super().__init__()
                self.connect(obj._host, obj._port, obj._timeout)
                self.login(obj._user, obj._passwd)
                self.set_pasv(passive_mode)
                if tls and encrypt_data:
                    self.prot_p()

        return ftputil.FTPHost(session_factory=SessFac)
    except (OSError, ftputil.error.FTPError) as ex:
        raise ConnectError('Connection to server "%s:%d" failed: %s' %
                           (obj._host, obj._port, ex))
