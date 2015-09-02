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

POSTGRES="${POSTGRES:-postgres}"    # Postgres daemon user
DAEMONUSER="${DAEMONUSER:-ermrest}" # Unix and DB user name
MASTERDB="${MASTEDB:-$DAEMONUSER}"  # Master DB name
DBNPREFIX="_ermrest_test_"          # DB name prefix
OUT=/dev/stdout                     # Standard output
ERR=/dev/stderr                     # Error output
if [[ "$QUIET" = "true" ]]; then
    ERR=/dev/null
    OUT=/dev/null
fi
BRIEF=/dev/null                     # Brief verbosity messages file
FULL=/dev/null                      # Full verbosity messages file
if [[ "$VERBOSE" == "true" ]]; then
    BRIEF=${ERR}
    FULL=${ERR}
elif [[ "$VERBOSE" == "brief" ]]; then
    BRIEF=${ERR}
fi

# Define the tests that will be run
#   0 = purge based on a time interval
TESTS[0]="CURRENT_TIMESTAMP - interval '1 week'"
#   1 = purge without regard to time
TESTS[1]="CURRENT_TIMESTAMP"
#   2 = purge all 
TESTS[2]="NULL"

function usage {
    cat >${ERR} <<EOF
usage: `basename "$0"`

Runs test suite for the 'ermrest-registry-test' command-line utility.

A successful run will exit with status 0 and an empty standard output.

A failure will exit with non-zero status and a non-empty standard output.

Setting VERBOSE=true will include full per-test brief information on
standard output for successes as well as failures. VERBOSE=brief will
output a single line per successful test.

Diagnostics may be printed to standard error regardless of success or
failure.

Setting QUIET=true will silence all output and overrides VERBOSE.

This script will not execute if any catalogs already exist in the 
registry. The execution of this script will purge all catalogs from the
database server.
EOF
}

# Prints test failure message
function failed {
    echo "FAILED: $1" >${OUT}
}

# Prints brief verbosity message
function info {
    echo "$1" >${BRIEF}
}

# Prints full verbosity message
function verbose {
    echo "$1" >${FULL}
}

# Create test database
#   dbn : name of the database
function create_db {
    local dbn=${1}
    verbose "Creating database ${dbn}"
    runuser -c "createdb --maintenance-db=\"${MASTERDB}\" \"${dbn}\"" - "${DAEMONUSER}" 2>${FULL}
    return $?
}

# Add a catalog entry to the simple_registry
#   dbn: name of the database
#   when: postgres timestamptz of deleted_on (default = NULL)
function register_catalog {
    local dbn=${1}
    local when=${2-NULL}
    verbose "Registering catalog for ${dbn} with deleted_on = ${when}"
    runuser -c "psql -q \"${MASTERDB}\"" - "${DAEMONUSER}" 2>${FULL} <<EOF
INSERT INTO ermrest.simple_registry ("descriptor", "deleted_on")
VALUES ('{ "dbname": "${dbn}" }', ${when});
EOF
}

# Output the count of catalogs in registry
function count_catalogs {
    runuser -c "psql -A -t -q -c \"select count(*) from ermrest.simple_registry\" ermrest" - ermrest
}

# Setup a few catalogs (with dbs) for different conditions
function setup {
    verbose "Setting up test environment"
    for i in ${!TESTS[*]}; do
        local dbn=$DBNPREFIX$i

        create_db "$dbn"
        if [ $? -ne 0 ]; then
            failed "could not create database $dbn"
            return $?
        fi

        register_catalog "$dbn" "${TESTS[$i]}"
        if [ $? -ne 0 ]; then
            failed "could not register catalog for $dbn"
            return $?
        fi
    done
}

# Clean up all test databases and catalog entries
function teardown {
    verbose "Tearing down test environment"
    # drop all test dbs
    for i in ${!TESTS[*]}; do
        local dbn=$DBNPREFIX$i
        verbose "Dropping database ${dbn}, if exists"
        runuser -c "dropdb --if-exists --maintenance-db=\"${MASTERDB}\" \"${dbn}\"" - "${DAEMONUSER}" 2>${FULL}
    done
    # delete all registry entries
    verbose "Deleting all entries from simple_registry table"
    runuser -c "psql -A -t -q -c \"delete from ermrest.simple_registry\" ermrest" - ermrest 2>${FULL}
}

# Make sure preconditions are satisfied before running tests
#  ! Registry must be empty
function preconditions {
    count=$(count_catalogs)
    if [[ $count -ne 0 ]]; then
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

    num_tests=$((num_tests + 1))
    eval "${cmd}" 2>${ERR} 1>&2
    _rc=$?
    if [[ $_rc -ne 0 ]]; then
        failed "\"$text\" exited with $_rc"
        num_fails=$((num_fails + 1))
    else
        count=$(count_catalogs)
        if [[ $count -ne $expect ]]; then
            failed "\"$text\" expected $expect but found $count"
            num_fails=$((num_fails + 1))
        else
            info "\"$text\" succeeded"
        fi
    fi
}

# Test suite
function suite {
    num_tests=0
    num_fails=0

    preconditions
    if [[ $? -ne 0 ]]; then
        return 1
    fi

    setup
    if [[ $? -eq 0 ]]; then
      verbose "Running test suite"
      dotest "Purge catalogs deleted >= 1 week ago" "ermrest-registry-purge -q -i '1 week'" 2
      dotest "Purge catalogs deleted anytime" "ermrest-registry-purge -q" 1
      dotest "Purge all catalogs" "ermrest-registry-purge -q -a" 0
    fi
    teardown

    if [[ ${num_fails} -gt 0 ]]; then
        failed "${num_fails} of ${num_tests} tests"
    else
        info "ALL ${num_tests} tests succeeded"
    fi

    return $num_fails
}

suite
exit $?
