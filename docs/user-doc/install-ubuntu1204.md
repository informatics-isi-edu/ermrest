
# Installing (Ubuntu 12.04)

1. Enable upstream Postgresql repo following [Apt instructions from Postgresql Wiki](http://wiki.postgresql.org/wiki/Apt).
2. Set the `PLATFORM=ubuntu1204` variable for our Makefiles
3. Do normal installation sequence as `root` user
  - `sudo su -`
  - `cd ~devuser/webauthn`
  - `make install PLATFORM=ubuntu1204`
  - `cd ~devuser/ermrest`
  - `make predeploy PLATFORM=ubuntu1204`
  - `make install PLATFORM=ubuntu1204`
  - `make deploy PLATFORM=ubuntu1204`
4. Enable SSL

## HTTPS Notes

1. The web service is called `apache2` and some file locations and operating details differ from that documented for CentOS.
2. The ermrest `predeploy` make target will run `apt-get` to install dependencies including self-signed certificates for apache.
3. The HTTPS service needs to be enabled explicitly, unlike on CentOS
  - `a2enmod ssl`
  - `s2ensite default-ssl`
  - `service apache2 reload`

## Postgres Notes

Content of `/etc/apt/sources.list.d/pgdg.list`:
```
deb http://apt.postgresql.org/pub/repos/apt/ precise-pgdg main
```

We try to install `postgresql-9.4` in our `predeploy` target, but you 
may want to install it sooner to make sure no other implicit postgres 
dependencies pull in an older, incompatible postgres from Ubuntu 12.04 itself.

