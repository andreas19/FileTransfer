"""Source and target implementations for SFTP."""

import logging
import posixpath
import stat
from contextlib import suppress

from paramiko import (HostKeys, SSHException, Transport,
                      RSAKey, DSSKey, ECDSAKey, Ed25519Key)

from . import utils
from .base import BaseSource, BaseTarget
from .exceptions import ConnectError

_logger = logging.getLogger(__name__)

_KEY_TYPES = {
    'RSA': RSAKey,
    'DSA': DSSKey,
    'ECDSA': ECDSAKey,
    'ED25519': Ed25519Key
}


class _Sftp:
    def __init__(self, job_cfg, host_cfg):
        super().__init__(job_cfg)
        self._host_cfg = host_cfg
        self._conn = self._connect()
        self._path_join = posixpath.join
        self._open = self._conn.open
        self._remove = self._conn.remove

    def _connect(self):
        host_id = self._host_cfg['host_id']
        host, port = self._host_cfg[host_id, 'host']
        user = self._host_cfg[host_id, 'user']
        passwd = self._host_cfg[host_id, 'password']
        timeout = self._host_cfg[host_id, 'timeout'] or None
        known_hosts = self._host_cfg[host_id, 'known_hosts']
        key_type = self._host_cfg[host_id, 'key_type']
        key_file = self._host_cfg[host_id, 'key_file']
        key_pass = self._host_cfg[host_id, 'key_pass']
        try:
            if key_type:
                key = _KEY_TYPES[key_type](filename=key_file, password=key_pass)
                _logger.debug('private key: %s', key.get_name())
            else:
                key = None
            hostname = utils.format_knownhost(host, port)
            hostkeys = HostKeys(known_hosts)
            transport = Transport((host, port))
            transport.start_client(timeout=timeout)
            hostkey = transport.get_remote_server_key()
            if not hostkeys.check(hostname, hostkey):
                raise SSHException('Incorrect hostkey')
            if key:
                transport.auth_publickey(user, key)
            else:
                transport.auth_password(user, passwd)
            client = transport.open_sftp_client()
            client.get_channel().settimeout(timeout)
            _logger.debug('client for %s created', hostname)
            return client
        except (OSError, SSHException) as ex:
            raise ConnectError('Connection to server "%s:%d" failed: %s' %
                               (host, port, ex.args))

    def _close(self):
        with suppress(Exception):
            self._conn.get_channel().get_transport().close()


class SFTPSource(_Sftp, BaseSource):
    """Source implementation for SFTP.

    :param job_cfg: job configuration
    :type job_cfg: salmagundi.config.Config
    """

    def __init__(self, job_cfg):
        super().__init__(job_cfg, job_cfg['source_host_cfg'])
        self._listdir = self._conn.listdir

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


class SFTPTarget(_Sftp, BaseTarget):
    """Target implementation for SFTP.

    :param job_cfg: job configuration
    :type job_cfg: salmagundi.config.Config
    """

    def __init__(self, job_cfg):
        super().__init__(job_cfg, job_cfg['target_host_cfg'])
        self._path_base = posixpath.basename
        self._path_dir = posixpath.dirname
        self._rename = self._conn.rename

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
