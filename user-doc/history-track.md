
# ERMrest History Tracking

**NOTE**: The majority of interface documentation previously found
here has been integrated into the [API docs](../api-docs/index.md). The corresponding 
content here has been removed to avoid any confusion for future editors.

This document summarizes the architectural concepts and implications
that might impact a DBA or developer looking at the backend
functionality or interacting with the catalog DB.

## Overview of Design

1. We now use timestamps as catalog version IDs instead of PostgreSQL transaction IDs
   - All writes by ERMrest use *serializable* isolation level
   - Timestamps are stable across dump/restore events
   - The system clock must be monotonically increasing (even across dump/restore events)
   - These can appear in URL for historical query and in ETag content for cache management
2. The introspected catalog model is reified in tables managed by ERMrest
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
3. We add an internal `_ermrest_history` schema to each catalog
4. We add internal tables to `_ermrest_history` corresponding to other tables in catalog
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
5. We add triggers to automate data management
   - One trigger *before* insert or update manages system column values
   - One trigger *after* insert or update tracks tuples aka versions of rows
6. The service can query historical content at a given time or live content
7. Regular mutation transactions are tracked:
   - `_ermrest.model_modified`: when any part of the model was changed and by who
   - `_ermrest.table_modified`: when individual table's content was changed and by who
8. Most recent transactions are tracked for quickly determining *current* version of catalog:
   - `_ermrest.model_last_modified`: when any part of the model was last changed and by who
   - `_ermrest.table_last_modified`: when individual table's content was last changed and by who

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
    
## Future Work?

### Indexing of history

### Something view-like which is compatible with history

### Audit UX support

### Asynchronous change-monitoring support

### Longitudinal History Retrieval

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

