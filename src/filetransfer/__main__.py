"""Main module.

usage:
 $prog [-v] [-c CONFIG] JOBID
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
 -v, --verbose        print stack trace for uncaught errors

 -h, --help           show this help
 -V, --version        show the version

 return codes:
  $succ   success
  $conf   configuration error
  $conn   connect error
  $tran   transfer error
  $sing   single instance error
  $cmdl   command line error
  $term   terminated
  $othe   another error
"""

import base64
import hashlib
import logging
import os
import sys

from paramiko import HostKeys, Transport, SSHException
from salmagundi import strings
from salmagundi.utils import docopt_helper

from . import __version__, set_sigterm_handler, config, job, utils
from .const import SSH_PORT, EXIT_CODES
from .exceptions import Error, ConfigError, ConnectError, Terminated

progname = 'FileTransfer'
env_var_name = 'FILETRANSFER_CFG'
logger = logging.getLogger(__name__)


def main():
    """Execute command."""
    args = docopt_helper(__doc__.split('\n', 2)[2],
                         version_str=f'{progname} {__version__}',
                         err_code=EXIT_CODES['cmdl'],
                         prog=progname.lower(),
                         envvar=env_var_name,
                         sshport=SSH_PORT,
                         **EXIT_CODES)
    if args['--hostkey']:
        return _get_hostkey(args)
    if args['--delete']:
        return _del_hostkey(args)
    return _run_filetransfer(args)


def _run_filetransfer(args):
    set_sigterm_handler()
    try:
        if args['--config']:
            cfg_file = args['--config']
        else:
            cfg_file = os.getenv(env_var_name)
        app_cfg, job_cfg = config.configure(cfg_file, args['JOBID'])
        job.run(app_cfg, job_cfg)
        status = EXIT_CODES['succ']
    except Error as ex:
        status = ex.code
    except (KeyboardInterrupt, Terminated):
        status = Terminated.code
    except Exception:
        if args['--verbose']:
            import traceback
            traceback.print_exc()
        status = EXIT_CODES['othe']
    logger.debug('exit status=%d', status)
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
        return EXIT_CODES['othe']
    return EXIT_CODES['succ']


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
        return EXIT_CODES['othe']
    return EXIT_CODES['succ']


if __name__ == '__main__':
    sys.exit(main())
