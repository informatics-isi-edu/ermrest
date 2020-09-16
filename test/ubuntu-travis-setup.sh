#!/bin/bash

set -eu

# monkey with ssl.conf for travisci (ubuntu) tests

conf=/etc/apache2/sites-available/default-ssl.conf
pattern="^\([[:space:]]*\)\(ServerAdmin .*\)"
replacement="\1\2"
replacement+="\1\n# ermrest needs this for full test suite"
replacement+="\1\nAllowEncodedSlashes On"

mv -f $conf $conf.orig
sed -e "s|$pattern|$replacement|" \
    < $conf.orig \
    > $conf
chmod u+rw,og=r $conf

