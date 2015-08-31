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
LOG=${LOG:-/dev/stderr}             # Log message file
DEBUG=${DEBUG:-0}                   # Debug flag
VERBOSE=${VERBOSE:-}                # Verbose flag
DBNPREFIX="_ermrest_test_"          # DB name prefix
NUMTESTS=3                          # Total num of tests

function usage {
    cat <<EOF
usage: `basename "$0"`

Runs test suite for the 'ermrest-registry-test' command-line utility.

A successful run will exit with status 0 and an empty standard output.

A failure will exit with non-zero status and a non-empty standard output.

Setting VERBOSE=true will include full per-test information on
standard output for successes as well as failures. VERBOSE=brief will
output a single line per successful test.

Diagnostics may be printed to standard error regardless of success or
failure.

This script will not execute if any catalogs already exist in the 
registry. The execution of this script will purge all catalogs from the
database server.
EOF
}

# Prints info message
function info {
    printf "$1" >${LOG}
}

# Prints error message
function error {
    printf "$1" >&2
}

# Create test database
#   dbn : name of the database
function create_db {
    local dbn=${1}
    runuser -c "createdb --maintenance-db=\"${MASTEDB}\" \"${dbn}\"" - "${DAEMONUSER}"
    return $?
}

# Add a catalog entry to the simple_registry
#   dbn : name of the database
#   when : postgres timestamptz of deleted_on (default = NULL)
function register_catalog {
    local dbn=${1}
    local when=${2-NULL}
    runuser -c "psql -q \"${MASTERDB}\" >/dev/null" - "${DAEMONUSER}" <<EOF
INSERT INTO ermrest.simple_registry ("descriptor", "deleted_on")
VALUES ('{ "dbname": "${dbn}" }', ${when})
RETURNING "id";
EOF
}

# Output the count of catalogs in registry
function count_catalogs {
    runuser -c "psql -A -t -q -c \"select count(*) from ermrest.simple_registry\" ermrest" - ermrest
}

# Setup a few catalogs (with dbs) for different conditions
function setup {
    # create databases
    for i in $(seq $NUMTESTS); do
        local dbn=$DBNPREFIX$i

        create_db "$dbn"
        if [ $? -ne 0 ]; then
            error "failed to create database $dbn"
            return $?
        fi

        register_catalog "$dbn" "CURRENT_TIMESTAMP"
        if [ $? -ne 0 ]; then
            error "failed to register $dbn"
            return $?
        fi

    done
}

# Clean up all test databases and catalog entries
function teardown {
    # drop all test dbs
    for i in $(seq $NUMTESTS); do
        local dbn=$DBNPREFIX$i
        runuser -c "dropdb --if-exists --maintenance-db=\"${MASTEDB}\" \"${dbn}\" 2>/dev/null" - "${DAEMONUSER}"
    done
    # delete all registry entries
    runuser -c "psql -A -t -q -c \"delete from ermrest.simple_registry\" ermrest 2>/dev/null" - ermrest
}

# Make sure preconditions are satisfied before running tests
#  ! Registry must be empty
function preconditions {
    count=$(count_catalogs)
    if [ "$count" != "0" ]; then
        error "found $count catalogs in registry. Must be empty.\n"
        usage
        return 1
    fi
}

function tests {
    tests=$((tests + 1))
    info "test: purge of deleted catalogs ... "
    ermrest-registry-purge -q
    count=$(count_catalogs)
    expected=0
    if [ $? -ne 0 ]; then
        info "failed: purge script returned error\n"
        failed=$((failed + 1))
    elif [ "$count" != "$expected" ]; then
        info "failed: count=${count}, but expected=${expected}\n"
        failed=$((failed + 1))
    else
        info "succeeded\n"
    fi
}

function suite {
    tests=0
    failed=0
    preconditions
    if [ $? -ne 0 ]; then
        return -1
    fi
    setup
    if [ $? -eq 0 ]; then
        tests
    fi
    teardown
    return $failed
}

suite
exit $?
