"""Source and target implementations for SFTP."""

import logging
import posixpath
import stat
from contextlib import suppress

from paramiko import HostKeys, SSHException, Transport, RSAKey, DSSKey

from . import config, utils
from .base import BaseSource, BaseTarget, server_config
from .const import SSH_PORT
from .exceptions import ConnectError

_logger = logging.getLogger(__name__)


class SFTPSource(BaseSource):
    """Source implementation for SFTP.

    :param cfg: source configuration
    :type cfg: :class:`configparser.ConfigParser` section
    """

    def __init__(self, cfg):
        super().__init__(cfg)
        self._conn = _connect(self, cfg)
        self._path_join = posixpath.join
        self._open = self._conn.open
        self._remove = self._conn.remove
        self._listdir = self._conn.listdir
        _logger.info('Source - SFTP: %s:%d | %s',
                     self._host, self._port, self._path)

    def _isdir(self, path):
        try:
            return stat.S_ISDIR(self._conn.stat(path).st_mode)
        except OSError:
            return False

    def _isfile(self, path):
        try:
            return stat.S_ISREG(self._conn.stat(path).st_mode)
        except OSError:
            return False

    def _close(self):
        with suppress(Exception):
            self._conn.get_channel().get_transport().close()


class SFTPTarget(BaseTarget):
    """Target implementation for SFTP.

    :param cfg: target configuration
    :type cfg: :class:`configparser.ConfigParser` section
    """

    def __init__(self, cfg):
        super().__init__(cfg)
        self._conn = _connect(self, cfg)
        self._path_join = posixpath.join
        self._open = self._conn.open
        self._remove = self._conn.remove
        self._path_base = posixpath.basename
        self._path_dir = posixpath.dirname
        self._rename = self._conn.rename
        _logger.info('Target - SFTP: %s:%d | %s',
                     self._host, self._port, self._path)

    def _path_exists(self, path):
        try:
            self._conn.stat(path)
            return True
        except OSError:
            return False

    def _makedirs(self, path):
        p = ''
        for x in path.split(posixpath.sep):
            p = posixpath.join(p, x)
            if not self._path_exists(p):
                self._conn.mkdir(p)

    def _close(self):
        with suppress(Exception):
            self._conn.get_channel().get_transport().close()


def _connect(obj, cfg):
    server_config(obj, cfg, SSH_PORT)
    if hasattr(config, 'sftp_cfg'):
        sftp_cfg = config.sftp_cfg
    else:
        sftp_cfg = {}
    known_hosts = cfg.get('known_hosts') or sftp_cfg['known_hosts']
    key_file = cfg.get('key_file')
    try:
        if key_file:
            if key_file.upper() == 'RSA':
                key = RSAKey(filename=sftp_cfg['key_rsa_file'],
                             password=sftp_cfg.get('key_rsa_pass'))
            elif key_file.upper() == 'DSA':
                key = DSSKey(filename=sftp_cfg['key_dsa_file'],
                             password=sftp_cfg.get('key_dsa_pass'))
            else:
                try:
                    key = RSAKey(filename=key_file,
                                 password=cfg.get('key_pass'))
                except SSHException:
                    try:
                        key = DSSKey(filename=key_file,
                                     password=cfg.get('key_pass'))
                    except SSHException:
                        raise SSHException('Could not create RSA or DSA key')
            _logger.debug('private key: %s', key.get_name())
        else:
            key = None
        hostname = utils.format_knownhost(obj._host, obj._port)
        hostkeys = HostKeys(known_hosts)
        transport = Transport((obj._host, obj._port))
        transport.start_client(timeout=obj._timeout)
        hostkey = transport.get_remote_server_key()
        if not hostkeys.check(hostname, hostkey):
            raise SSHException('Incorrect hostkey')
        if key:
            transport.auth_publickey(obj._user, key)
        else:
            transport.auth_password(obj._user, obj._passwd)
        client = transport.open_sftp_client()
        client.get_channel().settimeout(obj._timeout)
        _logger.debug('client for %s created', hostname)
        return client
    except (OSError, SSHException) as ex:
        raise ConnectError('Connection to server "%s:%d" failed: %s' %
                           (obj._host, obj._port, ex.args))
