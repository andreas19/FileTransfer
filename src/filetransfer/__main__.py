"""Main module.

usage:
 $prog [-v | -vv] [-c CONFIG] JOBID
 $prog -k [-H] [-p PORT] HOST FILE
 $prog -d [-p PORT] HOST FILE
 $prog -h | -V

 JOBID   the job id
 HOST    server name or IP
 FILE    known-hosts file

 -c, --config CONFIG  the application configuration file
                      If not given the value of the environment
                      variable $envvar will be used.
 -d, --delete         delete server hostkey from known-hosts file
 -H, --hash           hash hostnames
 -k, --hostkey        get hostkey from SFTP server
 -p, --port PORT      SFTP server port [default: $sshport]
 -v, --verbose        once: print message
                      twice: print stack trace

 -h, --help           show this help
 -V, --version        show the version

 return codes:
  $exit_codes
"""

import base64
import hashlib
import logging
import os
import sys
from contextlib import suppress

from paramiko import HostKeys, Transport, SSHException
from salmagundi import strings
from salmagundi.utils import docopt_helper

from . import __version__, set_sigterm_handler, config, job, utils
from .const import SSH_PORT, ExitCodes
from .exceptions import Error, ConfigError, ConnectError, Terminated

_PROGNAME = 'FileTransfer'
_ENV_VAR_NAME = 'FILETRANSFER_CFG'
_logger = logging.getLogger(__name__)


def main():
    """Execute command."""
    args = docopt_helper(__doc__.split('\n', 2)[2],
                         version_str=f'{_PROGNAME} {__version__}',
                         err_code=ExitCodes.CMDLINE.code,
                         prog=_PROGNAME.lower(),
                         envvar=_ENV_VAR_NAME,
                         sshport=SSH_PORT,
                         exit_codes=ExitCodes.as_doc())
    if args['--hostkey']:
        return _get_hostkey(args)
    if args['--delete']:
        return _del_hostkey(args)
    return _run_filetransfer(args)


def _run_filetransfer(args):
    set_sigterm_handler()
    verbose = args['--verbose']
    try:
        if args['--config']:
            cfg_file = args['--config']
        else:
            cfg_file = os.getenv(_ENV_VAR_NAME)
        app_cfg, job_cfg = config.configure(cfg_file, args['JOBID'])
        result, status = job.run(app_cfg, job_cfg)
        if verbose:
            print(f'Job finished: {result}')
    except Error as ex:
        _handle_exception(verbose, ex)
        status = ex.code
    except (KeyboardInterrupt, Terminated) as ex:
        _handle_exception(verbose, ex)
        status = Terminated.code
    except Exception as ex:
        # should not happen but may be useful for debugging
        _handle_exception(verbose, ex)
        status = ExitCodes.FAILURE.code
    _logger.debug('exit status=%d', status)
    return status


def _handle_exception(verbose, exc):
    if verbose:
        with suppress(AttributeError):
            print(f'Job finished: {exc.result}')
    if verbose == 1:
        if str(exc).strip():
            print(f'{exc.__class__.__name__}: {exc}', file=sys.stderr)
        else:
            print(exc.__class__.__name__, file=sys.stderr)
    if verbose == 2:
        import traceback
        traceback.print_exc()


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
            print(f'{name} ({hostkey.get_bits()}) Fingerprints:')
            fp_md5 = hashlib.md5()
            fp_md5.update(hostkey.asbytes())
            fp_md5_dig = strings.insert_separator(fp_md5.hexdigest(), ':', 2)
            print(f' MD5: {fp_md5_dig}')
            fp_sha = hashlib.sha256()
            fp_sha.update(hostkey.asbytes())
            fp_sha_dig = base64.b64encode(fp_sha.digest()).decode().strip('=')
            print(f' SHA256: {fp_sha_dig}')
            while True:
                a = input(f'Save this key to file "{file}" (yes/no)? ').lower()
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
                            print(f'Key for "{hostname}" exists'
                                  f' in file "{file}"')
                            addkey = False
                        else:
                            del hostkeys[hostname]
                            print(f'Key for "{hostname}" replaced'
                                  f' in file "{file}"')
                    else:
                        print(f'Key for "{hostname}" added in file "{file}"')
                else:
                    print(f'Key for "{hostname}" added in new file "{file}"')
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
        return ExitCodes.FAILURE.code
    return ExitCodes.SUCCESS.code


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
            print(f'Key for "{hostname}" deleted in file "{file}"')
        else:
            print(f'Key for "{hostname}" not found in file "{file}"')
    except (FileNotFoundError, ConfigError) as ex:
        print(ex, file=sys.stderr)
        return ConfigError.code
    except Exception as ex:
        print(repr(ex), file=sys.stderr)
        return ExitCodes.FAILURE.code
    return ExitCodes.SUCCESS.code


if __name__ == '__main__':
    sys.exit(main())
