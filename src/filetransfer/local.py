"""Source and target implementations for local filesystems."""

import logging
import os
from functools import partial

from .base import BaseSource, BaseTarget

_logger = logging.getLogger(__name__)


class _Local:
    def __init__(self, job_cfg):
        super().__init__(job_cfg)
        self._path_join = os.path.join
        self._open = open
        self._remove = os.remove

    def _close(self):
        pass


class LocalSource(_Local, BaseSource):
    """Source implementation for local filesystem.

    :param job_cfg: job configuration
    :type job_cfg: salmagundi.config.Config
    """

    def __init__(self, job_cfg):
        super().__init__(job_cfg)
        self._listdir = os.listdir
        self._isdir = os.path.isdir
        self._isfile = os.path.isfile


class LocalTarget(_Local, BaseTarget):
    """Target implementation for local filesystem.

    :param job_cfg: job configuration
    :type job_cfg: salmagundi.config.Config
    """

    def __init__(self, job_cfg):
        super().__init__(job_cfg)
        self._path_base = os.path.basename
        self._path_dir = os.path.dirname
        self._path_exists = os.path.exists
        self._makedirs = partial(os.makedirs, exist_ok=True)
        self._rename = os.rename
