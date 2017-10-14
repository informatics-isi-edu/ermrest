
# ERMrest History Tracking

There is experimental support for history-tracking in ERMrest. This
feature is a work in progress and requires REST API extensions before
it is fully realized.

This document summarizes the architectural concepts and implications
that might impact a DBA or developer looking at the backend
functionality or interacting with the catalog DB.

Implementation Status:

- [x] System columns support
- [x] Stateful model with `RID` for each element
- [x] Historical tuple storage for stateful model tables
- [x] Historical tuple storage for user-defined tables
- [x] Introspection mechanism for model at revision instead of latest model
- [x] REST URL structure for access at revision
- [x] Revision timestamp normalization (fit URL param to discrete events in history)
- [x] Read-only model introspection at revision
- [x] Read-only data query at revision
- [x] Appropriate errors reject write access at revision
- [x] Appropriate errors to reject historical access to non-tracked tables or views
- [x] Caching of historical models in Python
- [x] Change snapshot time format to URL-safe character string instead of human-readable timestamp text
- [x] Historical ACL amendment
- [x] Historical ACL binding amendment
- [x] Historical annotation amendment
- [x] Historical single attribute redaction
- [x] Historical single attribute redaction with basic filtering
- [x] Catalog history truncation

Future work requiring more investigation:

- Index acceleration of historical tuple queries?
- Replacement for SQL views which supports history
- Audit UX support
- Asynchronous change-monitoring support

## Overview of Design

1. The design depends heavily on new _system columns_ used throughout:
   - `RID` a numeric resource or row ID as primary key
   - `RMT` row modification timestamp
   - `RMB` row modified by client ID
   - `RCT` row creation timestamp
   - `RCB` row created by client ID
2. We now use timestamps as catalog version IDs instead of PostgreSQL transaction IDs
   - All writes by ERMrest use *serializable* isolation level
   - Timestamps are stable across dump/restore events
   - The system clock must be monotonically increasing (even across dump/restore events)
   - These can appear in URL for historical query and in ETag content for cache management
3. The introspected catalog model is reified in tables managed by ERMrest
   - These tables assign persistent `RID` and other system columns to PostgreSQL model elements
   - `RID` assignments are stable across dump/restore events
   - Runtime introspection can dump the state of these tables quickly
   - Runtime model changes incrementally adjust these tables
   - Stored procedures can update these tables for en masse model changes by a local DBA
      - One procedure syncs by OID for incremental changes including model element renaming
      - One procedure syncs by name for OID instability including dump/restore or DBA-driven replacement of model elements
   - All model-augmenting tables are refactored in terms of `RID` subjects instead of various composite keys
      - Annotations
      - ACLs
      - ACL bindings
4. We add an internal `_ermrest_history` schema to each catalog
5. We add internal tables to `_ermrest_history` corresponding to other tables in catalog
   - History tables track tuple content generically
      - keyed by composite (`RID`, `during`)
      - `RID` corresponds to the same `RID` from the tracked table
      - `during` is an interval `[RMT1,NULL)` when tuples are born or `[RMT1,RMT2)` when tuples have already died
      - `RMB` corresponds to the same `RMB` from the tracked table (in case we want to show changes by client later...)
   - System tables from `_ermrest` are mapped in a simplified fashion by name to allow bootstrapping
      - Table `_ermrest_history.foo` tracks table `_ermrest.foo`
      - Tuple data is stored in a JSON blob with field `X` tracking column with name `X`
   - User tables from other schemas are mapped in a generic fashion by `RID`
      - Table `_ermrest_history.tXYZ` tracks table with `RID` `XYZ`
      - Tuple data is stored in a JSON blob with field `ABC` tracking a column with `RID` `ABC`
      - System columns `RID`, `RMT`, and `RMB` are lifted out of the JSON blob
6. We add triggers to automate data management
   - One trigger *before* insert or update manages system column values
   - One trigger *after* insert or update tracks tuples aka versions of rows
7. The service can query historical content at a given time or live content
8. Regular mutation transactions are tracked:
   - `_ermrest.model_modified`: when any part of the model was changed and by who
   - `_ermrest.table_modified`: when individual table's content was changed and by who
9. Most recent transactions are tracked for quickly determining *current* version of catalog:
   - `_ermrest.model_last_modified`: when any part of the model was last changed and by who
   - `_ermrest.table_last_modified`: when individual table's content was last changed and by who

## Historical Catalog Access REST API

Historical access is defined in terms of a timestamp _revision_:

- /ermrest/catalog/N
- /ermrest/catalog/N@revision

where _revision_ is an implementation-defined snapshot
identifier. Each whole schema document will also gain a new `snaptime`
attribute at the top level to specify the effective revision 
for the model it describes.

Currently, we are using a base-32 string representing full
microseconds since "epoch" time. This may change before we complete
this work. An example is `2NP-XR15-7BY6` which corresponds to
`2017-10-13 17:39:22.308579-07`.

The first URL form continues to denote the live, mutable catalog and
all its subresources used for query end editing. The second,
_revision_ qualified, URL denotes a read-only snapshot of the catalog.

Aside from the new `@revision` syntax in the URL, the entire read-only
catalog data API should work as before. Instead of returning a
description of the current, live catalog content, they would instead
return a description of the content as it appeared at the _revision_
time in the past.

Limitation: if history capture is disabled for a particular table in
the catalog, it will be invisible in the _revision_ qualified catalog
snapshots. This means it will not appear in the historic model and 
cannot be queried for historical results.

All SQL views exposed as tables will lack history collection. Any
table lacking the core system columns `RID`, `RMB`, and `RMT` will
lack history collection.  In future implementations, history
collection MAY be disabled on individual tables as a local policy
decision, even if they would otherwise support history collection.

## Accessing Data History within SQL

To access historical data for a history-tracked table with table
`RID`=`T1` and column `RID`=(`C1`, `C2`, ... `Ck`) at timestamp `V1`,
we can use a query similar to this:

    SELECT
      t."RID" AS "RID",
      d."Cx" AS "RCT",
      lower(t.during) AS "RMT",
      d."Cy" AS "RMT",
      t."RMB",
      d."C1" AS "Column name 1",
      d."C2" AS "Column name 2",
      ...
      d."Ck" AS "Column name k"
    FROM _ermrest_history.tT1 t,
    LATERAL jsonb_to_record(t.rowdata) d("C1" type1, "C2" type2, ... "Ck" typek)
    WHERE t.during @> V1::timestamptz;

This approach allows us to handle three difference scenarios that can
occur during the history of the user data table:

1. A new column added after the table acquires data can implicitly add
   columns with `NULL` value without generating new storage
   tuples. The expansion of the JSON `rowdata` blob will fill in the
   missing NULL values.
2. An existing column deleted after the table acquires data can
   implicitly drop columns without generating new storage tuples. The
   expansion of the JSON `rowdata` blob will ignore extra values.
3. Renaming an existing column after the table acquires data can
   implicitly rename fields without generating new storage tuples. The
   expansion of the JSON `rowdata` blob will map the persistent
   column-level `RID` to the currently active column name.

### Special-case Handling of JSON

The preceding example to query a user data history table is sufficient
for basic column types like integers, text, and
numbers. Unfortunately, the PostgreSQL JSON support has some
asymmetries and requires special case handling of those columns. We
can pack them into the `rowdata` JSON blobs using a generic method in
our history-tracking trigger functions, but we must unpack them
differently:

    SELECT
      t."RID" AS "RID",
      d."Cx" AS "RCT",
      lower(t.during) AS "RMT",
      d."Cy" AS "RMT",
      t."RMB",
      d."C1" AS "Column name 1",
      t.rowdata->"C2" AS "Column name 2", -- json or jsonb column extraction
      ...
      d."Ck" AS "Column name k"
    FROM _ermrest_history.tT1 t,
    LATERAL jsonb_to_record(t.rowdata) d("C1" type1, "C3" type3, ... "Ck" typek)
    WHERE t.during @> V1::timestamptz;

This example differs only in the extraction of the `C2` field. The
`jsonb_to_record()` procedure would fail to round-trip the JSON
value. Instead, we explicitly project that value directly from the raw
`rowdata` blob while using the procedure to structure the other
non-JSON values.

## Accessing Model History within SQL

As implied by the preceding, we need to be able to reconstruct the
table definition which was in effect at the time of the data revision
we wish to query. We do this by making the same sort of query to
history-tracking tables for the reified model storage. Model history
tracking tables use their actual table and column names instead of
being indirected through RIDs, because we know ERMrest will not rename
these features over time.

For convenience, we've wrapped these introspection queries into stored
procedures parameterized by the catalog version timestamp.

    -- raw introspection example w/o history awareness
    SELECT * FROM _ermrest.known_tables;
    
    -- equivalent introspection example w/ history awareness
    SELECT * FROM _ermrest.known_tables(V1::timestamptz);
    
## Writable History

To support history tracking for production use, we need to
introduce new REST API features. History amendment means revising the
apparent historical content of the catalog so that subsequent access to
a particular historical snapshot will return different results:

1. Amend historical ACLs (replace ACLs).
   - Correct an erroneous ACL to patch an information leak of historical data
   - Adjust historical access rules due to organizational policy changes
2. Amend historical dynamic ACL bindings (replace ACL bindings).
   - (same motivations as for ACL amendment above)
3. Amend historical model annotations (replace annotations).
   - Correct erroneous presentation hints for historical model
   - Enhance presentation hints to support newer client software capabilities
4. Redact historical attributes (set fields to NULL for some or all rows).
   - Purge sensitive values which should not have been stored
   - Retain the other non-sensitive tuple info and identifiers as a "tombstone"
5. Truncate history (discard oldest history for some or all tables/rows).
   - Implement data retention policies which limit the storage horizon
   - Reclaim storage space

Pragmatically, we want operations on history to be flexible and
efficient:

- Bulk interfaces to operate over *time spans* rather than only amending a single revision at a time.
- Generic interfaces to amend history spans that cross model change boundaries.

As a common resource space for longitudinal history manipulation APIs, we
introduce:

    /ermrest/catalog/N/history/from,until

Unlike the read-only catalog snapshots, this resource space denotes a
longitudinal history of the catalog starting at a _from_ revision
(inclusive) and bounded by an _until_ revision (exclusive). Either or
both of _from_ and _until_ MAY be the empty string to represent a
half-open or fully open interval of history. However, for history
amendment, the effective _until_ boundary MUST be clamped by the
implementation to only affect *dead* storage. In other words, 
history amendment operation cannot affect *live* catalog state.

This resource space MAY be extended to support more interesting use
cases in the future. For now, only a minimal feature set is specified.

### Amend Historical ACLs

A collection of ACL resources can be mutated over a *time span*:

    PUT /ermrest/catalog/N/history/from,until/acl
    Content-Type: application/json
    
    {aclname: members, ...}

The effect of this operation will be to destructively overwrite the
effective ACLs for all revisions whose lifetimes are wholly enclosed
within the time span.

A similar operation is possible for each different ACL subjects 
by including the RID of the subject:

- catalog: `/ermrest/catalog/N/history/from,until/acl`
- model element: `/ermrest/catalog/N/history/from,until/acl/RID`
   - schema RID
   - table RID
   - column RID
   - foreign key RID

### Amend Historical ACL Bindings

A collection of ACL binding resources can be mutated over a *time span*:

    PUT /ermrest/catalog/N/history/from,until/RID/acl_binding
    Content-Type: application/json
    
    {bindingname: binding, ...}

The effect of this operation will be to destructively overwrite the
effective ACL bindings for all revisions whose lifetimes are wholly
enclosed within the time span.

A similar operation is possible for each different type of ACL binding
subject resource, just supplying the appropriate RID for the model
element subject to the ACL.

### Amend Historical Annotations

A collection of annotation resources can be mutated over a *time span*:

    PUT /ermrest/catalog/N/history/from,until/annotation
    Content-Type: application/json
    
    {key: annotation_value, ...}

The effect of this operation will be to destructively overwrite the
effective annotations for all revisions whose lifetimes are wholly
enclosed within the time span.

A similar operation is possible for each different type of annotation
subject by including the RID of the subject:

- catalog: `/ermrest/catalog/N/history/from,until/annotation`
- model element: `/ermrest/catalog/N/history/from,until/annotation/RID`
   - schema RID
   - table RID
   - column RID
   - key RID
   - foreign key RID

### Redact Historical Attributes

Specific attributes can be redacted over a *time span*:

    DELETE /ermrest/catalog/N/history/from,until/attribute/CRID

The effect of this operation is to redact (set NULL) all values of the
column whose RID is _CRID_ for all tuple revisions whose lifetimes are
wholly enclosed within the time span. The enclosing table is implicit
because _CRID_ uniquely identifies one column within the whole model.

More selective redaction can be made by a limited filter syntax:

    DELETE /ermrest/catalog/N/history/from,until/attribute/CRID/FRID=X

Here, only tuples with the given filter column whose RID is _FRID_
matches a given value _X_ are redacted.  More rich filtering syntax
may be considered in future enhancements to ERMrest. This syntax is
sufficient to target one row by its actual `RID` or all rows with a
certain *bad value* _X_ in the column being redacted.

### Find Current History Span

A simple GET request can discover the shape of history:

    GET /ermrest/catalog/N/history/,

this will return a summary of the stored history timeline in
a JSON document such as:

    {
      "amendver": a,
      "snaprange": [
        t0, t1
      ]
    }

where the two timepoints _t0_ and _t1_ represent the earliest and latest
historical snaptimes known in the system. Any value in that range MAY be used
as an _until_ boundary for the history truncation mechanism described next. The
amendment version _a_ may be `null` or a timepoint representing the latest
known amendment of that range.

A narrower boundary can also be queried to find out whether that particular
range of history has been amended:

    GET /ermrest/catalog/N/history/from,until
	
this will return a similar response but the `snaprange` and `amendver` fields
will only describe history within the requested range.

### Truncate Catalog History

A single, bulk request can irreversibly truncate catalog history:

    DELETE /ermrest/catalog/N/history/,until

All historical model and data content with a death time before or
equal to the _until_ time will be discarded. This can be used to
implement a data retention horizon and to reclaim storage resources.

### Longitudinal History Retrieval

(Possible future extension...)

Do we want to retrieve existing versions within a time range? These
would be collective resources providing an array of documents with
their own `[from,until)` intervals which chain together to span the
whole range of the request. Each document would have its own
configuration content.

- `GET /ermrest/catalog/N/history/from,until/acl/RID`
   - Content example: `{"from": T1, "until": T2, "acls": {aclname: members, ...}}`
- `GET /ermrest/catalog/N/history/from,until/acl_binding/RID`
   - Content example: `{"from": T1, "until": T2, "acl_bindings": {bindingname: binding, ...}}`
- `GET /ermrest/catalog/N/history/from,until/annotation/RID`
   - Content example: `{"from": T1, "until": T2, "annotations": {key: annotation_value, ...}}`
- `GET /ermrest/catalog/N/history/from,until/attribute/CRID/FRID=X`
   - Content example: `{"from": T1, "until": T2, "tuple": {CRID: Y}}`
- `GET /ermrest/catalog/N/history/from,until/entity/TRID/FRID=X`
   - Content example: `{"from": T1, "until": T2, "tuple": {CRID: value, ...}}`

