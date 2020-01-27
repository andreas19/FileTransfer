"""Constants module."""

from enum import Enum

FTP_PORT = 21  #: Default FTP port.

SSH_PORT = 22  #: Default SSH/SFTP port.

SMTP_PORT = 25  #: Default SMTP port.


class ExitCodes(Enum):
    """Exit Codes."""

    SUCCESS = (0, 'success')
    ERRORS = (1, 'with errors')
    FAILURE = (2, 'failure')
    CONFIG = (3, 'config error')
    CMDLINE = (4, 'cmd line syntax error')
    TERMINATED = (5, 'terminated')

    def __init__(self, code, descr):
        self.code = code
        self.descr = descr

    @classmethod
    def as_doc(cls):
        """Return string for usage documentation."""
        return '\n'.join(f'  {member.code}  {member.descr}'
                         for member in cls.__members__.values()).strip()


class FileTags(Enum):
    """Tags for ``file_list`` of :class:`JobResult`.

    Members:
     - ``TRANSF``: ``'='`` (transferred)
     - ``SRCERR``: ``'>'`` (source error)
     - ``TGTERR``: ``'<'`` (target error)

    The string representation of an enum member is just the value of the member.

    .. versionadded:: 0.10.0
    """

    TRANSF = '='
    SRCERR = '>'
    TGTERR = '<'

    def __str__(self):
        return self.value
