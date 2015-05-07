#!/bin/bash

# Run basic ERMrest REST API tests 

usage()
{
    cat <<EOF
usage: $0

Runs test against local host (https://$(hostname)/ermrest/).

Uses cookie store named in COOKIES environment ($COOKIES), if
specified.

A successful run will exit with status 0 and an empty standard output.

A failure will exit with status 1 and a non-empty standard output.

Diagnostics may be printed to standard error regardless of success or
failure.  Setting the environment variable VERBOSE=true increases the
amount of diagnostic output.

EOF
}

error()
{
    cat >&2 <<EOF
$0: $*
EOF
    usage >&2
    exit 1
}

RUNKEY=smoketest-$RANDOM
RESPONSE_HEADERS=/tmp/${RUNKEY}-response-headers
RESPONSE_CONTENT=/tmp/${RUNKEY}-response-content
TEST_DATA=/tmp/${RUNKEY}-test-data

cleanup()
{
    rm -f ${RESPONSE_HEADERS} ${RESPONSE_CONTENT} ${TEST_DATA}
    rm -f /tmp/parts-${RUNKEY}*
}

trap cleanup 0

curl_options=(
 -D ${RESPONSE_HEADERS}
 -o ${RESPONSE_CONTENT}
 -s -k
 -w "%{http_code}::%{content_type}::%{size_download}\n"
)

if [[ -n "$COOKIES" ]]
then
    curl_options+=( -b "$COOKIES" -c "$COOKIES" )
fi

mycurl()
{
    touch ${RESPONSE_HEADERS}
    touch ${RESPONSE_CONTENT}
    truncate -s 0 ${RESPONSE_HEADERS}
    truncate -s 0 ${RESPONSE_CONTENT}
    curl "${curl_options[@]}" "$@"
}

NUM_FAILURES=0
NUM_TESTS=0

BASE_URL="https://$(hostname)/ermrest"

dotest()
{
    pattern="$1"
    url="$2"
    shift 2

    printf "%s " "$@" "${BASE_URL}$url" >&2
    summary=$(mycurl "$@" "${BASE_URL}$url")
    printf " -->  %s " "$summary" >&2

    hash1=
    hash2=

    if [[ "$summary" != $pattern ]]
    then
	printf "FAILED.\n" >&2
	cat <<EOF

TEST FAILURE:

Expected result: $pattern
Actual result: $summary

Response headers:
$(cat ${RESPONSE_HEADERS})
Response body:
$(cat ${RESPONSE_CONTENT})

EOF
	NUM_FAILURES=$(( ${NUM_FAILURES} + 1 ))
    else
	printf "OK.\n" >&2
	if [[ "$VERBOSE" = "true" ]]
	then
	    cat >&2 <<EOF
Actual result: $summary

Response headers:
$(cat ${RESPONSE_HEADERS})
Response body:
$(cat ${RESPONSE_CONTENT})

EOF
	fi
    fi

    NUM_TESTS=$(( ${NUM_TESTS} + 1 ))
}

if [[ -z "${TEST_CID}" ]]
then
    ###### setup test catalog
    dotest "201::application/json::*" /catalog -X POST

    cid=$(grep "^Location" ${RESPONSE_HEADERS} | sed -e "s|^Location: /ermrest/catalog/\([0-9]\+\).*|\1|")
    [[ -n "$cid" ]] || error "failed to create catalog, testing aborted."
else
    cid=${TEST_CID}
    DESTROY_CATALOG=false
fi

echo "Using catalog \"${cid}\" for testing." >&2


###### do tests on catalog

dotest "200::application/json::*" /catalog/${cid}/schema
dotest "409::*::*" /catalog/${cid}/schema/public -X POST
dotest "201::*::*" /catalog/${cid}/schema/test1 -X POST
dotest "200::application/json::*" /catalog/${cid}/schema

# create tables using each core column type
ctypes=(
    boolean
    float4
    float8
    int2
    int4
    int8
    text
    timestamptz
    date
    uuid
    interval
    serial2
    serial4
    serial8
)

# use corresponding test values (already url-encoded for simplicity)
cvals=(
    True
    1.0
    1.0
    1
    1
    1
    one
    '2015-03-11T11%3A32%3A56-0700'
    '2015-03-11'
    '2648a44e-c81d-11e4-b6d7-00221930f5cc'
    'P1Y2M3DT4H5M6S'
    1
    1
    1
)

for typeno in "${!ctypes[@]}"
do
    ctype="${ctypes[$typeno]}"
    cval="${cvals[$typeno]}"

    cat > ${TEST_DATA} <<EOF
{
   "kind": "table",
   "schema_name": "test1",
   "table_name": "test_ctype_${ctype}",
   "column_definitions": [ 
      { "type": { "typename": "${ctype}" }, "name": "column1" },
      { "type": { "typename": "text" }, "name": "column2" }
   ],
   "keys": [ { "unique_columns": [ "column1" ] } ]
}
EOF
    # create table with core-typed key column
    dotest "201::*::*" /catalog/${cid}/schema/test1/table -H "Content-Type: application/json" -T ${TEST_DATA} -X POST
    dotest "200::*::*" "/catalog/${cid}/entity/test1:test_ctype_${ctype}"
    dotest "200::application/json::*" /catalog/${cid}/schema/test1/table/test_ctype_${ctype}

    # check that introspected type matches requested type
    dotest "200::application/json::*" /catalog/${cid}/schema/test1/table/test_ctype_${ctype}/column/column1
    if ! grep -q "\"typename\": \"${ctype}\"" ${RESPONSE_CONTENT}
    then
	cat <<EOF	
ERROR: Core type ${ctype} failed to round-trip for est1:test_ctype_${ctype}:column1

$(cat ${RESPONSE_CONTENT})
EOF
        NUM_FAILURES=$(( ${NUM_FAILURES} + 1 ))
    fi
    NUM_TESTS=$(( ${NUM_TESTS} + 1 ))

    # test handling of column-typed literals in filters
    dotest "200::application/json::*" "/catalog/${cid}/entity/test1:test_ctype_${ctype}/column1=${cval}"

    # test insertion of rows with server-generated serial ID types
    if [[ "$ctype" == serial* ]]
    then
	# NOTE: currently ermrest chokes on a null value for column1, so dummy value "1" is used instead... need to investigate further
	cat > ${TEST_DATA} <<EOF
column1,column2
1,value1
1,value1
1,value2
EOF
	dotest "200::*::*" "/catalog/${cid}/entity/test1:test_ctype_${ctype}?defaults=column1" -H "Content-Type: text/csv" -T ${TEST_DATA} -X POST
	dotest "200::text/csv::*" "/catalog/${cid}/entity/test1:test_ctype_${ctype}" -H "Accept: text/csv"
	dotest "200::application/json::*" "/catalog/${cid}/entity/test1:test_ctype_${ctype}"
    fi

    # drop table
    dotest "204::*::*" /catalog/${cid}/schema/test1/table/test_ctype_${ctype} -X DELETE
done

# create linked tables for basic tests
cat > ${TEST_DATA} <<EOF
{
   "kind": "table",
   "schema_name": "test1",
   "table_name": "test_level1",
   "column_definitions": [ 
      { "type": { "typename": "int8" }, "name": "id" },
      { "type": { "typename": "text" }, "name": "name" }
   ],
   "keys": [ { "unique_columns": [ "id" ] } ]
}
EOF
dotest "201::*::*" /catalog/${cid}/schema/test1/table -H "Content-Type: application/json" -T ${TEST_DATA} -X POST
dotest "200::*::*" "/catalog/${cid}/entity/test1:test_level1"

cat > ${TEST_DATA} <<EOF
id,name
1,foo
2,bar
3,baz
EOF
dotest "200::*::*" "/catalog/${cid}/entity/test1:test_level1" -H "Content-Type: text/csv" -T ${TEST_DATA} -X POST

cat > ${TEST_DATA} <<EOF
{
   "kind": "table",
   "schema_name": "test1",
   "table_name": "test_level2",
   "column_definitions": [ 
      { "type": { "typename": "int8" }, "name": "id" },
      { "type": { "typename": "int8" }, "name": "level1_id"},
      { "type": { "typename": "text" }, "name": "name" }
   ],
   "keys": [ { "unique_columns": [ "id" ] } ],
   "foreign_keys": [
      { 
        "foreign_key_columns": [{"schema_name": "test1", "table_name": "test_level2", "column_name": "level1_id"}],
        "referenced_columns": [{"schema_name": "test1", "table_name": "test_level1", "column_name": "id"}]
      }
   ]
}
EOF
dotest "201::*::*" /catalog/${cid}/schema/test1/table -H "Content-Type: application/json" -T ${TEST_DATA} -X POST
dotest "200::*::*" "/catalog/${cid}/entity/test1:test_level2"

cat > ${TEST_DATA} <<EOF
id,name,level1_id
1,foo 1,1
2,foo 2,1
3,bar 1,2
4,baz 1,3
EOF
dotest "200::*::*" "/catalog/${cid}/entity/test1:test_level2" -H "Content-Type: text/csv" -T ${TEST_DATA} -X POST

# test basic table-linking
dotest "200::*::*" "/catalog/${cid}/entity/test1:test_level1/test1:test_level2"
dotest "200::*::*" "/catalog/${cid}/entity/test1:test_level1/test1:test_level2/test_level1"
dotest "200::*::*" "/catalog/${cid}/entity/A:=test1:test_level1/B:=test1:test_level2/test_level1"

# test joined path projections
dotest "200::*::*" "/catalog/${cid}/attribute/A:=test1:test_level1/B:=test1:test_level2/C:=test_level1/id,B:name"
dotest "200::*::*" "/catalog/${cid}/aggregate/A:=test1:test_level1/B:=test1:test_level2/C:=test_level1/count:=cnt(id)"
dotest "200::*::*" "/catalog/${cid}/aggregate/A:=test1:test_level1/B:=test1:test_level2/C:=test_level1/count:=cnt(*)"
dotest "200::*::*" "/catalog/${cid}/attributegroup/A:=test1:test_level1/B:=test1:test_level2/C:=test_level1/id,B:name"
dotest "200::*::*" "/catalog/${cid}/attributegroup/A:=test1:test_level1/B:=test1:test_level2/C:=test_level1/B:id;name"

# test wildcard expansion variations
dotest "200::*::*" "/catalog/${cid}/attribute/A:=test1:test_level1/B:=test1:test_level2/C:=test_level1/*"
dotest "200::*::*" "/catalog/${cid}/attribute/A:=test1:test_level1/B:=test1:test_level2/C:=test_level1/C:*"
dotest "200::*::*" "/catalog/${cid}/attribute/A:=test1:test_level1/B:=test1:test_level2/C:=test_level1/A:*,B:*,C:*"
dotest "200::*::*" "/catalog/${cid}/attributegroup/A:=test1:test_level1/B:=test1:test_level2/C:=test_level1/A:*;B:*,C:*"


if [[ "${DESTROY_CATALOG}" = "true" ]]
then
    ###### tear down test catalog
    dotest "20?::*::*" /catalog/${cid} -X DELETE
fi

if [[ ${NUM_FAILURES} -gt 0 ]]
then
    echo "FAILED ${NUM_FAILURES} of ${NUM_TESTS} tests" 
    exit 1
else
    echo "ALL ${NUM_TESTS} tests succeeded" >&2
    exit 0
fi
