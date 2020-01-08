"""Utility functions."""

try:
    from importlib.resources import read_text
except ImportError:
    from importlib_resources import read_text

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
        return f'[{host}]:{port}'
    else:
        return host


def terminate(n, f):
    """Signal handler for SIGTERM."""
    raise Terminated


def read_resource(name):
    """Read a resource as text."""
    return read_text(__package__ + '.data', name)
