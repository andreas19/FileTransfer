"""Exceptions module."""


class Error(Exception):
    """Base error."""


class ConfigError(Error):
    """Raised when there is a problem with the configuration."""

    code = 1  #: Status code


class ConnectError(Error):
    """Raised when there is a problem connecting to a server."""

    code = 2  #: Status code


class TransferError(Error):
    """Raised when there is a fatal problem during transfer."""

    code = 3  #: Status code


class Terminated(BaseException):
    """Raised when terminated with SIGTERM, SIGINT or KeyboardInterrupt.

    This is a subclass of :exc:`BaseException`.

    See :ref:`example <ref-configure-and-run>`.
    """

    code = 8  #: Status code
