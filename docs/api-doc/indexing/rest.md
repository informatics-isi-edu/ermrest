
# Live Index Operations

This section is about managing indexes on the catalog's live tables.

## Index List Retrieval

The GET operation is used to retrieve a listing of all index sub-resources on a given table:

- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/index/`

    GET /ermrest/catalog/42/schema/schema_name/table/table_name/index/
    Host: www.example.com
    Accept: application/json

On success, the response is:

    HTTP/1.1  200 OK
    Content-Type: application/json

    [ {index representation}, ... ]

The JSON document is an array of individual index representations, described in the next operation.

Potential non-success status codes include:

- `401` or `403` when the client is not authorized to discover indexes

At time of writing, table ownership is required to discover indexes.

## Index Retrieval

The GET operation is used to retrieve a specific named index sub-resource on a given table:

- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/index/` _index name_

    GET /ermrest/catalog/42/schema/schema_name/table/table_name/index/
    Host: www.example.com
    Accept: application/json

On success, the response is:

    HTTP/1.1  200 OK
    Content-Type: application/json

    {index representation}

Potential non-success status codes include:

- `404` when the named index does not exist on the table
- `401` or `403` when the client is not authorized to retrieve indexes

At time of writing, table ownership is required to retrieve indexes.

The _index representation_ is a JSON object with several fields:

- `"schemaname"`: The same _schema name_ as in the URL.
- `"indexname"`: The same _index name_ as in the URL.
- `"primary"`: A boolean `true` when the index is a primary key index.
- `"unique"`: A boolean `true` when the index is a unique index.
- `"exclusion"`: A boolean `true` when the index is an exclusion index.
- `"sqldef"`: A string containing a SQL DDL definition for the index.

## Index Creation

The PUT operation is used to construct a named index on a given table:

- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/index/` _index name_

    PUT /ermrest/catalog/42/schema/schema_name/table/table_name/index/
    Host: www.example.com
    Accept: application/json
    Content-Type: application/json

    {
      _index type_: _table indexing preference_
    }

The input representation is a JSON document at a different level of abstraction than the resulting index representation seen with GET. This difference is for safety. ERMrest will generate stereotyped index DDL statements based on the input preferences, without allowing the client to inject arbitrary DDL fragments.

The input has exactly one logical field _index type_ which must be one of the supported index types from the indexing-preferences hint language. At the time of writing, supported _index type_ field names are:

- `"btree"`: Request a normal btree index.
- `"trgm"`: Request a GIN tri-gram index.
- `"gin_array"`: Request a GIN array index.

The indexing-preferences annotation is interpreted in the context of a given column and may request or suppress index creation for that column. This index creation request is scoped to a table and always requests index creation. Therefore, the _table indexing preference_ language is slightly different. It always supplies a base column:

- A bare _column name_ string selects the base column for the default index of the requested _index type_. This corresponds to the usual `true` preference hint in the indexing-preferences annotation.
- A `[` _column name_ `,` ... `]` array selects the base column first and selects additional columns to include in a compound index. This is the same array syntax used for compound indexes in the indexing-preferences annotation.

At time of writing, the compound index preference is only valid for the btree index type.

On success, the response is:

    HTTP/1.1  200 OK
    Content-Type: application/json

    {index representation}

The resulting _index representation_ will be the same as appears in a GET response. It does not echo back the abstract indexing preference input.

Potential non-success status codes include:

- `400` when the input is malformed
- `409` when the input references an unknown column name
- `401` or `403` when the client is not authorized to remove the index

Semantically, the PUT operation is idempotent as the HTTP protocol requires. After successful completion, the index will exist as requested.

**WARNING**: This operation is costly. If an index already exists with the same name, that index is dropped and a new index created according to the input preferences! Naive repetition of the same PUT request has negative consequences in terms of service resource consumption and performance.

## Index Deletion

The DELETE request is used to delete (i.e. drop) a named index on a given table:

- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/index/` _index name_

    DELETE /ermrest/catalog/42/schema/schema_name/table/table_name/index/
    Host: www.example.com

On success, the response is:

    HTTP/1.1  204 No Content

Potential non-success status codes include:

- `404` when the named index does not exist on the table
- `401` or `403` when the client is not authorized to remove the index

