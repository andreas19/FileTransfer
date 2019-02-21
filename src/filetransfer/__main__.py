"""Main module.

usage:
 %(prog)s [-v] [-c CONFIG] JOBID
 %(prog)s -k [-H] [-p PORT] HOST FILE
 %(prog)s -d [-p PORT] HOST FILE
 %(prog)s -h | -V

 JOBID   the job id
 HOST    server name or IP
 FILE    known-hosts file

 -c, --config CONFIG  the application configuration file
                      If not given the value of the environment
                      variable %(envvar)s will be used.
 -d, --delete         delete server hostkey from known-hosts file
 -H, --hash           hash hostnames
 -k, --hostkey        get hostkey from SFTP server
 -p, --port PORT      SFTP server port [default: %(sshport)d]
 -v, --verbose        print traceback for uncaught errors

 -h, --help           show this help
 -V, --version        show the version

 return codes:
  0   success
  1   configuration error
  2   connect error
  3   transfer error
  8   terminated
  9   another error
"""

import base64
import hashlib
import locale
import logging
import os
import signal
import sys

from docopt import docopt
from paramiko import HostKeys, Transport, SSHException
from salmagundi import strings

from . import __version__, config, job, utils
from .const import SSH_PORT
from .exceptions import Error, ConfigError, ConnectError, Terminated

progname = 'FileTransfer'
env_var_name = 'FILETRANSFER_CFG'
other_err_code = 9
_logger = logging.getLogger(__name__)


def main():
    """Execute command."""
    locale.setlocale(locale.LC_ALL, '')
    args = docopt(__doc__.split('\n', 2)[2] %
                  dict(prog=progname.lower(), envvar=env_var_name,
                       sshport=SSH_PORT),
                  version='%s %s' % (progname, __version__))
    if args['--hostkey']:
        return _get_hostkey(args)
    if args['--delete']:
        return _del_hostkey(args)
    return _run_filetransfer(args)


def _run_filetransfer(args):
    signal.signal(signal.SIGTERM, utils.terminate)
    try:
        if args['--config']:
            cfg_file = args['--config']
        else:
            cfg_file = os.getenv(env_var_name)
        app_cfg, job_cfg = config.configure(cfg_file, args['JOBID'])
        job.run(app_cfg, job_cfg)
        status = 0
    except Error as ex:
        status = ex.code
    except (KeyboardInterrupt, Terminated):
        status = Terminated.code
    except Exception:
        if args['--verbose']:
            import traceback
            traceback.print_exc()
        status = other_err_code
    _logger.debug('exit status=%d', status)
    return status


def _get_hostkey(args):
    host = args['HOST']
    file = args['FILE']
    hash_ = args['--hash']
    try:
        port = strings.str2port(args['--port'])
        with Transport((host, port)) as transport:
            transport.start_client()
            hostkey = transport.get_remote_server_key()
            name = hostkey.get_name().split('-', 1)[1].upper()
            # same fingerprints as the OpenSSH commands generate
            print('%s (%d) Fingerprints:' % (name, hostkey.get_bits()))
            fp_md5 = hashlib.md5()
            fp_md5.update(hostkey.asbytes())
            print(' MD5: %s' %
                  strings.insert_separator(fp_md5.hexdigest(), ':', 2))
            fp_sha = hashlib.sha256()
            fp_sha.update(hostkey.asbytes())
            print(' SHA256: %s' % base64.b64encode(fp_sha.digest()).
                  decode().strip('='))
            while True:
                a = input('Save this key to file "%s" (yes/no)? ' %
                          file).lower()
                if a in ('yes', 'no'):
                    break
                print('Type "yes" or "no"!')
            if a != 'no':
                hostname = utils.format_knownhost(host, port)
                hostkeys = HostKeys()
                addkey = True
                if os.path.exists(file):
                    hostkeys.load(file)
                    if hostkeys.lookup(hostname):
                        if hostkeys.check(hostname, hostkey):
                            print('Key for "%s" exists in file "%s"' %
                                  (hostname, file))
                            addkey = False
                        else:
                            del hostkeys[hostname]
                            print('Key for "%s" replaced in file "%s"' %
                                  (hostname, file))
                    else:
                        print('Key for "%s" added in file "%s"' %
                              (hostname, file))
                else:
                    print('Key for "%s" added in new file "%s"' %
                          (hostname, file))
                if addkey:
                    if hash_:
                        hostname = HostKeys.hash_host(hostname)
                    hostkeys.add(hostname, hostkey.get_name(), hostkey)
                    hostkeys.save(file)
    except ConfigError as ex:
        print(ex, file=sys.stderr)
        return ConfigError.code
    except (OSError, SSHException) as ex:
        print(ex, file=sys.stderr)
        return ConnectError.code
    except Exception as ex:
        print(repr(ex), file=sys.stderr)
        return other_err_code
    return 0


def _del_hostkey(args):
    host = args['HOST']
    file = args['FILE']
    try:
        port = strings.str2port(args['--port'])
        hostname = utils.format_knownhost(host, port)
        hostkeys = HostKeys()
        hostkeys.load(file)
        if hostkeys.lookup(hostname):
            del hostkeys[hostname]
            hostkeys.save(file)
            print('Key for "%s" deleted in file "%s"' % (hostname, file))
        else:
            print('Key for "%s" not found in file "%s"' % (hostname, file))
    except (FileNotFoundError, ConfigError) as ex:
        print(ex, file=sys.stderr)
        return ConfigError.code
    except Exception as ex:
        print(repr(ex), file=sys.stderr)
        return other_err_code
    return 0


if __name__ == '__main__':
    sys.exit(main())
