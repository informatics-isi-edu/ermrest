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

WSGISOCKETDIR=$(shell dirname "$(WSGISOCKETPREFIX)")

# catalog of all the files/dirs we manage via make targets below

# these will be augmented by sub-directory variable defs
INSTALL_FILES=
INSTALL_DIRS=
EDIT_FILES=Makefile install-script
CLEAN_FILES= $(EDIT_FILES:%=%~)

# get sub-directory variables (e.g. modular file groups)
include sbin/makefile-vars
include ermrest/makefile-vars
include ermrest/exception/makefile-vars
include ermrest/ermpath/makefile-vars
include ermrest/model/makefile-vars
include ermrest/url/makefile-vars
include ermrest/url/ast/makefile-vars
include ermrest/url/ast/data/makefile-vars
include test/makefile-vars

# turn off annoying built-ins
.SUFFIXES:

INSTALL_SCRIPT=./install-script -R \
                SBINDIR=$(SBINDIR) \
                LIBEXECDIR=$(LIBEXECDIR) \
                SHAREDIR=$(SHAREDIR) \
                VARLIBDIR=$(VARLIBDIR) \
                HTTPCONFDIR=$(HTTPCONFDIR) \
                HTMLDIR=$(HTMLDIR) \
                LOGFACILITY=$(LOGFACILITY) \
                LOGDIR=$(LOGDIR) \
                SYSLOGCONF=$(SYSLOGCONF) \
                LOGROTATECONFDIR=$(LOGROTATECONFDIR) \
		SU=$(SU)

# make this the default target
install: $(INSTALL_FILES)

uninstall: force
	rm -f $(INSTALL_FILES)
	rmdir --ignore-fail-on-non-empty -p $(INSTALL_DIRS)


# get platform-specific rules (e.g. actual predeploy recipe)
include config/make-rules-$(PLATFORM)

# get sub-directory rules (e.g. extra modular targets)
include sbin/makefile-rules
include ermrest/makefile-rules
include test/makefile-rules

deploy: force install
	$(SBINDIR)/ermrest-deploy HTTPCONFDIR=$(HTTPCONFDIR)

undeploy: force $(SBINDIR)/ermrest-undeploy
	$(SBINDIR)/ermrest-undeploy || true

restart: force install
	make httpd_restart

clean: force
	rm -f $(CLEAN_FILES)

cleanhost: force undeploy uninstall

force:

