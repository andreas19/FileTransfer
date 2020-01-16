"""Utility functions."""

try:
    from importlib.resources import read_text
except ImportError:
    from importlib_resources import read_text

from logging import FileHandler, StreamHandler
from logging.handlers import MemoryHandler

from .const import SSH_PORT


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


def read_resource(name):
    """Read a resource as text."""
    return read_text(__package__ + '.data', name)


class LogHandler(MemoryHandler):
    """Log handler class."""

    def __init__(self, filename):
        if filename:
            target = FileHandler(filename, mode='w', delay=True)
        else:
            target = StreamHandler()
        super().__init__(0, target=target)
        self._activated = False
        self._enabled = True

    @property
    def activated(self):
        """Return ``activated`` property."""
        return self._activated

    @property
    def enabled(self):
        """Return ``enabled`` property."""
        return self._enabled

    def activate(self):
        """Activate flushing log records to target."""
        self._activated = True

    def disable(self):
        """Disable logging."""
        self._enabled = False
        self.buffer.clear()

    def shouldFlush(self, record):
        """Overwrite ``shouldFlush``."""
        return self._activated

    def flush(self):
        """Overwrite ``flush``."""
        if self._activated:
            super().flush()

    def setFormatter(self, fmt):
        """Overwrite ``setFormatter``."""
        self.target.setFormatter(fmt)

    def emit(self, record):
        """Overwrite ``emit``."""
        if self._enabled:
            super().emit(record)
