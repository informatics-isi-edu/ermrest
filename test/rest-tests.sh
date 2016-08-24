#!/bin/bash

# Run basic ERMrest REST API tests 

usage()
{
    cat <<EOF
usage: $0

Runs test against BASE_URL environment (${BASE_URL}), default (https://$(hostname)/ermrest/).

Uses cookie store named in COOKIES environment ($COOKIES), if
specified.

A successful run will exit with status 0 and an empty standard output.

A failure will exit with status 1 and a non-empty standard output.

Test case failures will not abort testing unless ABORT_ON_FAILURE is
set to "true". However, 500 Internal Server Error responses will
always abort testing.

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

BASE_URL=${BASE_URL:-"https://$(hostname)/ermrest"}

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

  Curl options:

   ${curl_options[@]}

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

	errorpattern="500::*::*"
    
	if [[ "$summary" = $errorpattern ]] || [[ "${ABORT_ON_FAILURE:-false}" = "true" ]]
	then
	    if [[ -n "$cid" ]] && [[ "${DESTROY_CATALOG}" = "true" ]]
	    then
		mycurl -X DELETE "${BASE_URL}/catalog/${cid}"
	    fi
	    error terminating on "$summary"
	fi
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
    longtext
    markdown
    timestamptz
    date
    uuid
    interval
    serial2
    serial4
    serial8
)

# use corresponding test values
cvals=(
    True
    1.0
    1.0
    1
    1
    1
    one
    oneoneoneone
    '**one**'
    '2015-03-11T11:32:56-0700'
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

    # apply url-escaping in limited form to cover cvals array above
    cval_uri=$(sed -e 's/:/%3A/g' <<<"${cval}")

    if [[ "$ctype" == serial* ]] || [[ "$ctype" == longtext ]] || [[ "$ctype" == markdown ]]
    then
	# do not try to test array types based on serial nor domain
	col3_type="{ \"typename\": \"${ctype}\" }"
    else
	col3_type="{ \"typename\": \"${ctype}[]\", \"is_array\": true, \"base_type\": { \"typename\": \"${ctype}\" } }"
    fi

    cat > ${TEST_DATA} <<EOF
{
   "kind": "table",
   "schema_name": "test1",
   "table_name": "test_ctype_${ctype}",
   "column_definitions": [ 
      { "type": { "typename": "${ctype}" }, "name": "column1" },
      { "type": { "typename": "text" }, "name": "column2" },
      { "type": ${col3_type}, "name": "column3" }
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
FAILED: Core type ${ctype} failed to round-trip for test1:test_ctype_${ctype}:column1

$(cat ${RESPONSE_CONTENT})
EOF
        NUM_FAILURES=$(( ${NUM_FAILURES} + 1 ))
    fi
    NUM_TESTS=$(( ${NUM_TESTS} + 1 ))

    # test handling of column-typed literals in filters
    dotest "200::application/json::*" "/catalog/${cid}/entity/test1:test_ctype_${ctype}/column1=${cval_uri}"
    dotest "200::application/json::*" "/catalog/${cid}/entity/test1:test_ctype_${ctype}/column3=${cval_uri}"

    if [[ "$ctype" == serial* ]]
    then
	# test insertion of rows with server-generated serial ID types
	cat > ${TEST_DATA} <<EOF
column1,column2,column3
,value1,${cval}
,value1,${cval}
,value2,${cval}
EOF
	dotest "200::*::*" "/catalog/${cid}/entity/test1:test_ctype_${ctype}?defaults=column1" -H "Content-Type: text/csv" -T ${TEST_DATA} -X POST

	cat > ${TEST_DATA} <<EOF
[{"column2": "value2", "column3": "${cval}"}]
EOF
	dotest "200::*::*" "/catalog/${cid}/entity/test1:test_ctype_${ctype}?defaults=column1" -H "Content-Type: application/json" -T ${TEST_DATA} -X POST
    else
	# test insertion of rows with array data
	cat > ${TEST_DATA} <<EOF
column1,column2,column3
${cval},value1,"{${cval},${cval}}"
EOF
	dotest "200::*::*" "/catalog/${cid}/entity/test1:test_ctype_${ctype}" -H "Content-Type: text/csv" -T ${TEST_DATA} -X POST

	cat > ${TEST_DATA} <<EOF
[{"column1": "${cval}", "column2": "value1", "column3": ["${cval}", "${cval}"]}]
EOF
	dotest "200::*::*" "/catalog/${cid}/entity/test1:test_ctype_${ctype}" -H "Content-Type: application/json" -T ${TEST_DATA}
    fi
    
    dotest "200::text/csv::*" "/catalog/${cid}/entity/test1:test_ctype_${ctype}" -H "Accept: text/csv"
    dotest "200::application/json::*" "/catalog/${cid}/entity/test1:test_ctype_${ctype}"

    # drop table
    dotest "204::*::*" /catalog/${cid}/schema/test1/table/test_ctype_${ctype} -X DELETE
done

doresponsediff()
{
    diff -q -w ${RESPONSE_CONTENT} ${TEST_DATA}
    status=$?

    if [[ $status = 1 ]]
    then
	cat <<EOF
FAILED: Data round-trip failed for $@

$(diff -w ${RESPONSE_CONTENT} ${TEST_DATA})
EOF
	NUM_FAILURES=$(( ${NUM_FAILURES} + 1 ))
    else
	if [[ "$VERBOSE" = true ]] || [[ "$VERBOSE" = brief ]]
	then
	    cat <<EOF
TEST $(( ${NUM_TESTS} + 1 )) OK: Entities round-tripped for $@
EOF
	fi
    fi
    NUM_TESTS=$(( ${NUM_TESTS} + 1 ))
}

for etype in json jsonb
do
    cat > ${TEST_DATA} <<EOF
{
   "kind": "table",
   "schema_name": "test1",
   "table_name": "test_etype_${etype}",
   "column_definitions": [ 
      { "type": { "typename": "int8" }, "name": "id" },
      { "type": { "typename": "text" }, "name": "name" },
      { "type": { "typename": "${etype}" }, "name": "payload" }
   ],
   "keys": [ { "unique_columns": [ "id" ] } ]
}
EOF

    dotest "201::*::*" /catalog/${cid}/schema/test1/table -H "Content-Type: application/json" -T ${TEST_DATA} -X POST
    dotest "200::*::*" /catalog/${cid}/entity/test1:test_etype_${etype}
    dotest "200::application/json::*" /catalog/${cid}/schema/test1/table/test_etype_${etype}

    write_urls=(
	"/catalog/${cid}/entity/test1:test_etype_${etype}"
	"/catalog/${cid}/attributegroup/test1:test_etype_${etype}/id;name,payload"
    )
    
    read_urls=(
	"${write_urls[@]}"
	"/catalog/${cid}/attribute/test1:test_etype_${etype}/id,name,payload"
    )

    for eval_json in '5' '"foo"' '{"foo": "bar"}' '[5, 6]' '["foo", "bar"]' '[{"foo": "bar"}, {"foo": "bar"}]'
    do
	eval_csv="\"$(echo "${eval_json}" | sed -e "s/\"/\"\"/g")\""
	[[ "${eval_csv}" = '"5"' ]] && eval_csv=5  # HACK: special case the above logic for integer test case
    
	cat > ${TEST_DATA} <<EOF
id,name,payload
1,row1,${eval_csv}
EOF
	for write_url in "${write_urls[@]}"
	do
	    dotest "200::*::*" "${write_url}" -H "Content-Type: text/csv" -T ${TEST_DATA}
	    # these outputs look correct but have unstable order so don't work with diff testing...
	    #doresponsediff "CSV encoded JSON ${eval_json} for ${write_url} PUT response"

	    for read_url in "${read_urls[@]}"
	    do
		dotest "200::text/csv::*" "${read_url}@sort(id)" -H "Accept: text/csv"
		doresponsediff "CSV encoded JSON ${eval_json} for ${write_url} to ${read_url}"
	    done
	done
	    
	cat > ${TEST_DATA} <<EOF
[{"id": 1, "name": "row1", "payload": ${eval_json}}]
EOF
	for write_url in "${write_urls[@]}"
	do
	    dotest "200::*::*" "${write_url}" -H "Content-Type: application/json" -T ${TEST_DATA}
	    # these outputs look correct but have unstable order so don't work with diff testing...
	    #doresponsediff "JSON encoded JSON ${eval_json} for ${write_url} PUT response"
	    
	    for read_url in "${read_urls[@]}"
	    do
		dotest "200::application/json::*" "${read_url}@sort(id)" -H "Accept: application/json"
		doresponsediff "JSON encoded JSON ${eval_json} for ${write_url} to ${read_url}"
	    done
	done
    done
    
    dotest "204::*::*" /catalog/${cid}/schema/test1/table/test_etype_${etype} -X DELETE
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

# do basic parsing tests
for path in "test_level1" "test1:test_level1"
do
    for filter in "" "/id=4" "/name=foo" "/name="
    do
	dotest "200::*::*" "/catalog/${cid}/entity/${path}${filter}"
	dotest "200::*::*" "/catalog/${cid}/attribute/${path}${filter}/id,name"
	dotest "400::*::*" "/catalog/${cid}/attribute/${path}${filter}/id;name"
	dotest "200::*::*" "/catalog/${cid}/attributegroup/${path}${filter}/id;name,n:=cnt(name)"
	dotest "200::*::*" "/catalog/${cid}/aggregate/${path}${filter}/n:=cnt(id),ndistinct:=cnt_d(name)"
    done
    dotest "400::*::*" "/catalog/${cid}/entity/id=4"
    dotest "400::*::*" "/catalog/${cid}/attribute/id=4/id,name"
    dotest "400::*::*" "/catalog/${cid}/attribute/id=4/id;name"
    dotest "400::*::*" "/catalog/${cid}/attributegroup/id=4/id;name,n:=cnt(name)"
    dotest "400::*::*" "/catalog/${cid}/aggregate/id=4/n:=cnt(id),ndistinct:=cnt_d(name)"
done

# create table for composite-key tests and also nullok input
cat > ${TEST_DATA} <<EOF
{
   "kind": "table",
   "schema_name": "test1",
   "table_name": "test_composite",
   "column_definitions": [ 
      { "type": { "typename": "int8" }, "name": "id", "nullok": false },
      { "type": { "typename": "timestamptz" }, "name": "last_update" },
      { "type": { "typename": "text" }, "name": "name", "nullok": true },
      { "type": { "typename": "int8" }, "name": "site", "nullok": false }
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
3,,,2
EOF
dotest "200::*::*" "/catalog/${cid}/entity/test1:test_composite" -H "Content-Type: text/csv" -T ${TEST_DATA} -X PUT

cat > ${TEST_DATA} <<EOF
id,last_update,name,site
1,2010-01-02,Foo,2
,2010-01-01,FooN,1
EOF
dotest "409::*::*" "/catalog/${cid}/entity/test1:test_composite" -H "Content-Type: text/csv" -T ${TEST_DATA} -X PUT

cat > ${TEST_DATA} <<EOF
id,last_update,name,site
1,2010-01-02,Foo,2
1,2010-01-01,FooN,
EOF
dotest "409::*::*" "/catalog/${cid}/entity/test1:test_composite" -H "Content-Type: text/csv" -T ${TEST_DATA} -X PUT

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

# create table for composite-fkey tests and also nullok input
cat > ${TEST_DATA} <<EOF
{
   "kind": "table",
   "schema_name": "test1",
   "table_name": "test_composite2",
   "column_definitions": [ 
      { "type": { "typename": "int8" }, "name": "id", "nullok": false },
      { "type": { "typename": "timestamptz" }, "name": "last_update" },
      { "type": { "typename": "text" }, "name": "name", "nullok": true },
      { "type": { "typename": "int8" }, "name": "site", "nullok": false }
   ],
   "keys": [ 
      { "unique_columns": [ "id", "site" ] } 
   ],
   "foreign_keys": [
      { 
        "foreign_key_columns": [
          {"schema_name": "test1", "table_name": "test_composite2", "column_name": "id"},
          {"schema_name": "test1", "table_name": "test_composite2", "column_name": "site"}

        ],
        "referenced_columns": [
          {"schema_name": "test1", "table_name": "test_composite", "column_name": "id"},
          {"schema_name": "test1", "table_name": "test_composite", "column_name": "site"}
        ]
      }
   ]
}
EOF
dotest "201::*::*" /catalog/${cid}/schema/test1/table -H "Content-Type: application/json" -T ${TEST_DATA} -X POST
dotest "200::*::*" "/catalog/${cid}/entity/test1:test_composite2"

# column API tests
dotest "200::application/json::*" /catalog/${cid}/schema/test1/table/test_level2/column
dotest "200::application/json::*" /catalog/${cid}/schema/test1/table/test_level2/column/name
dotest "204::*::*" /catalog/${cid}/schema/test1/table/test_level2/column/name -X DELETE

cat > ${TEST_DATA} <<EOF
{ "type": { "typename": "text" }, "name": "name" }
EOF
dotest "201::*::*" /catalog/${cid}/schema/test1/table/test_level2/column -H "Content-Type: application/json" -T ${TEST_DATA} -X POST
dotest "200::application/json::*" /catalog/${cid}/schema/test1/table/test_level2/column/name

# key API tests
dotest "200::application/json::*" /catalog/${cid}/schema/test1/table/test_level2/key
dotest "200::application/json::*" /catalog/${cid}/schema/test1/table/test_level2/key/id
dotest "204::*::*" /catalog/${cid}/schema/test1/table/test_level2/key/id -X DELETE
dotest "404::*::*" /catalog/${cid}/schema/test1/table/test_level2/key/id

cat > ${TEST_DATA} <<EOF
{ "unique_columns": [ "id" ] }
EOF
dotest "201::*::*" /catalog/${cid}/schema/test1/table/test_level2/key -H "Content-Type: application/json" -T ${TEST_DATA} -X POST
dotest "200::application/json::*" /catalog/${cid}/schema/test1/table/test_level2/key/id

# foreign key API tests
dotest "200::application/json::*" /catalog/${cid}/schema/test1/table/test_level2/foreignkey
dotest "200::application/json::*" /catalog/${cid}/schema/test1/table/test_level2/foreignkey/level1_id
dotest "200::application/json::*" /catalog/${cid}/schema/test1/table/test_level2/foreignkey/level1_id/reference
dotest "200::application/json::*" /catalog/${cid}/schema/test1/table/test_level2/foreignkey/level1_id/reference/test1:test_level1
dotest "200::application/json::*" /catalog/${cid}/schema/test1/table/test_level2/foreignkey/level1_id/reference/test1:test_level1/id
dotest "204::*::*" /catalog/${cid}/schema/test1/table/test_level2/foreignkey/level1_id/reference/test1:test_level1/id -X DELETE
dotest "404::*::*" /catalog/${cid}/schema/test1/table/test_level2/foreignkey/level1_id/reference/test1:test_level1/id

cat > ${TEST_DATA} <<EOF
{ 
  "foreign_key_columns": [{"schema_name": "test1", "table_name": "test_level2", "column_name": "level1_id"}],
  "referenced_columns": [{"schema_name": "test1", "table_name": "test_level1", "column_name": "id"}]
}
EOF
dotest "201::*::*" /catalog/${cid}/schema/test1/table/test_level2/foreignkey -H "Content-Type: application/json" -T ${TEST_DATA} -X POST
dotest "200::application/json::*" /catalog/${cid}/schema/test1/table/test_level2/foreignkey/level1_id/reference/test1:test_level1/id

# load test data
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

# test ambiguous links
cat > ${TEST_DATA} <<EOF
{
   "kind": "table",
   "schema_name": "test1",
   "table_name": "test_level2b",
   "column_definitions": [
      { "type": { "typename": "int8" }, "name": "id" },
      { "type": { "typename": "int8" }, "name": "level1_id1"},
      { "type": { "typename": "int8" }, "name": "level1_id2"},
      { "type": { "typename": "text" }, "name": "name" }
   ],
   "keys": [ { "unique_columns": [ "id" ] } ],
   "foreign_keys": [
      {
        "foreign_key_columns": [{"schema_name": "test1", "table_name": "test_level2b", "column_name": "level1_id1"}],
        "referenced_columns": [{"schema_name": "test1", "table_name": "test_level1", "column_name": "id"}]
      },
      {
        "foreign_key_columns": [{"schema_name": "test1", "table_name": "test_level2b", "column_name": "level1_id2"}],
        "referenced_columns": [{"schema_name": "test1", "table_name": "test_level1", "column_name": "id"}]
      }
   ]
}
EOF
dotest "201::*::*" /catalog/${cid}/schema/test1/table -H "Content-Type: application/json" -T ${TEST_DATA} -X POST
dotest "200::*::*" "/catalog/${cid}/entity/test1:test_level2b"

# load test data
cat > ${TEST_DATA} <<EOF
id,name,level1_id1,level1_id2
1,foo 1,1,1
2,foo 2,1,2
3,bar 1,2,3
4,baz 1,3,1
EOF
dotest "200::*::*" "/catalog/${cid}/entity/test1:test_level2b" -H "Content-Type: text/csv" -T ${TEST_DATA} -X POST

# test basic table-linking
dotest "200::*::*" "/catalog/${cid}/entity/test1:test_level1/(test1:test_level2b:level1_id1)"
dotest "200::*::*" "/catalog/${cid}/entity/test1:test_level1/(test1:test_level2b:level1_id2)"
dotest "200::*::*" "/catalog/${cid}/entity/test1:test_level1/test1:test_level2b"

# test explicit join linking
dotest "200::*::*" "/catalog/${cid}/entity/test1:test_level1/(id)=(test1:test_level2b:level1_id1)"
dotest "200::*::*" "/catalog/${cid}/entity/test1:test_level1/(id)=(test1:test_level2b:level1_id2)"
dotest "200::*::*" "/catalog/${cid}/entity/test1:test_level2/(level1_id)=(test1:test_level2b:level1_id2)"
dotest "200::*::*" "/catalog/${cid}/entity/test1:test_level2/(id)=(test1:test_level2b:level1_id2)"

# test composite link resolution
dotest "200::*::*" "/catalog/${cid}/entity/test1:test_composite/(id,site)"
dotest "200::*::*" "/catalog/${cid}/entity/A:=test1:test_composite/(A:id,A:site)"
dotest "200::*::*" "/catalog/${cid}/entity/A:=test1:test_composite/(A:id,site)"
dotest "200::*::*" "/catalog/${cid}/entity/test1:test_composite/(test1:test_composite2:id,test1:test_composite2:site)"
dotest "200::*::*" "/catalog/${cid}/entity/test1:test_composite/(test1:test_composite2:id,site)"
dotest "200::*::*" "/catalog/${cid}/entity/test1:test_composite/(id,site)=(test1:test_composite2:id,test1:test_composite2:site)"
dotest "200::*::*" "/catalog/${cid}/entity/A:=test1:test_composite/(A:id,A:site)=(test1:test_composite2:id,test1:test_composite2:site)"
dotest "200::*::*" "/catalog/${cid}/entity/A:=test1:test_composite/(A:id,site)=(test1:test_composite2:id,test1:test_composite2:site)"
dotest "200::*::*" "/catalog/${cid}/entity/test1:test_composite/(id,site)=(test1:test_composite2:id,site)"
dotest "200::*::*" "/catalog/${cid}/entity/A:=test1:test_composite/(A:id,site)=(test1:test_composite2:id,site)"

# test aliased attributegroup updates
cat > ${TEST_DATA} <<EOF
old,new
foo 1,foo 1B
foo 2,foo 2B
bar 1,bar 1B
EOF
dotest "200::*::*" "/catalog/${cid}/attributegroup/test1:test_level2b/old:=name;new:=name" -H "Content-Type: text/csv" -T ${TEST_DATA}

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

cat > ${TEST_DATA} <<EOF
{
   "kind": "table",
   "schema_name": "test1",
   "table_name": "test_comments",
   "comment": "TABLE1",
   "column_definitions": [ 
      { "type": { "typename": "int8" }, "name": "id", "comment": "COLUMN1" },
      { "type": { "typename": "int8" }, "name": "level1_id", "comment": "COLUMN2" },
      { "type": { "typename": "text" }, "name": "name", "comment": "COLUMN3" },
      { "type": { "typename": "int8" }, "name": "level1_id2", "comment": "COLUMN4" }
   ],
   "keys": [ { "unique_columns": [ "id" ], "comment": "KEY1" } ],
   "foreign_keys": [
      { 
        "comment": "FKEY1",
        "foreign_key_columns": [{"schema_name": "test1", "table_name": "test_comments", "column_name": "level1_id"}],
        "referenced_columns": [{"schema_name": "test1", "table_name": "test_level1", "column_name": "id"}]
      }
   ]
}
EOF
dotest "201::*::*" /catalog/${cid}/schema/test1/table -H "Content-Type: application/json" -T ${TEST_DATA} -X POST

cat > ${TEST_DATA} <<EOF
{ "unique_columns": [ "name" ], "comment": "KEY2" }
EOF
dotest "201::*::*" /catalog/${cid}/schema/test1/table/test_comments/key -H "Content-Type: application/json" -T ${TEST_DATA} -X POST

cat > ${TEST_DATA} <<EOF
{
  "comment": "FKEY2",
  "foreign_key_columns": [{"schema_name": "test1", "table_name": "test_comments", "column_name": "level1_id2"}],
  "referenced_columns": [{"schema_name": "test1", "table_name": "test_level1", "column_name": "id"}]
}
EOF
dotest "201::*::*" /catalog/${cid}/schema/test1/table/test_comments/foreignkey -H "Content-Type: application/json" -T ${TEST_DATA} -X POST

do_comment_test()
{
    local resource="$1" comment="$2"

    dotest "200::*::*" "/catalog/${cid}${resource}/comment"
    if ! grep -q "${comment}" ${RESPONSE_CONTENT}
    then
	cat <<EOF
FAILED: Comment value mismatch.
  Expected: ${comment}  (${#test_value} bytes)
  Actual: $(cat ${RESPONSE_CONTENT})  ($(wc -c ${RESPONSE_CONTENT}) bytes)

EOF
	NUM_FAILURES=$(( ${NUM_FAILURES} + 1 ))
    fi
    NUM_TESTS=$(( ${NUM_TESTS} + 1 ))
}

do_comment_test /schema/test1/table/test_comments                  TABLE1
do_comment_test /schema/test1/table/test_comments/column/id        COLUMN1
do_comment_test /schema/test1/table/test_comments/column/level1_id COLUMN2
do_comment_test /schema/test1/table/test_comments/column/name      COLUMN3
do_comment_test /schema/test1/table/test_comments/key/id           KEY1
do_comment_test /schema/test1/table/test_comments/key/name           KEY2
do_comment_test /schema/test1/table/test_comments/foreignkey/level1_id/reference/test1:test_level1/id FKEY1
do_comment_test /schema/test1/table/test_comments/foreignkey/level1_id2/reference/test1:test_level1/id FKEY2

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

# test foreign key reference names
dofkrnamestest()
{
    testpattern="$1"
    fkrnames="$2"

    cat > ${TEST_DATA} <<EOF
{
   "kind": "table",
   "schema_name": "test1",
   "table_name": "test_level2c",
   "column_definitions": [
      { "type": { "typename": "int8" }, "name": "id" },
      { "type": { "typename": "int8" }, "name": "level1_id1"},
      { "type": { "typename": "text" }, "name": "name" }
   ],
   "keys": [ { "unique_columns": [ "id" ] } ],
   "foreign_keys": [
      {
        "names": ${fkrnames},
        "foreign_key_columns": [{"schema_name": "test1", "table_name": "test_level2c", "column_name": "level1_id1"}],
        "referenced_columns": [{"schema_name": "test1", "table_name": "test_level1", "column_name": "id"}]
      }
   ]
}
EOF
    dotest "$testpattern" /catalog/${cid}/schema/test1/table -H "Content-Type: application/json" -T ${TEST_DATA} -X POST
    if [[ "$testpattern" == 201* ]]
    then
	dotest "204::*::*" "/catalog/${cid}/schema/test1/table/test_level2c" -X DELETE
    fi
}

dofkrnamestest "201::*::*" "[]"
dofkrnamestest "201::*::*" "null"
dofkrnamestest "201::*::*" "[[\"test1\", \"mytestconstraint\"]]"
dofkrnamestest "400::*::*" "[[\"test1\", 5]]"
dofkrnamestest "400::*::*" "[5]"
dofkrnamestest "400::*::*" "[[\"test1\", \"mytestconstraint\", \"too many names\"]"

# create table for paging tests
cat > ${TEST_DATA} <<EOF
{
   "kind": "table",
   "schema_name": "test1",
   "table_name": "pagedata",
   "column_definitions": [ 
      { "type": { "typename": "serial4" }, "name": "id" },
      { "type": { "typename": "text" }, "name": "name" },
      { "type": { "typename": "int4" }, "name": "value" }
   ],
   "keys": [ { "unique_columns": [ "id" ] } ]
}
EOF
dotest "201::*::*" /catalog/${cid}/schema/test1/table -H "Content-Type: application/json" -T ${TEST_DATA} -X POST

cat > ${TEST_DATA} <<EOF
id,name,value
,bar,0
,bar,1
,bar,2
,bar,3
,bar,4
,bar,
,baz,0
,baz,1
,baz,2
,baz,3
,baz,4
,baz,
,foo,0
,foo,1
,foo,2
,foo,3
,foo,4
,foo,
,,5
,,
EOF
dotest "200::*::*" "/catalog/${cid}/entity/pagedata?defaults=id" -H "Content-Type: text/csv" -T ${TEST_DATA} -X POST

dopagetest_typed()
{
    mime_type="$1"
    expected_rows=$2
    shift 2
    dotest "$@" -H "Accept: ${mime_type}"
    offset=0
    if [[ "${mime_type}" = text/csv ]]
    then
	offset=1
    fi
    got_rows=$(( $(wc -l < ${RESPONSE_CONTENT} ) - $offset )) # minus one for CSV header
    [[ ${got_rows} -eq -1 ]] && got_rows=0 # ERMrest skips CSV header on empty result set!
    [[ "${mime_type}" = "application/json" ]] && grep -q '^\[\]$' ${RESPONSE_CONTENT} && got_rows=0 # empty array
    if [[ ${expected_rows} -ne ${got_rows} ]]
    then
	cat <<EOF
FAILED: result row count ${got_rows} does not match expected ${expected_rows} for $@

$(cat ${RESPONSE_CONTENT})
EOF
	NUM_FAILURES=$(( ${NUM_FAILURES} + 1 ))
    elif [[ "$VERBOSE" = "true" ]] || [[ "$VERBOSE" = "brief" ]]
    then
	cat <<EOF
TEST $(( ${NUM_TESTS} + 1 )) OK: row count ${got_rows} matches expected ${expected_rows}
EOF
    fi
    NUM_TESTS=$(( ${NUM_TESTS} + 1 ))
}

dopagetest()
{
    dopagetest_typed text/csv "$@"
    dopagetest_typed application/x-json-stream "$@"
    dopagetest_typed application/json "$@"
}

# different API forms that denote the same essential entity result set
# to tickle different code paths
for query in "/catalog/${cid}/entity/pagedata" \
		 "/catalog/${cid}/attribute/pagedata/id,name,value" \
		 "/catalog/${cid}/attributegroup/pagedata/id;name,value" \
		 "/catalog/${cid}/attributegroup/pagedata/id;name,value,c:=cnt(*)"
do
    # valid page key syntax
    dopagetest 20 "200::*::*" "${query}@sort(name,value)@after(,4)"
    dopagetest 16 "200::*::*" "${query}@sort(name,value)@after(bar,3)"
    dopagetest 14 "200::*::*" "${query}@sort(name,value)@after(bar,::null::)"
    dopagetest  0 "200::*::*" "${query}@sort(name,value)@after(::null::,::null::)"
    dopagetest  2 "200::*::*" "${query}@sort(value,id)@after(::null::,12)"

    dopagetest  0 "200::*::*" "${query}@sort(name,value)@before(,4)?limit=50"
    dopagetest  3 "200::*::*" "${query}@sort(name,value)@before(bar,3)?limit=50"
    dopagetest  5 "200::*::*" "${query}@sort(name,value)@before(bar,::null::)?limit=50"
    dopagetest 19 "200::*::*" "${query}@sort(name,value)@before(::null::,::null::)?limit=50"
    dopagetest 17 "200::*::*" "${query}@sort(value,id)@before(::null::,12)?limit=50"
done

for query in "/catalog/${cid}/entity/pagedata" \
		 "/catalog/${cid}/attribute/pagedata/id,name,value" \
		 "/catalog/${cid}/attributegroup/pagedata/id;name,value" \
		 "/catalog/${cid}/attributegroup/pagedata/id;name,value,c:=cnt(*)" \
		 "/catalog/${cid}/aggregate/pagedata/id:=cnt(id),name:=cnt(name),value:=cnt(*)"
do
    # invalid page key syntax
    dotest "400::*::*" "${query}@after(bar)"
    dotest "400::*::*" "${query}@before(bar)"
    dotest "400::*::*" "${query}@sort(name,value)@after(bar)"
    dotest "400::*::*" "${query}@sort(name,value)@before(bar)"
done

# even valid page key syntax not allowed on aggregates
query="/catalog/${cid}/aggregate/pagedata/id:=cnt(id),name:=cnt(name),value:=cnt(*)"
dotest "400::*::*" "${query}@sort(name,value)@after(,4)"
dotest "400::*::*" "${query}@sort(name,value)@after(bar,3)"
dotest "400::*::*" "${query}@sort(name,value)@after(bar,::null::)"
dotest "400::*::*" "${query}@sort(name,value)@after(::null::,::null::)"

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
