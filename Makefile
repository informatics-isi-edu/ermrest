# arguments that can be set via make target params or environment?
PLATFORM=centos7

PGADMIN=postgres
DAEMONUSER=ermrest
USERADD=true
USERDEL=false
CREATEUSER=true
DROPUSER=false
DROPDB=true

# get platform-specific variable bindings
include config/make-vars-$(PLATFORM)

# catalog of all the files/dirs we manage via make targets below

# turn off annoying built-ins
.SUFFIXES:

# make this the default target
install:
	python ./setup.py install

# get platform-specific rules (e.g. actual predeploy recipe)
include config/make-rules-$(PLATFORM)

deploy: force install
	$(BINDIR)/ermrest-deploy HTTPCONFDIR=$(HTTPCONFDIR)

restart: force install
	make httpd_restart

force:

