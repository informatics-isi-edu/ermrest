#!/bin/bash

# 
# Copyright 2012-2015 University of Southern California
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#    http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

PROG=$(basename $0)                 # Program name
LOG=${PROG}.log                     # Log file
DAEMONUSER="${DAEMONUSER:-ermrestddl}" # Unix and DB user name
MASTERDB="${MASTEDB:-ermrest}"      # Master DB name
DBNPREFIX="_${MASTERDB}_test"       # DB name prefix

# Define the tests that will be run:
#   purge based on a time interval
TESTS[0]="CURRENT_TIMESTAMP - interval '1 week'"
#   purge based on a time interval (used by the archive test case)
TESTS[1]="CURRENT_TIMESTAMP - interval '1 day'"
#   purge without regard to time
TESTS[2]="CURRENT_TIMESTAMP"
#   purge all
TESTS[3]="NULL"

function usage {
    cat >&2 <<EOF
usage: ${PROG}

Runs test suite for the 'ermrest-registry-purge' command-line utility.

A successful run will exit with status 0 and an empty standard output.

A failure will exit with non-zero status and a non-empty standard output.

Setting VERBOSE=true will include full per-test brief information on
standard output for successes as well as failures. VERBOSE=brief will
output a single line per successful test.

Diagnostics may be printed to standard error regardless of success or
failure.

This script will not execute if any catalogs already exist in the 
registry. The execution of this script will purge all catalogs from the
database server.
EOF
}

# Prints test failure message
function failed {
    echo "FAILED: $1"
}

# Prints brief verbosity message
function info {
    if [ "${VERBOSE}" == "brief" -o "${VERBOSE}" == "true" ]
    then
        echo $1
    fi
}

# Prints full verbosity message
function verbose {
    if [ "${VERBOSE}" == "true" ]
    then
        echo $1
    fi
}

# Add a catalog entry to the simple_registry
#   dbn: name of the database
#   when: postgres timestamptz of deleted_on (default = NULL)
function register_catalog {
    local dbn=$1
    local when=$2
    verbose "Registering catalog for ${dbn} with deleted_on = ${when}"
    su -c "psql -q \"${MASTERDB}\"" - "${DAEMONUSER}" >>${LOG} 2>&1 <<EOF
INSERT INTO ermrest.simple_registry ("descriptor", "deleted_on")
VALUES ('{ "dbname": "${dbn}" }', ${when});
EOF
}

# Output the count of catalogs in registry
function count_catalogs {
    su -c "psql -A -t -q -c \"select count(*) from ermrest.simple_registry\" ${MASTERDB}" - "${DAEMONUSER}"
}

# Setup a few catalogs (with dbs) for different conditions
function setup {
    verbose "Setting up test environment"

    for i in ${!TESTS[*]}
    do
        local dbn="${DBNPREFIX}_${i}"

        if ! su -c "createdb \"${dbn}\"" - "${DAEMONUSER}"
        then
            failed "could not create database $dbn"
            return 1
        fi

        if ! register_catalog "$dbn" "${TESTS[$i]}"
        then
            failed "could not register catalog for $dbn"
	    return 1
        fi
    done

    archive_dir=$(mktemp -d "/tmp/${PROG}.XXXXX")
    if ! chown ${DAEMONUSER}:${DAEMONUSER} ${archive_dir}
    then
        failed "Failed to create and chown archive directory ${archive_dir}"
        return 1
    else
        verbose "Created archive directory ${archive_dir}"
    fi
}

# Clean up all test databases and catalog entries
function teardown {
    verbose "Tearing down test environment"
    # drop all test dbs
    for i in ${!TESTS[*]}
    do
        local dbn="${DBNPREFIX}_${i}"
        verbose "Dropping database ${dbn}, if exists"
        su -c "dropdb --if-exists \"${dbn}\"" - "${DAEMONUSER}" >>${LOG} 2>&1
    done
    # delete all registry entries
    verbose "Deleting all entries from simple_registry table"
    su -c "psql -A -t -q -c \"delete from ermrest.simple_registry\" \"${MASTERDB}\"" - "${DAEMONUSER}" >>${LOG} 2>&1
    # cleanup archive directory
    rm -rf "${archive_dir}" >>${LOG} 2>&1
}

# Make sure preconditions are satisfied before running tests
#  ! Registry must be empty
function preconditions {
    count=$(count_catalogs)
    if [ $count -ne 0 ]
    then
        failed "found $count catalogs in registry. Must be empty."
        usage
        return 1
    fi
}

# Run test
#   text: friendly text for reporting
#   cmd: command to run
#   expect: expected count of catalogs after test
function dotest {
    local text="$1"
    local cmd="$2"
    local expect=$3
    local _rc=0
    num_tests=$((${num_tests} + 1))

    su -c "${cmd}" - ${DAEMONUSER} >>${LOG} 2>&1
    _rc=$?
    if [ ${_rc} -ne 0 ]
    then
        failed "\"$text\" exited with ${_rc}"
        num_fails=$((${num_fails} + 1))
    else
        count=$(count_catalogs)
        if [ $count -ne $expect ]
        then
            failed "\"$text\" expected $expect but found $count"
            num_fails=$((${num_fails} + 1))
        else
            info "\"$text\" succeeded"
        fi
    fi
}

# Test suite
function suite {
    >${LOG}
    num_tests=0
    num_fails=0

    if ! preconditions
    then
        return 1
    fi

    if setup
    then
        verbose "Running test suite"
        dotest "Purge catalogs deleted >= 1 week ago" "ermrest-registry-purge -q -i '1 week'" 3
        dotest "Purge and archive catalogs deleted >= 1 day ago" "ermrest-registry-purge -q -i '1 day' -z \"${archive_dir}\"" 2
        dotest "Purge catalogs deleted anytime" "ermrest-registry-purge -q" 1
        dotest "Purge all catalogs" "ermrest-registry-purge -q -a" 0
    else
        num_fails=$(( ${num_fails} + 1 ))
    fi
    teardown

    if [ ${num_fails} -gt 0 ]
    then
        cat ${LOG}
        failed "${num_fails} of ${num_tests} tests"
    else
        info "ALL ${num_tests} tests succeeded"
    fi

    return ${num_fails}
}

suite
