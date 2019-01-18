# arguments that can be set via make target params or environment?
PLATFORM=centos7

PGADMIN=postgres
DAEMONUSER=ermrest

# get platform-specific variable bindings
include config/make-vars-$(PLATFORM)

# catalog of all the files/dirs we manage via make targets below

# turn off annoying built-ins
.SUFFIXES:

# make this the default target
install:
	pip3 install --no-deps --upgrade .

# get platform-specific rules (e.g. actual predeploy recipe)
include config/make-rules-$(PLATFORM)

deploy: force install
	$(BINDIR)/ermrest-deploy HTTPCONFDIR=$(HTTPCONFDIR) HTTPDGRP=$(HTTPDGRP)

restart: force install
	make httpd_restart

force:

