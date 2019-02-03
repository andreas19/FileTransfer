"""Utility functions."""

from .const import SSH_PORT
from .exceptions import Terminated


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


def terminate(n, f):
    """Signal handler for SIGTERM."""
    raise Terminated
