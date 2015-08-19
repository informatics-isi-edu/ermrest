# arguments that can be set via make target params or environment?
PLATFORM=centos6

INSTALLSVC=ermrest

PGADMIN=postgres
DAEMONUSER=$(INSTALLSVC)
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

# bump the revision when changing predeploy side-effects
PREDEPLOY=$(VARLIBDIR)/predeploy.r5055
DEPLOYLOCK=$(VARLIBDIR)/deploy.lock

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
                LOGROTATECONFDIR=$(LOGROTATECONFDIR)

# make this the default target
install: $(PREDEPLOY) $(INSTALL_FILES)
	make httpd_restart

uninstall: force
	rm -f $(INSTALL_FILES)
	rmdir --ignore-fail-on-non-empty -p $(INSTALL_DIRS)


# get platform-specific rules (e.g. actual predeploy recipe)
include config/make-rules-$(PLATFORM)

# get sub-directory rules (e.g. extra modular targets)
include sbin/makefile-rules
include ermrest/makefile-rules
include test/makefile-rules

predeploy: $(PREDEPLOY)

unpredeploy: force
	rm -f $(PREDEPLOY)

$(DEPLOYLOCK): predeploy install $(VARLIBDIR)
	$(SBINDIR)/ermrest-deploy

deploy: $(DEPLOYLOCK)

undeploy: force $(SBINDIR)/ermrest-undeploy
	$(SBINDIR)/ermrest-undeploy || true

restart: force install
	make httpd_restart

clean: force
	rm -f $(CLEAN_FILES)

cleanhost: force undeploy uninstall

force:

