"""Base classes for source and target implementations."""

import fnmatch
import logging

from . import utils
from .exceptions import ConfigError

_logger = logging.getLogger(__name__)


def server_config(obj, cfg, dflt_port):
    """Set server configuration.

    :param obj: source or target object
    :param cfg: source or target configuration
    :type cfg: :class:`configparser.ConfigParser` section
    :param int dflt_port: default port
    """
    obj._host, obj._port = utils.split_host_port(cfg['host'], dflt_port)
    obj._user = cfg['user']
    obj._passwd = cfg.get('password', '')
    obj._timeout = cfg.getfloat('timeout') or None


class Endpoint:
    """Base class for source and target implementations.

    :param cfg: source or target configuration
    :type cfg: :class:`configparser.ConfigParser` section

    """

    def __init__(self, cfg):
        self._path = cfg['path']
        self.error_cnt = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._close()


class BaseSource(Endpoint):
    """Base class for source implementations.

    :param cfg: source configuration
    :type cfg: :class:`configparser.ConfigParser` section
    """

    def __init__(self, cfg):
        super().__init__(cfg)
        self._files = utils.str_to_tuple(cfg['files'], ',')
        _logger.debug('source files=%s', self._files)
        self._ignore = utils.str_to_tuple(cfg.get('ignore', '.*'), ',')
        _logger.debug('source ignore=%s', self._ignore)
        try:
            self._recursive = cfg.getboolean('recursive', False)
        except ValueError as ex:
            raise ConfigError('Wrong value for "source.recursive": %s' % ex)
        try:
            self._delete = cfg.getboolean('delete', False)
        except ValueError as ex:
            raise ConfigError('Wrong value for "source.delete": %s' % ex)
        _logger.debug('source recursive=%s | delete=%s',
                      self._recursive, self._delete)

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
            if fnmatch.fnmatch(path, p):
                return True
        return False

    def _walk(self, path):
        for entry in sorted(self._listdir(path)):
            p = self._path_join(path, entry)
            if self._recursive and self._isdir(p):
                try:
                    for file_path in self._walk(p):
                        yield file_path
                except Exception as ex:
                    self.error_cnt += 1
                    _logger.error('Source - directory: %s (%s)', p, ex)
            elif self._isfile(p):
                yield p

    def files(self):
        """Return a generator that yields 2-tuples.

        The first element of the tuple is the file path as a :class:`str`,
        the second a :term:`binary file` opened in read-mode.

        :return: generator
        """
        files = self._patterns(self._files)
        ignore = self._patterns(self._ignore)
        for file_path in self._walk(self._path):
            if (self._match(files, file_path) and
                    not self._match(ignore, file_path)):
                _logger.debug('source files file_path=%s', file_path)
                try:
                    yield (file_path[len(self._path) + 1:],
                           self._open(file_path, 'rb'))
                    if self._delete:
                        self._remove(file_path)
                except Exception as ex:
                    self.error_cnt += 1
                    _logger.error('Source - file: %s (%s)', file_path, ex)


class BaseTarget(Endpoint):
    """Base class for target implementations.

    :param cfg: target configuration
    :type cfg: :class:`configparser.ConfigParser` section
    """

    def __init__(self, cfg):
        super().__init__(cfg)
        self._temp = utils.str_to_tuple(cfg.get('temp', ''), ':')
        _logger.debug('target temp=%s', self._temp)
        if self._temp and (len(self._temp) > 2 or
                           self._temp[0] not in ('dot', 'ext', 'dir') or
                           self._temp[0] == 'dot' and len(self._temp) > 1):
            raise ConfigError('Wrong value for "target.temp": %s' %
                              cfg['temp'])

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

    def store(self, file_path, reader):
        """Save file.

        See: :meth:`BaseSource.files`.

        :param str file_path: file path
        :param reader: file reader
        :type reader: :term:`binary file` opened in read-mode
        """
        try:
            full_path = self._path_join(self._path, file_path)
            _logger.debug('target store full_path=%s', full_path)
            self._makedirs(self._path_dir(full_path))
            tmp_path = self._temp_path(full_path)
            _logger.debug('target store tmp_path=%s', tmp_path)
            if self._path_exists(full_path):
                self._remove(full_path)
            with self._open(tmp_path or full_path, 'wb') as fh:
                fh.write(reader.read())
            if tmp_path:
                self._rename(tmp_path, full_path)
            return True
        except Exception as ex:
            self.error_cnt += 1
            _logger.error('Target - file: %s (%s)', file_path, ex)
        return False
