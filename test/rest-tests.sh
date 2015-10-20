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

Setting VERBOSE=true will include full per-test information on
standard output for successes as well as failures. VERBOSE=brief will
output a single line per successful test.

Diagnostics may be printed to standard error regardless of success or
failure.

EOF
}

error()
{
    cat <<EOF
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

declare -a curl_options
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

logtest()
{
    status=$1
    shift
    cat <<EOF
TEST $(( ${NUM_TESTS} + 1 )) $status:

  Request: mycurl $@ ${BASE_URL}$url
  Expected result: $pattern
  Actual result: $summary
$(case "$*" in 
   *${TEST_DATA}*)
     cat <<EOF2

  Request body:
$(sed -e "s/^\(.*\)/    \1/" "${TEST_DATA}")

  Response headers:
EOF2
     ;;
  *)
     cat <<EOF2

  Response headers:
EOF2
     ;;
esac)
$(cat ${RESPONSE_HEADERS} | sed -e "s/^\(.*\)/    \1/")
  Response body:
$(cat ${RESPONSE_CONTENT} | sed -e "s/^\(.*\)/    \1/")

EOF

}

dotest()
{
    pattern="$1"
    url="$2"
    shift 2

    summary=$(mycurl "$@" "${BASE_URL}$url")

    hash1=
    hash2=

    if [[ "$summary" != $pattern ]]
    then
	logtest FAILED "$@"
	NUM_FAILURES=$(( ${NUM_FAILURES} + 1 ))
    else
	if [[ "$VERBOSE" = "true" ]]
	then
	    logtest OK "$@"
	elif [[ "$VERBOSE" = "brief" ]]
	then
	    cat >&2 <<EOF
TEST $(( ${NUM_TESTS} + 1 )) OK: mycurl $@ ${BASE_URL}$url --> $summary
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
    DESTROY_CATALOG=${DESTROY_CATALOG:-true}
else
    cid=${TEST_CID}
    DESTROY_CATALOG=false
fi

echo "Using catalog \"${cid}\" for testing." >&2


###### do tests on catalog

dotest "200::application/json::*" /catalog/${cid}/schema
dotest "400::*::*" /catalog/${cid}/invalid_api_name
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
FAILED: Core type ${ctype} failed to round-trip for est1:test_ctype_${ctype}:column1

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

# create table for composite-key tests
cat > ${TEST_DATA} <<EOF
{
   "kind": "table",
   "schema_name": "test1",
   "table_name": "test_composite",
   "column_definitions": [ 
      { "type": { "typename": "int8" }, "name": "id" },
      { "type": { "typename": "timestamptz" }, "name": "last_update" },
      { "type": { "typename": "text" }, "name": "name" },
      { "type": { "typename": "int8" }, "name": "site" }
   ],
   "keys": [ 
      { "unique_columns": [ "id", "site" ] } 
   ]
}
EOF
dotest "201::*::*" /catalog/${cid}/schema/test1/table -H "Content-Type: application/json" -T ${TEST_DATA} -X POST
dotest "200::*::*" "/catalog/${cid}/entity/test1:test_composite"

# test key introspection
dotest "200::application/json::*" "/catalog/${cid}/schema/test1/table/test_level1/key/"
dotest "200::application/json::*" "/catalog/${cid}/schema/test1/table/test_level1/key/id"
dotest "404::*::*" "/catalog/${cid}/schema/test1/table/test_level1/key/id,name"

dotest "200::application/json::*" "/catalog/${cid}/schema/test1/table/test_composite/key/"
dotest "200::application/json::*" "/catalog/${cid}/schema/test1/table/test_composite/key/id,site"
dotest "404::*::*" "/catalog/${cid}/schema/test1/table/test_composite/key/id"


cat > ${TEST_DATA} <<EOF
{ "unique_columns": ["id", "name"] }
EOF
dotest "201::application/json::*" "/catalog/${cid}/schema/test1/table/test_level1/key" -T ${TEST_DATA} -X POST
dotest "200::application/json::*" "/catalog/${cid}/schema/test1/table/test_level1/key/id,name"
dotest "204::*::*" "/catalog/${cid}/schema/test1/table/test_level1/key/id,name" -X DELETE
dotest "404::*::*" "/catalog/${cid}/schema/test1/table/test_level1/key/id,name" -X DELETE
dotest "404::*::*" "/catalog/${cid}/schema/test1/table/test_level1/key/id,name"

# test preconditions
for resource in "/schema/test1/table/test_level1" "/entity/test1:test_level1"
do
    dotest "200::*::*" "/catalog/${cid}${resource}"
    etag=$(grep "^ETag" ${RESPONSE_HEADERS} | sed -e "s|^ETag: ||")
    dotest "200::*::*" "/catalog/${cid}${resource}" -H 'If-Match: *'
    dotest "304::*::*" "/catalog/${cid}${resource}" -H 'If-None-Match: *'
    dotest "200::*::*" "/catalog/${cid}${resource}" -H 'If-Match: '"${etag}"
    dotest "304::*::*" "/catalog/${cid}${resource}" -H 'If-None-Match: '"${etag}"
    dotest "304::*::*" "/catalog/${cid}${resource}" -H 'If-Match: "broken-etag"'
    dotest "200::*::*" "/catalog/${cid}${resource}" -H 'If-None-Match: "broken-etag"'
    dotest "200::*::*" "/catalog/${cid}${resource}" -H 'If-Match: "broken-etag"'", ${etag}"
    dotest "304::*::*" "/catalog/${cid}${resource}" -H 'If-None-Match: "broken-etag"'", ${etag}"
done

dotest "200::*::*" "/catalog/${cid}/schema"
etag=$(grep "^ETag" ${RESPONSE_HEADERS} | sed -e "s|^ETag: ||")
dotest "412::*::*" "/catalog/${cid}/schema/DOES_NOT_EXIST" -X POST -H "If-None-Match: ${etag}"
dotest "20?::*::*" "/catalog/${cid}/schema/DOES_NOT_EXIST" -X POST -H "If-Match: ${etag}"
etag=$(grep "^ETag" ${RESPONSE_HEADERS} | sed -e "s|^ETag: ||")
dotest "412::*::*" "/catalog/${cid}/schema/DOES_NOT_EXIST" -X DELETE -H "If-None-Match: ${etag}"
dotest "20?::*::*" "/catalog/${cid}/schema/DOES_NOT_EXIST" -X DELETE -H "If-Match: ${etag}"


cat > ${TEST_DATA} <<EOF
id,name
1,foo
2,bar
3,baz
EOF
dotest "200::*::*" "/catalog/${cid}/entity/test1:test_level1" -H "Content-Type: text/csv" -T ${TEST_DATA} -X POST

cat > ${TEST_DATA} <<EOF
id,last_update,name,site
1,2010-01-01,Foo,1
1,2010-01-02,Foo,2
2,2010-01-03,Foo,1
2,2010-01-04,Foo,2
EOF
dotest "200::*::*" "/catalog/${cid}/entity/test1:test_composite" -H "Content-Type: text/csv" -T ${TEST_DATA} -X POST

cat > ${TEST_DATA} <<EOF
id,last_update,name,site
1,2010-01-01,Foo1,1
2,2010-01-04,Foo1,1
EOF
dotest "200::*::*" "/catalog/${cid}/entity/test1:test_composite" -H "Content-Type: text/csv" -T ${TEST_DATA} -X PUT

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

# do comment tests
resources=(
    /schema/test1
    /schema/test1/table/test_level2
    /schema/test1/table/test_level2/column/name
    /schema/test1/table/test_level2/key/id
    /schema/test1/table/test_level2/foreignkey/level1_id/reference/test_level1/id
)
for resource in ${resources[@]}
do
    dotest "404::*::*" "/catalog/${cid}${resource}/comment"
    cat > ${TEST_DATA} <<EOF
This is a comment.
EOF
    dotest "20?::*::*" "/catalog/${cid}${resource}/comment" -T ${TEST_DATA}
    dotest "204::*::*" "/catalog/${cid}${resource}/comment" -T ${TEST_DATA}
    dotest "200::text/plain*::*" "/catalog/${cid}${resource}/comment"
    dotest "20?::*::*" "/catalog/${cid}${resource}/comment" -X DELETE
    dotest "404::*::*" "/catalog/${cid}${resource}/comment"
done

# do annotation tests
do_annotation_phase1_tests()
{
    local resource="$1" tag_key="$2" test_value="$3"

    dotest "200::application/json::*" "/catalog/${cid}${resource}/annotation"
    dotest "404::*::*" "/catalog/${cid}${resource}/annotation/${tag_key}"
    cat > ${TEST_DATA} <<EOF
"${test_value}"
EOF
    dotest "405::*::*" "/catalog/${cid}${resource}/annotation" -T ${TEST_DATA}
    dotest "201::*::*" "/catalog/${cid}${resource}/annotation/${tag_key}" -T ${TEST_DATA}
    cat > ${TEST_DATA} <<EOF
{"dummy": "value", "malformed"
EOF
    dotest "400::*::*" "/catalog/${cid}${resource}/annotation/${tag_key}" -T ${TEST_DATA}
}

do_annotation_phase2_tests()
{
    local resource="$1" tag_key="$2" test_value="\"$3\""

    dotest "200::application/json::*" "/catalog/${cid}${resource}/annotation/${tag_key}"
    if ! grep -q "${test_value}" ${RESPONSE_CONTENT}
    then
	cat <<EOF
FAILED: Annotation value mismatch.
  Expected: ${test_value}  (${#test_value} bytes)
  Actual: $(cat ${RESPONSE_CONTENT})  ($(wc -c ${RESPONSE_CONTENT}) bytes)

EOF
	NUM_FAILURES=$(( ${NUM_FAILURES} + 1 ))
    fi
    NUM_TESTS=$(( ${NUM_TESTS} + 1 ))
}

do_annotation_phase3_tests()
{
    local resource="$1" tag_key="$2"

    dotest "405::*::*" "/catalog/${cid}${resource}/annotation" -X DELETE
    dotest "200::application/json::*" "/catalog/${cid}${resource}/annotation/${tag_key}"
    dotest "20?::*::*" "/catalog/${cid}${resource}/annotation/${tag_key}" -X DELETE
}

tag_key='tag%3Amisd.isi.edu%2C2015%3Atest1' # tag:misd.isi.edu,2015:test1
tag_key2='tag%3Amisd.isi.edu%2C2015%3Atest2' # tag:misd.isi.edu,2015:test2
resources=(
    /schema/test1
    /schema/test1/table/test_level2
    /schema/test1/table/test_level2/column/name
    /schema/test1/table/test_level2/key/id
    /schema/test1/table/test_level2/foreignkey/level1_id/reference/test_level1/id
)
for resource in ${resources[@]}
do
    do_annotation_phase1_tests "${resource}" "${tag_key}" "${resource} value 1"
    do_annotation_phase2_tests "${resource}" "${tag_key}" "${resource} value 1"
    
    do_annotation_phase1_tests "${resource}" "${tag_key2}" "${resource} value 2"
    do_annotation_phase2_tests "${resource}" "${tag_key2}" "${resource} value 2"

    # re-check first value (regression test for issue #37, PUT modified values for other keys too)
    do_annotation_phase2_tests "${resource}" "${tag_key}" "${resource} value 1"
    
    do_annotation_phase3_tests "${resource}" "${tag_key}"
    do_annotation_phase3_tests "${resource}" "${tag_key2}"
done

# do more destructive precondition tests
dotest "200::*::*" "/catalog/${cid}/entity/test1:test_level1"
etag1=$(grep "^ETag" ${RESPONSE_HEADERS} | sed -e "s|^ETag: ||")

cat > ${TEST_DATA} <<EOF
id,name
47,foo
EOF

dotest "412::*::*" "/catalog/${cid}/entity/test1:test_level1" -H "Content-Type: text/csv" -T ${TEST_DATA} -X POST -H 'If-Match: "broken"'
dotest "412::*::*" "/catalog/${cid}/entity/test1:test_level1" -H "Content-Type: text/csv" -T ${TEST_DATA} -X POST -H 'If-None-Match: '"${etag1}"
dotest "200::*::*" "/catalog/${cid}/entity/test1:test_level1" -H "Content-Type: text/csv" -T ${TEST_DATA} -X POST -H 'If-Match: '"${etag1}"
etag2=$(grep "^ETag" ${RESPONSE_HEADERS} | sed -e "s|^ETag: ||")

if [[ "${etag2}" == "${etag1}" ]]
then
    cat <<EOF
FAILED: POST response ETag does not reflect changed resource state

$(cat ${RESPONSE_HEADERS})
EOF
    NUM_FAILURES=$(( ${NUM_FAILURES} + 1 ))
elif [[ -z "${etag2}" ]]
then
    cat <<EOF
FAILED: POST response lacks ETag header

$(cat ${RESPONSE_HEADERS})
EOF
    NUM_FAILURES=$(( ${NUM_FAILURES} + 1 ))
fi
NUM_TESTS=$(( ${NUM_TESTS} + 1 ))

dotest "304::*::*" "/catalog/${cid}/entity/test1:test_level1/id=47" -H 'If-None-Match: '"${etag2}"

dotest "200::*::*" "/catalog/${cid}/entity/test1:test_level1"
etag2=$(grep "^ETag" ${RESPONSE_HEADERS} | sed -e "s|^ETag: ||")

cat > ${TEST_DATA} <<EOF
id,name
47,bar
EOF
dotest "412::*::*" "/catalog/${cid}/entity/test1:test_level1" -H "Content-Type: text/csv" -T ${TEST_DATA} -H 'If-Match: "broken"'
dotest "412::*::*" "/catalog/${cid}/entity/test1:test_level1" -H "Content-Type: text/csv" -T ${TEST_DATA} -H 'If-None-Match: '"${etag2}"
dotest "200::*::*" "/catalog/${cid}/entity/test1:test_level1" -H "Content-Type: text/csv" -T ${TEST_DATA} -H 'If-Match: '"${etag2}"

dotest "200::*::*" "/catalog/${cid}/entity/test1:test_level1"
etag3=$(grep "^ETag" ${RESPONSE_HEADERS} | sed -e "s|^ETag: ||")

dotest "412::*::*" "/catalog/${cid}/attributegroup/test1:test_level1/id;name" -H "Content-Type: text/csv" -T ${TEST_DATA} -H 'If-Match: "broken"'
dotest "412::*::*" "/catalog/${cid}/attributegroup/test1:test_level1/id;name" -H "Content-Type: text/csv" -T ${TEST_DATA} -H 'If-None-Match: '"${etag3}"
dotest "200::*::*" "/catalog/${cid}/attributegroup/test1:test_level1/id;name" -H "Content-Type: text/csv" -T ${TEST_DATA} -H 'If-Match: '"${etag3}"

dotest "200::*::*" "/catalog/${cid}/entity/test1:test_level1"
etag4=$(grep "^ETag" ${RESPONSE_HEADERS} | sed -e "s|^ETag: ||")

dotest "412::*::*" "/catalog/${cid}/entity/test1:test_level1/id=47" -X DELETE -H 'If-Match: "broken"'
dotest "412::*::*" "/catalog/${cid}/entity/test1:test_level1/id=47" -X DELETE -H 'If-None-Match: '"${etag4}"
dotest "204::*::*" "/catalog/${cid}/entity/test1:test_level1/id=47" -X DELETE -H 'If-Match: '"${etag4}"

# create table for unicode tests... use unusual unicode characters to test proper pass-through
dotest "201::*::*" "/catalog/${cid}/schema/%C9%90%C9%AF%C7%9D%C9%A5%C9%94s" -X POST
cat > ${TEST_DATA} <<EOF
{
   "kind": "table",
   "schema_name": "ɐɯǝɥɔs",
   "table_name": "ǝlqɐʇ",
   "column_definitions": [ 
      { "type": { "typename": "int8" }, "name": "id" },
      { "type": { "typename": "text" }, "name": "ǝɯɐu" }
   ],
   "keys": [ { "unique_columns": [ "id" ] } ]
}
EOF
dotest "201::*::*" "/catalog/${cid}/schema/%C9%90%C9%AF%C7%9D%C9%A5%C9%94s/table" -H "Content-Type: application/json" -T ${TEST_DATA} -X POST
dotest "200::*::*" "/catalog/${cid}/entity/%C9%90%C9%AF%C7%9D%C9%A5%C9%94s:%C7%9Dlq%C9%90%CA%87"

# make sure weird column name is OK in CSV
cat > ${TEST_DATA} <<EOF
id,ǝɯɐu
1,foo 1
2,foo 2
3,bar 1
4,baz 1
EOF
dotest "200::*::*" "/catalog/${cid}/entity/%C9%90%C9%AF%C7%9D%C9%A5%C9%94s:%C7%9Dlq%C9%90%CA%87" -H "Content-Type: text/csv" -T ${TEST_DATA} -X POST

# make sure weird column name is OK in JSON
cat > ${TEST_DATA} <<EOF
[{"id":5,"ǝɯɐu": "baz 2"}]
EOF
dotest "200::*::*" "/catalog/${cid}/entity/%C9%90%C9%AF%C7%9D%C9%A5%C9%94s:%C7%9Dlq%C9%90%CA%87" -H "Content-Type: application/json" -T ${TEST_DATA} -X POST

# make sure weird data is OK in CSV
cat > ${TEST_DATA} <<EOF
id,ǝɯɐu
6,foo ǝɯɐu
EOF
dotest "200::*::*" "/catalog/${cid}/entity/%C9%90%C9%AF%C7%9D%C9%A5%C9%94s:%C7%9Dlq%C9%90%CA%87" -H "Content-Type: text/csv" -T ${TEST_DATA} -X POST

# make sure weird data is OK in JSON
cat > ${TEST_DATA} <<EOF
[{"id":7,"ǝɯɐu": "foo ǝɯɐu 2"}]
EOF
dotest "200::*::*" "/catalog/${cid}/entity/%C9%90%C9%AF%C7%9D%C9%A5%C9%94s:%C7%9Dlq%C9%90%CA%87" -H "Content-Type: application/json" -T ${TEST_DATA} -X POST

# test access to data in CSV and JSON
dotest "200::*::*" "/catalog/${cid}/entity/%C9%90%C9%AF%C7%9D%C9%A5%C9%94s:%C7%9Dlq%C9%90%CA%87" -H "Accept: text/csv"
dotest "200::*::*" "/catalog/${cid}/entity/%C9%90%C9%AF%C7%9D%C9%A5%C9%94s:%C7%9Dlq%C9%90%CA%87" -H "Accept: application/json"

# test CSV error cases including that unicode data passes through OK
cat > ${TEST_DATA} <<EOF
id,ǝɯɐu
10
EOF
dotest "400::*::*" "/catalog/${cid}/entity/%C9%90%C9%AF%C7%9D%C9%A5%C9%94s:%C7%9Dlq%C9%90%CA%87" -H "Content-Type: text/csv" -T ${TEST_DATA} -X POST

# test CSV error cases including that unicode data passes through OK
cat > ${TEST_DATA} <<EOF
ǝɯɐu,id
ǝlqɐʇ
EOF
dotest "400::*::*" "/catalog/${cid}/entity/%C9%90%C9%AF%C7%9D%C9%A5%C9%94s:%C7%9Dlq%C9%90%CA%87" -H "Content-Type: text/csv" -T ${TEST_DATA} -X POST

cat > ${TEST_DATA} <<EOF
id
10
EOF
dotest "409::*::*" "/catalog/${cid}/entity/%C9%90%C9%AF%C7%9D%C9%A5%C9%94s:%C7%9Dlq%C9%90%CA%87" -H "Content-Type: text/csv" -T ${TEST_DATA} -X POST

cat > ${TEST_DATA} <<EOF
id,ǝlqɐʇ
10,foo 10
EOF
dotest "409::*::*" "/catalog/${cid}/entity/%C9%90%C9%AF%C7%9D%C9%A5%C9%94s:%C7%9Dlq%C9%90%CA%87" -H "Content-Type: text/csv" -T ${TEST_DATA} -X POST

for pattern in foo bar "foo.%2A"
do
    dotest "200::*::*" "/catalog/${cid}/textfacet/${pattern}"
done

if [[ "${DESTROY_CATALOG}" = "true" ]]
then
    ###### tear down test catalog
    dotest "20?::*::*" /catalog/${cid} -X DELETE
    dotest "404::*::*" /catalog/${cid} -X DELETE
fi

if [[ ${NUM_FAILURES} -gt 0 ]]
then
    echo "FAILED ${NUM_FAILURES} of ${NUM_TESTS} tests" 
    exit 1
else
    echo "ALL ${NUM_TESTS} tests succeeded" >&2
    exit 0
fi
