"""Constants module."""

from enum import Enum

FTP_PORT = 21  #: Default FTP port.

SSH_PORT = 22  #: Default SSH/SFTP port.

SMTP_PORT = 25  #: Default SMTP port.

ErrorsEnum = Enum('ErrorsEnum', 'NONE, FILES, CONFIG, CONNECT, TRANSFER, OTHER')
