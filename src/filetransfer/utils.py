"""Utility functions."""

from .const import SSH_PORT
from .exceptions import ConfigError


def str_to_tuple(s, sep):
    """Convert a string to a tuple.

    :param str s: a string
    :param str sep: the separator
    :return: a tuple
    :rtype: tuple(str)
    """
    if s:
        return tuple(x.strip() for x in s.split(sep) if x.strip())
    return ()


def split_host_port(s, dflt_port):
    """Split a string into host and port.

    :param str s: a string
    :param int dflt_port: default port in none is given in the string
    :return: host and  port
    :rtype: (str, int)
    :raises filetransfer.exceptions.ConfigError: if no valid port in string
    """
    a = s.split(':', 1)
    if len(a) == 1:
        return s, dflt_port
    try:
        return a[0], str2port(a[1])
    except ConfigError as ex:
        raise ConfigError('%s in "%s"' % (ex.args[0], s))


def str2port(s):
    """Convert a string to a port.

    :param str s: a string
    :return: a port
    :rtype: int
    :raises filetransfer.exceptions.ConfigError: if no valid port in string
    """
    try:
        port = int(s)
    except ValueError:
        raise ConfigError('Port must be integer')
    if 0 < port <= 65535:
        return port
    raise ConfigError('Port must be between 1 and 65535')


def format_knownhost(host, port):
    """Format a hostname for a  SSH ``known_hosts`` file.

    :param str host: a host
    :param int port: a port
    :return: hostname like ``[example.com]:8000`` or ``example.com``
    :rytpe: str
    """
    if port != SSH_PORT:
        return '[%s]:%d' % (host, port)
    else:
        return host


def format_hex(s):
    """Format a hexadecimal string.

    A colon will be inserted after every second character.

    :param str s: hexadecimal
    :return: string with formated hexdecimal
    :rtype: str
    """
    return ':'.join([s[i:i + 2] for i in range(0, len(s), 2)])
