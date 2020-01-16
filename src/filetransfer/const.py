"""Constants module."""

from enum import Enum

from .exceptions import (ConfigError, ConnectError, TransferError,
                         SingleInstanceError, Terminated)

FTP_PORT = 21  #: Default FTP port.

SSH_PORT = 22  #: Default SSH/SFTP port.

SMTP_PORT = 25  #: Default SMTP port.

ErrorsEnum = Enum('ErrorsEnum', 'NONE, FILES, CONFIG, CONNECT, TRANSFER, OTHER')

EXIT_CODES = dict(
    succ=0,                         # success
    conf=ConfigError.code,          # configuration error
    conn=ConnectError.code,         # connection error
    tran=TransferError.code,        # error during transfer of files
    sing=SingleInstanceError.code,  # single instance error
    cmdl=7,                         # command line syntax error
    term=Terminated.code,           # terminated by SIGTERM or SIGINT
    othe=9                          # another error
)
