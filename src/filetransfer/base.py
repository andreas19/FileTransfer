"""Base classes for source and target implementations."""

import logging
import os
from contextlib import suppress
from fnmatch import fnmatch

_logger = logging.getLogger(__name__)

_CHUNK_SIZE = 64 * 1024


class Endpoint:
    """Base class for source and target implementations.

    :param str path: the path
    """

    def __init__(self, path):
        self._path = path.rstrip('/')

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._close()

    def _close(self):
        raise NotImplementedError(f'{self.__class__.__name__}._close()')


class BaseSource(Endpoint):
    """Base class for source implementations.

    Subclasses must define::

        self._path_join
        self._open
        self._remove
        self._listdir
        self._isdir
        self._isfile

    :param job_cfg: job configuration
    :type job_cfg: salmagundi.config.Config
    """

    def __init__(self, job_cfg):
        super().__init__(job_cfg['source', 'path'])
        _logger.info('Source: %s', job_cfg['source_url'])
        self._files = job_cfg['source', 'files']
        self._ignore = job_cfg['source', 'ignore']
        self._recursive = job_cfg['source', 'recursive']
        self._delete = job_cfg['source', 'delete']

    def _patterns(self, patterns):
        lst = []
        for p in patterns:
            if p.startswith('/'):
                lst.append(self._path_join(self._path, p[1:]))
            else:
                lst.append(self._path_join(self._path, p))
                lst.append(self._path_join(self._path, '*', p))
        return lst

    def _match(self, patterns, path):
        for p in patterns:
            if fnmatch(path, p) or fnmatch(os.path.join(path, ''), p):
                return True
        return False

    def _walk(self, path):
        for entry in sorted(self._listdir(path)):
            p = self._path_join(path, entry)
            if self._recursive and self._isdir(p):
                try:
                    yield from self._walk(p)
                except Exception as ex:
                    yield p, ex
            elif self._isfile(p):
                yield p, None

    def files(self):
        """Return an iterator that yields 2-tuples.

        The first element of the tuple is the file path relative to the source
        base path as a :class:`str`, the second a :term:`binary file` opened in
        read-mode.

        :return: iterator
        """
        files = self._patterns(self._files)
        ignore = self._patterns(self._ignore)
        path_len = len(self._path) + 1
        for file_path, exc in self._walk(self._path):
            if (self._match(files, file_path) and
                    not self._match(ignore, file_path)):
                _logger.debug('source files file_path=%s', file_path)
                if exc is not None:
                    _logger.error('Source: %s (%s)', file_path, exc)
                    yield file_path[path_len:], exc
                    continue
                try:
                    yield file_path[path_len:], self._open(file_path, 'rb')
                    if self._delete:
                        with suppress(Exception):
                            self._remove(file_path)
                except Exception as ex:
                    _logger.error('Source: %s (%s)', file_path, ex)
                    yield file_path[path_len:], ex


class BaseTarget(Endpoint):
    """Base class for target implementations.

    Subclasses must define::

        self._path_join
        self._open
        self._remove
        self._path_base
        self._path_dir
        self._path_exists
        self._makedirs
        self._rename

    :param job_cfg: job configuration
    :type job_cfg: salmagundi.config.Config
    """

    def __init__(self, job_cfg):
        super().__init__(job_cfg['target', 'path'])
        _logger.info('Target: %s', job_cfg['target_url'])
        self._temp = job_cfg['target', 'temp']

    def _temp_path(self, file_path):
        if self._temp:
            if self._temp[0] == 'dot':
                return (self._path_join(self._path_dir(file_path),
                        '.' + self._path_base(file_path)))
            elif self._temp[0] == 'ext':
                return file_path + self._temp[1]
            elif self._temp[0] == 'dir':
                d = self._path_join(self._path, self._temp[1])
                self._makedirs(d)
                return self._path_join(d, self._path_base(file_path))
        return None

    def store(self, path, reader):
        """Save file.

        See: :meth:`BaseSource.files`.

        :param str path: file path relative to the target base path
        :param reader: file reader
        :type reader: :term:`binary file` opened in read-mode
        """
        try:
            file_path = self._path_join(self._path, path)
            _logger.debug('target store file_path=%s', file_path)
            self._makedirs(self._path_dir(file_path))
            tmp_path = self._temp_path(file_path)
            _logger.debug('target store tmp_path=%s', tmp_path)
            if self._path_exists(file_path):
                self._remove(file_path)
            with self._open(tmp_path or file_path, 'wb') as fh:
                while fh.write(reader.read(_CHUNK_SIZE)):
                    pass
            if tmp_path:
                self._rename(tmp_path, file_path)
        except Exception as ex:
            _logger.error('Target: %s (%s)', file_path, ex)
            return ex
