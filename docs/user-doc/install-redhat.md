# Installing (Red Hat derivatives)

This guide provides instructions for installing ERMrest on a Linux
distribution from the Red Hat Linux family. We recommend using a
current Fedora release to get a reasonably modern Apache HTTPD which
supports the HTTP/2 protocol. Installation on CentOS 7 is similar but
requires the additional EPEL repository to add third-party
dependencies included in Fedora but missing from CentOS; in this case,
your server will only support HTTP/1.1.

In all cases, we recommend using the upstream PostgreSQL binary
distribution suitable for your OS, to be sure you have the latest
stable database release for better performance.

## Prerequisites

ERMrest depends on the following prerequisites:

- Currently supported Fedora
- PostgreSQL 10 or above
- WebAuthn

This guide assumes only that you have installed the [Fedora Linux distribution](https://getfedora.org).

In this document, commands that begin with `#` should be run as root or with
super user privileges (`sudo`). Commands that begin with `$` may be run as a
normal user.

### Extended Packages for Enterprise Linux (EPEL)

If you run an enterprise Linux distribution instead of Fedora, you
will also need additional third-party software. For CentOS 7, run the
following commands to install the EPEL repository.

```
# rsync -v rsync://mirrors.kernel.org/fedora-epel/7/x86_64/e/epel-release*.rpm .
# dnf install epel-release*.rpm
```

### PostgreSQL

PostgreSQL must be installed and configured to operate within the
[SE-Linux] access control mechanism.  We recommend using the latest
stable release, i.e. Postgres 10 at time of writing.

1. Install the PostgreSQL 10 repository.

   Check the list of packages for the version of PostgreSQL and your 
   distribution from the list at `http://yum.postgresql.org/`.

   At time of writing, these are the latest packages for stable Fedora and CentOS, respectively:
   
```
# dnf install https://download.postgresql.org/pub/repos/yum/10/fedora/fedora-28-x86_64/pgdg-fedora10-10-4.noarch.rpm
## OR
# dnf install https://download.postgresql.org/pub/repos/yum/10/redhat/rhel-7-x86_64/pgdg-centos10-10-4.noarch.rpm
```

2. Install the required packages. You may first want to uninstall any
   conflicting packages if you had default PostgreSQL packages installed with
   your base CentOS installation.

```
# dnf install policycoreutils-python
# dnf remove postgresql{,-server}
# dnf install postgresql10{,-server,-docs,-contrib}
```

3. Add local labeling rules to [SE-Linux] since the files are not where CentOS
   expects them.

```
# semanage fcontext --add --type postgresql_tmp_t "/tmp/\.s\.PGSQL\.[0-9]+.*"
# semanage fcontext --add --type postgresql_exec_t "/usr/pgsql-[.0-9]+/bin/(initdb|postgres)"
# semanage fcontext --add --type postgresql_log_t "/var/lib/pgsql/[.0-9]+/pgstartup\.log"
# semanage fcontext --add --type postgresql_db_t "/var/lib/pgsql/[.0-9]+/data(/.*)?"
# restorecon -rv /var/lib/pgsql/
# restorecon -rv /usr/pgsql-[.0-9]+
```

4. Initialize and enable the `postgresql` service.

```
# /usr/pgsql-10/bin/postgresql10-setup initdb
# systemctl enable postgresql-10.service
# systemctl start postgresql-10.service
```

5. Verify that postmaster is running under the right SE-Linux context
   `postgresql_t` (though process IDs will vary of course).

```
# ps -Z -U postgres
system_u:system_r:unconfined_service_t:s0 22188 ? 00:00:00 postmaster
system_u:system_r:unconfined_service_t:s0 22189 ? 00:00:00 postmaster
system_u:system_r:unconfined_service_t:s0 22191 ? 00:00:00 postmaster
system_u:system_r:unconfined_service_t:s0 22192 ? 00:00:00 postmaster
system_u:system_r:unconfined_service_t:s0 22193 ? 00:00:00 postmaster
system_u:system_r:unconfined_service_t:s0 22194 ? 00:00:00 postmaster
system_u:system_r:unconfined_service_t:s0 22195 ? 00:00:00 postmaster
```

6. Permit network connections to the database service.

```
# setsebool -P httpd_can_network_connect_db=1
```

### Other Prerequisites

```
# dnf install httpd mod_{ssl,wsgi} python3{,-psycopg2,-setuptools,-ply}
```

Install the web framework

```
# pip3 install flask
```

### WebAuthn

[WebAuthn] is a library that provides a small extension to the
lightweight [web.py] web framework. It must be installed first before
installing ERMrest.

1. Download WebAuthn.

```
$ git clone https://github.com/informatics-isi-edu/webauthn.git webauthn
```

2. From the WebAuthn source directory, run the installation and deployment scripts.

```
# cd webauthn
# make preinstall_centos
# make install
# make deploy
```

   The `preinstall_centos` target attempts to install prerequisites
   for Red Hat family distributions. System administrators may prefer
   to review the Makefile and install packages manually instead.

   This will install the WebAuthn Python module under
   `/usr/local/lib/python3*/site-packages/webauthn2/`. It will also create a
   daemon account `webauthn` and place a default security config under
   `~webauthn/webauthn2_config.json`. A new web service will be
   enabled under `/etc/httpd/conf.d/wsgi_webauthn2.conf`.

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
     `/usr/lib/python3*/site-packages`
   - installs command-line interface (CLI) tools under `/usr/local/bin`.

   Note, the Makefile install target just invokes `python3 ./setup.py install`

3. From the same directory, run the deployment script.

```
# make deploy [PLATFORM=centos7]
```

   The deployment script:
   - runs install target
   - prepares service environment (makes ERMrest daemon user, creates directories)
   - creates and initializes ERMrest-specific database, owned by daemon user
   - creates default Apache httpd integration as `/etc/httpd/conf.d/wsgi_ermrest.conf`.
   - creates default service config as `/home/ermrest/ermrest_config.json`

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
# make deploy
# service httpd restart
```

The `install` target updates files under
`/usr/local/lib/python3*/site-packages/ermrest`.  The `deploy` target runs
idempotent deploy processes which MAY upgrade the database schema in
existing catalogs. For small changes to service code, the `deploy`
target is unnecessary; however, it is safe to always run to be sure
that catalogs are upgraded as necessary to match the newly installed
service code.

You may want to review `ermrest_config.json` and
`wsgi_ermrest.conf` in the installation location for changes. These are
deployed to `/home/ermrest/` and `/etc/httpd/conf.d/`, respectively,
during fresh installs but will not overwrite deployed configurations
during an updating install.

## Change web_authn config

Change the following config file to use different authentication modes:
* /home/webauthn/webauthn2_config.json

```
  "sessionids_provider": "webcookie", 
  "sessionstates_provider": "database", 
  "clients_provider": "database", 
  "attributes_provider": "database", 
  "preauth_provider": "database",
```

For more details, see a [webauthn config example](https://github.com/informatics-isi-edu/webauthn/blob/master/samples/database/webauthn2_config.json).
  
## Setup User Accounts

The WebAuthn framework allows for pluggable security providers for
authenticating clients. The simplest configuration assumes [basic authentication]
against an internal database of usernames and passwords and attributes.

1. Switch to the `webauthn` user in order to perform the  configuration steps.

```
# su - webauthn
```

2. Setup an administrator account.

```
$ webauthn2-manage adduser root
$ webauthn2-manage addattr admin
$ webauthn2-manage assign root admin
$ webauthn2-manage passwd root 'your password here'
```

   The `admin` attribute has special meaning only if it appears in ACLs
   in `~webauthn/webauthn2_config.json` or `~ermrest/ermrest_config.json`.

3. Setup a user account.

```
$ webauthn2-manage adduser myuser
$ webauthn2-manage passwd myuser 'your password here'
```

## Create Your First Catalog

A quick sanity check of the above configuration is to login to ERMrest, create
a catalog, and read its meta properties. The following commands can be run as
any local user.

1. Login to ERMrest using an `admin` account previously created with
   `ermrest-webauthn-manage`. Do not include the single quotes in the parameter. The following script will create a cookie file named `cookie`.

```
$ curl -k -c cookie -d username=testuser -d password='your password here' https://$(hostname)/ermrest/authn/session
```

2. Create a catalog.

```
$ curl -k -b cookie -X POST https://$(hostname)/ermrest/catalog/
```

3. Inspect the catalog metadata. (Readable indentation added here.)

```
$ curl -k -b cookie -H "Accept: application/json" \
> https://$(hostname)/ermrest/catalog/1
{
 "acls": {"owner": ["testuser"]},
 "id": "1"
}
```

4. Inspect the catalog schema.

```
$ curl -k -b cookie -H "Accept: application/json" \
> https://$(hostname)/ermrest/catalog/1/schema
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


[SE-Linux]: http://wiki.centos.org/HowTos/SELinux (Security-Enhanced Linux)
[WebAuthn]: https://github.com/informatics-isi-edu/webauthn (WebAuthn)
