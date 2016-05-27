# ERMrest Installation (CentOS 7)

This guide provides instructions for installing ERMrest on the CentOS 7.x Linux
distribution.

## Prerequisites

ERMrest depends on the following prerequisites:
- CentOS 7.x
- EPEL 7 repository
- PostgreSQL 9.4 or above (note: we recommend latest stable version)
- WebAuthn

This guide assumes only that you have installed the CentOS 7.x Linux
distribution. See http://www.centos.org for more information.

In this document, commands that begin with `#` should be run as root or with
super user privileges (`sudo`). Commands that begin with `$` may be run as a
normal user.

### Extended Packages for Enterprise Linux (EPEL)

Run the following commands to install the EPEL repository.

```
# rsync -v rsync://mirrors.kernel.org/fedora-epel/7/x86_64/e/epel-release*.rpm .
# yum localinstall epel-release*.rpm
```

### PostgreSQL 9.4 or above

PostgreSQL must be installed and configured to operate within the
[SE-Linux] access control mechanism.  We recommend using the latest
stable release, i.e. Postgres 9.5 at time of writing.

1. Install the PostgreSQL 9.x repository

   ```
   # yum install https://download.postgresql.org/pub/repos/yum/9.5/redhat/rhel-7-x86_64/pgdg-centos95-9.5-2.noarch.rpm
   ```

2. Install the required packages. You may first want to uninstall any
   conflicting packages if you had default PostgreSQL packages installed with
   your base CentOS installation.

   ```
   # yum install policycoreutils-python
   # yum erase postgresql{,-server}
   # yum install postgresql95{,-server,-docs,-contrib}
   ```

3. Add local labeling rules to [SE-Linux] since the files are not where CentOS
   expects them.

  ```
  # semanage fcontext --add --type postgresql_tmp_t "/tmp/\.s\.PGSQL\.[0-9]+.*"
  # semanage fcontext --add --type postgresql_exec_t "/usr/pgsql-9\.[0-9]/bin/(initdb|postgres)"
  # semanage fcontext --add --type postgresql_log_t "/var/lib/pgsql/9\.[0-9]/pgstartup\.log"
  # semanage fcontext --add --type postgresql_db_t "/var/lib/pgsql/9\.[0-9]/data(/.*)?"
  # restorecon -rv /var/lib/pgsql/
  # restorecon -rv /usr/pgsql-9.*
  ```

4. Initialize and enable the `postgresql` service.

   ```
   # /usr/pgsql-9.4/bin/postgresql94-setup initdb
   # systemctl enable postgresql-9.4.service
   # systemctl start postgresql-9.4.service
   ```

5. Verify that postmaster is running under the right SE-Linux context
   `postgresql_t` (though process IDs will vary of course).

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

### Other Prerequisites

   ```
   # yum install httpd mod_{ssl,wsgi} python{,-psycopg2,-dateutil,-setuptools,-ply} pytz
   # pip install web.py
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
   - runs install target
   - prepares service environment (makes ERMrest daemon user, creates directories)
   - creates and initializes ERMrest-specific database, owned by daemon user
   - creates default service config as `/etc/httpd/conf.d/wsgi_ermrest.conf`.

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
# service httpd restart
```

The install target updates files under `/usr/lib/python2*/site-packages/ermrest`.

You may want to review `/usr/share/ermrest/ermrest_config.json` and
`/usr/share/ermrest/wsgi_ermrest.conf` for changes, as these are
deployed to `/home/ermrest/` and `/etc/httpd/conf.d/`, respectively,
during fresh installs but will not overwrite deployed configurations
during an updating install.

## Change web_authn config

Change the following config files to use database authentication instead of globus authentication. 
* /home/hatrac/webauthn2_config.json
* /home/ermrest/ermrest_config.json

```
  "sessionids_provider": "webcookie", 
  "sessionstates_provider": "database", 
  "clients_provider": "database", 
  "attributes_provider": "database", 
  "preauth_provider": "database",
```  

See config example [here](https://github.com/informatics-isi-edu/webauthn/blob/master/samples/database/webauthn2_config.json).  
  
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
   `ermrest-webauthn-manage`. Do not include the single quotes in the parameter. The following script will create a cookie file named `cookie`.

   ```
   $ curl -k -c cookie -d username=root -d password='your password here' https://$(hostname)/ermrest/authn/session
   ```

2. Create a catalog.

   ```
   $ curl -k -b cookie -XPOST https://$(hostname)/ermrest/catalog/
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

Normally, you need to expose the HTTPS port (TCP 443) to client
machines. Contact your local system administrator if you need help
accomplishing this.


[Basic authentication]: https://en.wikipedia.org/wiki/Basic_access_authentication (Basic authentication)
[SE-Linux]: http://wiki.centos.org/HowTos/SELinux (Security-Enhanced Linux)
[WebAuthn]: https://github.com/informatics-isi-edu/webauthn (WebAuthn)
[web.py]:   http://webpy.org (web.py)
