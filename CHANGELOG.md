History
-------

**2020-01-16 (0.9.0)**
 - New: option single_instance in job configuration
 - New: logging can be disabled in application or job configuration
 - Add function set_sigterm_handler() to API
 - Upgrade dependency: salmagundi -> 0.11.2
 - Bugfix: error when sending email if file list contained source or target errors

**2020-01-09 (0.8.0)**
 - Emails are now customizable
 - Upgrade dependencies: paramiko -> 2.7.1, salmagundi -> 0.10.0

**2019-12-03 (0.7.5)**
 - Improve documentation
 - Add more examples

**2019-06-12 (0.7.4)**
 - Upgrade dependency: paramiko 2.4.2 -> 2.5.0

**2019-02-21 (0.7.3)**
 - Improve email handling code
 - Improve API

**2019-02-03 (0.7.2)**
 - Fix dependency (wrong salmagundi version in setup.cfg)

**2019-02-03 (0.7.1)**
 - Bugfix: subpackage data was not included

**2019-02-03 (0.7.0)**
 - Re-implementation of configuration handling
 - Changes in API
 - Minor changes in job and host configurations

**2019-01-08 (0.6.0)**
 - Support ECDSA and Ed25519 for SFTP authentication keys
 - Change SFTP authentication key configuration
 - Remove host configurations from job configuration files

**2018-12-16 (0.5.4)**
 - Improve usage message and documentation

**2018-09-24 (0.5.3)**
 - Some minor corrections
 - Improve API

**2018-09-20 (0.5.1)**
 - Bugfix: When using the API in a script only one SFTP transfer succeeded and the others failed.

**2018-09-04 (0.5.0)**
 - First public release.
