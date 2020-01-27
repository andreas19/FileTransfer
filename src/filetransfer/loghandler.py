"""Log handler."""

import sys
from logging import Handler


class LogHandler(Handler):
    """Log handler class."""

    terminator = '\n'

    def __init__(self, filename):
        super().__init__()
        self._filename = filename
        self._activated = False
        self._enabled = True
        self._out = None
        self._buffer = []

    def _open(self):
        if self._filename:
            self._out = open(self._filename, 'w')
        else:
            self._out = sys.stderr

    def emit(self, record):
        """Overwrite ``emit``."""
        if not self._enabled:
            return
        if self._activated:
            try:
                self._out.write(self.format(record) + self.terminator)
                self._out.flush()
            except Exception:
                self.handleError(record)
        else:
            self._buffer.append(record)

    def handle(self, record):
        """Overwrite ``handle``."""
        if not self._enabled:
            return
        super().handle(record)

    def close(self):
        """Overwrite ``close``."""
        self.acquire()
        try:
            try:
                if self._filename and self._out:
                    self._out.close()
            finally:
                super().close()
        finally:
            self.release()

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
        if not self._enabled or self._activated:
            return
        self.acquire()
        try:
            self._open()
            self._activated = True
            for record in self._buffer:
                self.handle(record)
            self._buffer = None
        finally:
            self.release()

    def disable(self):
        """Disable logging."""
        if not self._enabled:
            return
        self.acquire()
        try:
            self._enabled = False
            self._buffer = None
        finally:
            self.release()

    def purge(self, level):
        """Purge records in buffer."""
        if not self._enabled or self._activated:
            return
        self.acquire()
        try:
            self._buffer = [record for record in self._buffer
                            if record.levelno >= level]
        finally:
            self.release()
