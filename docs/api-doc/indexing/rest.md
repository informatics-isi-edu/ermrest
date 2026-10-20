
# Index Operations

This section is about managing indexes on the catalog's tables. The
operations for indexes on live tables and history tables are
isomorphic. However, they are described separately because of
differences in the URL structure and JSON representation.

At the time of writing, all index management operations require
ownership priveleges. Live index managment requires ownership of the
live table being indexed. History index management requires ownership
of the whole catalog.

## Live Index List Retrieval

The GET operation is used to retrieve a listing of all index sub-resources on a given table:

- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/index/`

    GET /ermrest/catalog/42/schema/schema_name/table/table_name/index/
    Host: www.example.com
    Accept: application/json

On success, the response is:

    HTTP/1.1  200 OK
    Content-Type: application/json

    [ {live index representation}, ... ]

The JSON document is an array of individual live index representations, described in the next operation.

Potential non-success status codes include:

- `401` or `403` when the client is not authorized to discover indexes

## Live Index Retrieval

The GET operation is used to retrieve a specific named index sub-resource on a given table:

- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/index/` _index name_

    GET /ermrest/catalog/42/schema/schema_name/table/table_name/index/
    Host: www.example.com
    Accept: application/json

On success, the response is:

    HTTP/1.1  200 OK
    Content-Type: application/json

    {live index representation}

Potential non-success status codes include:

- `404` when the named index does not exist on the table
- `401` or `403` when the client is not authorized to retrieve indexes

The _live index representation_ is a JSON object with several fields:

- `"schemaname"`: The same _schema name_ as in the URL.
- `"indexname"`: The same _index name_ as in the URL.
- `"primary"`: A boolean `true` when the index is a primary key index.
- `"unique"`: A boolean `true` when the index is a unique index.
- `"exclusion"`: A boolean `true` when the index is an exclusion index.
- `"sqldef"`: A string containing a SQL DDL definition for the index.

## Live Index Creation

The PUT operation is used to construct a named index on a given table:

- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/index/` _index name_

    PUT /ermrest/catalog/42/schema/schema_name/table/table_name/index/index_name
    Host: www.example.com
    Accept: application/json
    Content-Type: application/json

    {
      _index type_: _live table indexing preference_
    }

The input representation is a JSON document at a different level of abstraction than the resulting index representation seen with GET. This difference is for safety. ERMrest will generate stereotyped index DDL statements based on the input preferences, without allowing the client to inject arbitrary DDL fragments.

The input has exactly one logical field _index type_ which must be one of the supported index types from the indexing-preferences hint language. At the time of writing, supported _index type_ field names are:

- `"btree"`: Request a normal btree index.
- `"trgm"`: Request a GIN tri-gram index.
- `"gin_array"`: Request a GIN array index.

The _table indexing preference_ language is slightly different from the indexing-preferences annotation. The annotation supports a boolean which can request or suppress default index creation by the service. However, this request always requests index creation and always supplies a base column:

- A bare _column name_ string selects the base column for the default index of the requested _index type_. This corresponds to the usual `true` preference hint in the indexing-preferences annotation.
- A `[` _column name_ `,` ... `]` array selects the base column first and selects additional columns to include in a compound index. This is the same array syntax used for compound indexes in the indexing-preferences annotation.

At time of writing, the compound index preference is only valid for the btree index type.

On success, the response is:

    HTTP/1.1  200 OK
    Content-Type: application/json

    {live index representation}

The resulting _live index representation_ will be the same as appears in a GET response. It does not echo back the abstract indexing preference input.

Potential non-success status codes include:

- `400` when the input is malformed
- `409` when the input references an unknown column name
- `401` or `403` when the client is not authorized to remove the index

Semantically, the PUT operation is idempotent as the HTTP protocol requires. After successful completion, the index will exist as requested.

**WARNING 1**: Live tables exist in multiple PostgreSQL schemas, and index names exist in per-schema namespaces, corresponding to the schema containing the live table. Therefore, live index names must be unique across all live tables in the same schema. For ease of management, it is a recommended convention that all index names be prefixed as in the template `{table_name}_`, e.g. for a table name `Foo` use the prefix `Foo_` for each of its index names. Alternately, live indexes could also follow the naming scheme suggested for history indexes: `t{table_RID}_`.

**WARNING 2**: This operation is costly. If an index already exists with the same name, that index is dropped and a new index created according to the input preferences! Naive repetition of the same PUT request has negative consequences in terms of service resource consumption and performance.

## Live Index Deletion

The DELETE request is used to delete (i.e. drop) a named index on a given table:

- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/index/` _index name_

    DELETE /ermrest/catalog/42/schema/schema_name/table/table_name/index/
    Host: www.example.com

On success, the response is:

    HTTP/1.1  204 No Content

Potential non-success status codes include:

- `404` when the named index does not exist on the table
- `401` or `403` when the client is not authorized to remove the index

## History Index List Retrieval

The GET operation is used to retrieve a listing of all index sub-resources on a given history table:

- _service_ `/catalog/` _cid_ `/history/table/` _table RID_ `/index/`

    GET /ermrest/catalog/42/history/table/table_RID/index/
    Host: www.example.com
    Accept: application/json

On success, the response is:

    HTTP/1.1  200 OK
    Content-Type: application/json

    [ {history index representation}, ... ]

The JSON document is an array of individual index representations, described in the next operation.

Potential non-success status codes include:

- `401` or `403` when the client is not authorized to discover indexes

At time of writing, catalog ownership is required to discover history indexes.

## History Index Retrieval

The GET operation is used to retrieve a specific named index sub-resource on a given history table:

- _service_ `/catalog/` _cid_ `/history/table/` _table RID_ `/index/` _index name_

    GET /ermrest/catalog/42/history/table/table_RID/index/
    Host: www.example.com
    Accept: application/json

On success, the response is:

    HTTP/1.1  200 OK
    Content-Type: application/json

    {history index representation}

Potential non-success status codes include:

- `404` when the named index does not exist on the table
- `401` or `403` when the client is not authorized to retrieve indexes

At time of writing, catalog ownership is required to retrieve history indexes.

The _history index representation_ is a JSON object with several fields:

- `"indexname"`: The same _index name_ as in the URL.
- `"primary"`: A boolean `true` when the index is a primary key index.
- `"unique"`: A boolean `true` when the index is a unique index.
- `"exclusion"`: A boolean `true` when the index is an exclusion index.
- `"sqldef"`: A string containing a SQL DDL definition for the index.

**NOTE**: while live index names are schema-qualified by the same
  schema as their target table, history index names all exist in a
  single, flat namespace corresponding to the database schema where
  ERMrest places all history tables.

## History Index Creation

The PUT operation is used to construct a named index on a given history table:

- _service_ `/catalog/` _cid_ `/history/table/` _table RID_ `/index/` _index name_

    PUT /ermrest/catalog/42/history/table/table_RID/index/index_name
    Host: www.example.com
    Accept: application/json
    Content-Type: application/json

    {
      _index type_: _history table indexing preference_
    }

The input representation is a JSON document at a different level of abstraction than the resulting index representation seen with GET. This difference is for safety. ERMrest will generate stereotyped index DDL statements based on the input preferences, without allowing the client to inject arbitrary DDL fragments.

The input has exactly one logical field _index type_ which must be one of the supported index types from the indexing-preferences hint language. At the time of writing, supported _index type_ field names are:

- `"btree"`: Request a normal btree index.
- `"trgm"`: Request a GIN tri-gram index.
- `"gin_array"`: Request a GIN array index.

The _history table indexing preference_ language is slightly different from the _live table indexing preference_ language. It references columns by RID rather than by name:

- A bare _column RID_ string selects the base column for the default index of the requested _index type_. This corresponds to the usual `true` preference hint in the indexing-preferences annotation.
- A `[` _column RID_ `,` ... `]` array selects the base column first and selects additional columns to include in a compound index. This is ismorphic to the array syntax used for compound indexes in the indexing-preferences annotation, but referencing columns by RID rather than by name.

At time of writing, the compound index preference is only valid for the btree index type.

On success, the response is:

    HTTP/1.1  200 OK
    Content-Type: application/json

    {history index representation}

The resulting _history index representation_ will be the same as appears in a GET response. It does not echo back the abstract indexing preference input.

Potential non-success status codes include:

- `400` when the input is malformed
- `409` when the input references an unknown column name
- `401` or `403` when the client is not authorized to remove the index

Semantically, the PUT operation is idempotent as the HTTP protocol requires. After successful completion, the index will exist as requested.

**WARNING 1**: All history tables exist in the same PostgreSQL schema, and therefore all index names exist in one flat namespace, corresponding to that schema. Therefore, history index names must be unique across all history tables regardless of how their corresponding live tables may be organized into different schemas. For ease of management, it is a recommended convention that all index names be prefixed as in the template `t{table_RID}_`, e.g. for a table RID `10-1234` use the prefix `t10-1234_` for each of its index names.

**WARNING 2**: This operation is costly. If an index already exists with the same name, that index is dropped and a new index created according to the input preferences! Naive repetition of the same PUT request has negative consequences in terms of service resource consumption and performance.

## History Index Deletion

The DELETE request is used to delete (i.e. drop) a named index on a given history table:

- _service_ `/catalog/` _cid_ `/schema/history/table/` _table RID_ `/index/` _index name_

    DELETE /ermrest/catalog/42/history/table/table_RID/index/
    Host: www.example.com

On success, the response is:

    HTTP/1.1  204 No Content

Potential non-success status codes include:

- `404` when the named index does not exist on the table
- `401` or `403` when the client is not authorized to remove the index

