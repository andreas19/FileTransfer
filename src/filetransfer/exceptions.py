"""Exceptions module."""


class Error(Exception):
    """Base error."""


class ConfigError(Error):
    """Raised when there is a problem with the configuration."""


class ConnectError(Error):
    """Raised when there is a problem connecting to a server."""


class TransferError(Error):
    """Raised when there is a fatal problem during transfer."""


class Terminated(BaseException):
    """Raised when terminated with SIGTERM, SIGINT or KeyboardInterrupt."""
