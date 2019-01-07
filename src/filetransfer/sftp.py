"""Source and target implementations for SFTP."""

import logging
import posixpath
import stat
from contextlib import suppress

from paramiko import (HostKeys, SSHException, Transport,
                      RSAKey, DSSKey, ECDSAKey, Ed25519Key)

from . import config, utils
from .base import BaseSource, BaseTarget, server_config
from .const import SSH_PORT
from .exceptions import ConnectError, ConfigError

_logger = logging.getLogger(__name__)
_KEY_TYPES = {
    'RSA': (RSAKey, 'key_rsa_file', 'key_rsa_pass'),
    'DSA': (DSSKey, 'key_dsa_file', 'key_dsa_pass'),
    'ECDSA': (ECDSAKey, 'key_ecdsa_file', 'key_ecdsa_pass'),
    'ED25519': (Ed25519Key, 'key_ed25519_file', 'key_ed25519_pass')
}


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
    key_type = cfg.get('key_type')
    try:
        if key_type:
            key_type = key_type.upper()
            key_file = cfg.get('key_file')
            try:
                if key_file:
                    key_pass = cfg.get('key_pass')
                else:
                    key_file = sftp_cfg.get(_KEY_TYPES[key_type][1])
                    if not key_file:
                        raise ConfigError(
                            'Missing "%s" in application configuration' %
                            _KEY_TYPES[key_type][1])
                    key_pass = sftp_cfg.get(_KEY_TYPES[key_type][2])
                key = _KEY_TYPES[key_type][0](filename=key_file,
                                              password=key_pass)
            except KeyError:
                raise ConfigError('Unknown key type: %s' % key_type)
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
