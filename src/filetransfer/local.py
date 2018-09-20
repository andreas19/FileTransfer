"""Source and target implementations for local filesystems."""

import logging
import os
from functools import partial

from .base import BaseSource, BaseTarget

_logger = logging.getLogger(__name__)


class LocalSource(BaseSource):
    """Source implementation for local filesystem.

    :param cfg: source configuration
    :type cfg: :class:`configparser.ConfigParser` section
    """

    def __init__(self, cfg):
        super().__init__(cfg)
        self._path_join = os.path.join
        self._open = open
        self._remove = os.remove
        self._listdir = os.listdir
        self._isdir = os.path.isdir
        self._isfile = os.path.isfile
        _logger.info('Source - LOCAL: %s', os.path.abspath(self._path))

    def _close(self):
        pass


class LocalTarget(BaseTarget):
    """Target implementation for local filesystem.

    :param cfg: target configuration
    :type cfg: :class:`configparser.ConfigParser` section
    """

    def __init__(self, cfg):
        super().__init__(cfg)
        self._path_join = os.path.join
        self._open = open
        self._remove = os.remove
        self._path_base = os.path.basename
        self._path_dir = os.path.dirname
        self._path_exists = os.path.exists
        self._makedirs = partial(os.makedirs, exist_ok=True)
        self._rename = os.rename
        _logger.info('Target - LOCAL: %s', os.path.abspath(self._path))

    def _close(self):
        pass
