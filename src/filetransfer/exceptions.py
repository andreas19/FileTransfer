"""Exceptions module."""

from .const import ExitCodes


class Error(Exception):
    """Base error."""


class ConfigError(Error):
    """Raised when there is a problem with the configuration.

    .. versionchanged:: 0.10.0 ``code`` 1 -> 3
    """

    code = ExitCodes.CONFIG.code  #: Status code


class ConnectError(Error):
    """Raised when there is a problem connecting to a server."""

    code = ExitCodes.FAILURE.code  #: Status code


class TransferError(Error):
    """Raised when there is a fatal problem during transfer.

    .. versionchanged:: 0.10.0 ``code`` 3 -> 2
    """

    code = ExitCodes.FAILURE.code  #: Status code


class SingleInstanceError(Error):
    """Raised when a single instance requirement is violated.

    .. versionadded:: 0.9.0
    .. versionchanged:: 0.10.0 ``code`` 4 -> 0
    """

    code = ExitCodes.SUCCESS.code  #: Status code


class NotReadyError(Error):
    """Raised when a ready file is required but not present.

    .. versionadded:: 0.10.0
    """

    code = ExitCodes.SUCCESS.code  #: Status code


class Terminated(BaseException):
    """Raised when terminated with SIGTERM.

    This is a subclass of :exc:`BaseException`.

    See: :func:`filetransfer.set_sigterm_handler`

    .. versionchanged:: 0.10.0 ``code`` 8 -> 5
    """

    code = ExitCodes.TERMINATED.code  #: Status code
