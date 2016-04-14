# ERMrest Installation (CentOS 6)

This guide provides instructions for installing ERMrest on the CentOS 6.x Linux
distribution.

## Prerequisites

ERMrest depends on the following prerequisites:
- CentOS 6.x
- EPEL 6 repository
- PostgreSQL 9.2 or above
- WebAuthn

This guide assumes only that you have installed the CentOS 6.x Linux
distribution. See http://www.centos.org for more information.

In this document, commands that begin with `#` should be run as root or with
super user privileges (`sudo`). Commands that begin with `$` may be run as a
normal user.

### Extended Packages for Enterprise Linux (EPEL)

Run the following commands to install the EPEL repository.

For CentOS 6 use:

```
# rsync -v rsync://mirrors.kernel.org/fedora-epel/6/x86_64/epel-release*.rpm .
# yum localinstall epel-release*.rpm
```

For CentOS 7 use:

```
# rsync -v rsync://mirrors.kernel.org/fedora-epel/7/x86_64/e/epel-release*.rpm .
# yum localinstall epel-release*.rpm
```

### Workaround HTTPD errors related to mod_wsgi not finding its sockets

With older deployments, you may encounter errors in the
Apache SSL server log similar to `Unable to connect to WSGI daemon
process on '/var/run/wsgi/wsgi.1331.1.1.sock'`.

The solution is to use `/var/run/httpd/wsgi` as the WSGI socket
directory in the `/etc/httpd/conf.d/wsgi_ermrest.conf` file. This
location will have appropriate SE-Linux context to work with the
default Apache httpd sandboxing.

### PostgreSQL 9.2 or above

PostgreSQL must be installed and configured to operate within the [SE-Linux]
access control mechanism.

1. Install the PostgreSQL 9.4 repository

   For CentOS 6 use:

   ```
   # yum install http://yum.postgresql.org/9.4/redhat/rhel-6-x86_64/pgdg-redhat94-9.4-1.noarch.rpm
   ```

   For CentOS 7 use:

   ```
   # yum install http://yum.postgresql.org/9.4/redhat/rhel-7-x86_64/pgdg-centos94-9.4-1.noarch.rpm
   ```

2. Install the required packages. You may first want to uninstall any
   conflicting packages if you had default PostgreSQL packages installed with
   your base CentOS installation.

   ```
   # yum install policycoreutils-python
   # yum erase postgresql{,-server}
   # yum install postgresql94{,-server,-docs,-contrib}
   ```

3. Add local labeling rules to [SE-Linux] since the files are not where CentOS
   expects them.

   For CentOS 6 use:

   ```
   # semanage fcontext --add --ftype "" --type postgresql_tmp_t "/tmp/\.s\.PGSQL\.[0-9]+.*"
   # semanage fcontext --add --ftype "" --type postgresql_exec_t "/usr/pgsql-9\.[0-9]/bin/(initdb|postgres)"
   # semanage fcontext --add --ftype "" --type postgresql_log_t "/var/lib/pgsql/9\.[0-9]/pgstartup\.log"
   # semanage fcontext --add --ftype "" --type postgresql_db_t "/var/lib/pgsql/9\.[0-9]/data(/.*)?"
   # restorecon -rv /var/lib/pgsql/
   # restorecon -rv /usr/pgsql-9.*
   ```

  For CentOS 7 use:

  ```
  # semanage fcontext --add --type postgresql_tmp_t "/tmp/\.s\.PGSQL\.[0-9]+.*"
  # semanage fcontext --add --type postgresql_exec_t "/usr/pgsql-9\.[0-9]/bin/(initdb|postgres)"
  # semanage fcontext --add --type postgresql_log_t "/var/lib/pgsql/9\.[0-9]/pgstartup\.log"
  # semanage fcontext --add --type postgresql_db_t "/var/lib/pgsql/9\.[0-9]/data(/.*)?"
  # restorecon -rv /var/lib/pgsql/
  # restorecon -rv /usr/pgsql-9.*
  ```

4. Initialize and enable the `postgresql` service.

   For CentOS 6 use:

   ```
   # service postgresql-9.4 initdb
   # service postgresql-9.4 start
   # chkconfig postgresql-9.4 on
   ```

   For CentOS 7 use:

   ```
   # /usr/pgsql-9.4/bin/postgresql94-setup initdb
   # systemctl enable postgresql-9.4.service
   # systemctl start postgresql-9.4.service
   ```

5. Verify that postmaster is running under the right SE-Linux context
   `postgresql_t` (though process IDs will vary of course).

   For CentOS 6 use:

   ```
   # ps -eZ | grep postmaster
   unconfined_u:system_r:postgresql_t:s0 2278 ?   00:00:00 postmaster
   unconfined_u:system_r:postgresql_t:s0 2280 ?   00:00:00 postmaster
   unconfined_u:system_r:postgresql_t:s0 2282 ?   00:00:00 postmaster
   unconfined_u:system_r:postgresql_t:s0 2283 ?   00:00:00 postmaster
   unconfined_u:system_r:postgresql_t:s0 2284 ?   00:00:00 postmaster
   unconfined_u:system_r:postgresql_t:s0 2285 ?   00:00:00 postmaster
   unconfined_u:system_r:postgresql_t:s0 2286 ?   00:00:00 postmaster
   ```

   For CentOS 7 use:

   ```
   # ps -eZ | grep postgres
   system_u:system_r:unconfined_service_t:s0 22188 ? 00:00:00 postgres
   system_u:system_r:unconfined_service_t:s0 22189 ? 00:00:00 postgres
   system_u:system_r:unconfined_service_t:s0 22191 ? 00:00:00 postgres
   system_u:system_r:unconfined_service_t:s0 22192 ? 00:00:00 postgres
   system_u:system_r:unconfined_service_t:s0 22193 ? 00:00:00 postgres
   system_u:system_r:unconfined_service_t:s0 22194 ? 00:00:00 postgres
   system_u:system_r:unconfined_service_t:s0 22195 ? 00:00:00 postgres
   ```

6. Permit network connections to the database service.

   ```
   # setsebool -P httpd_can_network_connect_db=1
   ```

### WebAuthn

[WebAuthn] is a library that provides a small extension to the lightweight
[web.py] web framework. It must be installed first before installing ERMrest.

1. Download WebAuthn.

   ```
   $ git clone https://github.com/informatics-isi-edu/webauthn.git webauthn
   ```

2. From the WebAuthn source directory, run the installation script.

   ```
   # cd webauthn
   # make install
   ```

   This will install the WebAuthn Python module under
   `/usr/lib/python2*/site-packages/webauthn2/`.

   **NOTE**: the above step will partially fail on CentOS 7. The python-webpy
   package is not yet available on CentOS 7. It may be installed using:

   ```
   # easy_install web.py
   ```

## Installing ERMrest

After installing the prerequisite, you are ready to install ERMrest.

1. Download ERMrest.

   ```
   $ git clone https://github.com/informatics-isi-edu/ermrest.git ermrest
   ```

2. From the ERMrest source directory, run the installation script.

   ```
   # cd ermrest
   # make install [PLATFORM=centos7]
   ```

   The install script:
   - installs the ERMrest Python module under
     `/usr/lib/python2*/site-packages/ermrest/`
   - installs command-line interface (CLI) tools under `/usr/sbin`.


3. From the same directory, run the deployment script.

   ```
   # make deploy [PLATFORM=centos7]
   ```

   The deployment script:
   - attempts a `yum install` of essential dependencies
   - runs install target
   - prepares service environment (makes ERMrest daemon user, creates directories)
   - creates and initializes ERMrest-specific database, owned by daemon user
   - creates default service config as `/etc/httpd/conf.d/zz_ermrest.conf`.

   CentOS notes:
   - you may need to uninstall mod_python to use mod_wsgi
   - you may need to uncomment `/etc/httpd/conf.d/wsgi.conf` load module.


4. Restart the Apache httpd service

   ```
   # service httpd restart
   ```

## Updating ERMrest

Changes to code in your working copy can be quickly tested with the following
commands.

```
# cd path/to/ermrest
# make install [PLATFORM=centos7]
```

The script updates files under `/usr/lib/python2*/site-packages/ermrest` and
`/var/www/html/ermrest`. It then restarts `httpd` to force reload of all service
code.

## Setup User Accounts

The WebAuthn framework allows for pluggable security providers for
authenticating clients. The simplest configuration assumes [basic authentication]
against an internal database of usernames and passwords and attributes.

1. Switch to the `ermrest` user in order to perform the  configuration steps.

   ```
   # su - ermrest
   ```

2. Setup an administrator account.

   ```
   $ ermrest-webauthn2-manage adduser root
   $ ermrest-webauthn2-manage addattr admin
   $ ermrest-webauthn2-manage assign root admin
   $ ermrest-webauthn2-manage passwd root 'your password here'
   ```

   The `admin` attribute has special meaning only because it appears in
   `~ermrest/ermrest-config.json` in some ACLs.

3. Setup a user account.

   ```
   $ ermrest-webauthn2-manage adduser myuser
   $ ermrest-webauthn2-manage passwd myuser 'your password here'
   ```

## Create Your First Catalog

A quick sanity check of the above configuration is to login to ERMrest, create
a catalog, and read its meta properties. The following commands can be run as
any local user.

1. Login to ERMrest using an 'admin' account previously created with
   `ermrest-webauthn-manage`. Do not include the single quotes in the parameter.

   ```
   $ curl -k -c cookie -d username=root -d password='your password here' \
   > https://localhost/ermrest/authn/session
   ```

2. Create a catalog.

   ```
   $ curl -k -b cookie -XPOST https://localhost/ermrest/catalog/
   ```

3. Inspect the catalog metadata. (Readable indentation added here.)

   ```
   $ curl -k -b cookie -H "Accept: application/json" \
   > https://localhost/ermrest/catalog/1
   {
     "meta": [
       {"k": "owner", "v": "testuser"},
       {"k": "write_user", "v": "testuser"},
       {"k": "read_user", "v": "testuser"},
       {"k": "schema_write_user", "v": "testuser"},
       {"k": "content_read_user", "v": "testuser"},
       {"k": "content_write_user", "v": "testuser"}],
     "id": "1"
   }
   ```

4. Inspect the catalog schema.

   ```
   $ curl -k -b cookie -H "Accept: application/json" \
   > https://localhost/ermrest/catalog/1/schema
   {
      "schemas": {
      ...
   }
   ```

## Firewall

You will need to edit your firewall rules if you want to access the ERMrest
service from remote hosts. There are multiple ways to do this.

https://fedoraproject.org/wiki/How_to_edit_iptables_rules

The `system-config-firewall-tui` is one simple utility for making basic
modifications to a CentOS 6 firewall configuration.

https://fedoraproject.org/wiki/How_to_edit_iptables_rules#TUI_.28text-based_user_interface.29


[Basic authentication]: https://en.wikipedia.org/wiki/Basic_access_authentication (Basic authentication)
[SE-Linux]: http://wiki.centos.org/HowTos/SELinux (Security-Enhanced Linux)
[WebAuthn]: https://github.com/informatics-isi-edu/webauthn (WebAuthn)
[web.py]:   http://webpy.org (web.py)
