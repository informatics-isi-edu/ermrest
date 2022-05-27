# Model Operations

The model operations configure the entity-relationship model that will be used to structure tabular data in the [ERMrest](http://github.com/informatics-isi-edu/ermrest) catalog.  The model must be configured before use, but it may continue to be adjusted throughout the lifecycle of the catalog, interleaved with data operations.

## Schemata Retrieval

The GET operation is used to retrieve a document describing the entire catalog data model using
a model-level resource name of the form:

- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema`
- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/`

In this operation, content-negotiation SHOULD be used to select the `application/json` representation as other content types MAY be returned, including HTML-based user interfaces:

    GET /ermrest/catalog/42/schema HTTP/1.1
	Host: www.example.com
	Accept: application/json

On success, the response is:

    HTTP/1.1 200 OK
	Content-Type: application/json
    
    {
      "schemas": {
	    schema name: schema representation, ...
      }
    }

Note, this JSON document is usually quite long and too verbose to show verbatim in this documentation. Its general structure is a single field `schemas` which in turn is a sub-object used as a dictionary mapping. Each field name of the sub-object is a _schema name_ and its corresponding value is a _schema representation_ as described in [Schema Retrieval](#schema-retrieval).

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

## Bulk Schemata and Table Creation

The POST operation can be used to create multiple named schemata and/or tables in a single request by posting a complex JSON document to the same resource used for retrieving all schemata:

- _service_ `/catalog/` _cid_ `/schema`

In this operation, `application/json` content MUST be provided. The same format returned in schemata retrieval is supported:

    POST /ermrest/catalog/42/schema HTTP/1.1
	Host: www.example.com
	Content-Type: application/json

    {
	  "schemas": {
	    schema name: schema representation, ...
	  }
	}

with this form, each _schema name_ MUST be distinct and available for use as a new schema in the catalog. Each _schema representation_ MAY include multiple fields as described in the [Schema Retrieval](#schema-retrieval) documentation. If present, the `"schema_name"` field MUST match the _schema name_ key of the enclosing document. If present, the `"tables"` field MAY describe new tables which will also be created as part of the same request.

Optionally, a batch request list document is also supported:

    POST /ermrest/catalog/42/schema HTTP/1.1
	Host: www.example.com
	Content-Type: application/json
    
    [
	   schema, table, or foreign-key representation, ...
	]
	
In this form, each _schema representation_, _table representation_,  or _foreign key representation_ is handled similarly to the [Schema Creation](#schema-creation), [Table Creation](#table-creation), or [Foreign Key Creation](#foreign-key-creation) APIs, respectively. The list of representations are processed in document order, and embedded sub-resources are also created.  With both forms, a set of tables with interdependent foreign key constraints MAY be specified and the service will defer all foreign key definitions until after all tables and keys have been defined.

On success, the response is:

    HTTP/1.1 201 Created
	Content-Type: application/json
	
	...new resource representation...
	
Typical error response codes include:
- 400 Bad Request
- 403 Forbidden
- 409 Conflict
- 401 Unauthorized

The request effects are atomic, either applying all elements of the batch change to the catalog model or making no changes at all in the case of failures.

## Schema Creation

The POST operation is used to create new, empty schemata, using a model-level resource name of the form:

- _service_ `/catalog/` _cid_ `/schema/` _schema name_

In this operation, no input is required:

    POST /ermrest/catalog/42/schema/schema_name HTTP/1.1
	Host: www.example.com

On success, the response is:

    HTTP/1.1 201 Created

BUG: should be 204 No Content and/or should include Location header for new schema?

Typical error response codes include:
- 409 Conflict
- 403 Forbidden
- 401 Unauthorized

## Schema Retrieval

The GET operation is used to retrieve a document describing the one schema in the data model using
a model-level resource name of the form:

- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_

In this operation, content-negotiation SHOULD be used to select the `application/json` representation:

    GET /ermrest/catalog/42/schema/schema_name HTTP/1.1
	Host: www.example.com
	Accept: application/json

On success, the response is:

    HTTP/1.1 200 OK
	Content-Type: application/json
    
    {
      "schema_name": schema name,
      "comment": comment,
	  "annotations": {
	     annotation key: annotation document, ...
	  }
      "tables": {
         table name: table representation, ...
      }
    }

Note, this JSON document is usually quite long and too verbose to show verbatim in this documentation. Its general structure is a single object with the following fields:

- `schema_name`: whose value is the _schema name_ addressed in the retrieval request
- `comment`: whose value is a human-readable _comment_ for the schema
- `annotations`: whose value is a sub-object use as a dictionary where each field of the sub-object is an _annotation key_ and its corresponding value a nested object structure representing the _annotation document_ content (as hierarchical content, not as a double-serialized JSON string!)
- `tables`: which is a sub-object used as a dictionary mapping. Each field name of the sub-object is a _table name_ and its corresponding value is a _table representation_ as described in [Table Creation](#table-creation).

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

## Schema Alteration

The PUT operation is used to alter an existing schema's definition:

- _service_ `/catalog/` _cid_ `/schema/` _schema name_

In this operation, the `application/json` _schema representation_ is supplied as input:

    PUT /ermrest/catalog/42/schema/schema_name HTTP/1.1
	Host: www.example.com
	Content-Type: application/json

    {
      "schema_name": new schema name,
      "comment": new column comment,
      "annotations": {
        annotation key: annotation document, ...
      }
    }

The input _schema representation_ is as for schema creation via the POST request. Instead of creating a new schema, the existing schema with _schema name_ as specified in the URL is altered to match the input representation. Each of these fields, if present, will be processed as a target configuration for that aspect of the table definition:

- `schema_name`: a new schema name to support renaming from _schema name_ to _new schema name_
- `comment`: a new comment string
- `annotations`: a replacement annotation map
- `acls`: a replacement ACL set

Other schema fields are immutable through this interface, and such input fields will be ignored.

Absence of a named field indicates that the existing state for that aspect of the definition should be retained without change. For example, an input to rename a schema and set a comment would look like:

    {
      "schema_name": "the new name",
      "comment": "This is my new named table."
    }

On success, the response is:

    HTTP/1.1 200 OK
	Content-Type: application/json

    schema representation

where the body content represents the schema status at the end of the request.

*NOTE*: In the case that the schema name is changed, the returned document will indicate the new name, and subsequent access to the model resource will require using the updated URL:

- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _new schema name_

The old URL will immediately start responding with a schema not found error.

Typical error response codes include:
- 400 Bad Request
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

## Schema Deletion

The DELETE method is used to delete a schema:

    DELETE /ermrest/catalog/42/schema/schema_name HTTP/1.1
    Host: www.example.com
    
On success, this request yields a description:

    HTTP/1.1 204 No Content

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

## Table List Retrieval

The GET operation is used to retrieve a list of tables in one schema using
a model-level resource name of the form:

- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table`
- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/`

In this operation, content-negotiation SHOULD be used to select the `application/json` representation as other content types MAY be returned, including HTML-based user interfaces:

    GET /ermrest/catalog/42/schema/schema_name/table HTTP/1.1
	Host: www.example.com
	Accept: application/json

On success, the response is:

    HTTP/1.1 200 OK
	Content-Type: application/json
    
    [
	  table representation, ...
    ]

Note, this JSON document is usually quite long and too verbose to show verbatim in this documentation. Its general structure is an array where each element is a _table representation_ as described in [Table Creation](#table-creation).

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

## Table Creation

The POST operation is used to add a table to an existing schema's table list resource:

- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table`
- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/`

In this operation, the `application/json` _table representation_ is supplied as input:

    POST /ermrest/catalog/42/schema/schema_name/table HTTP/1.1
	Host: www.example.com
	Content-Type: application/json

    {
      "schema_name": schema name,
      "table_name": table name,
	  "comment": table comment,
	  "annotations": {
	    annotation key: annotation document, ...
	  },
	  "column_definitions": [ column representation, ... ],
	  "keys": [ key representation, ... ],
	  "foreign_keys": [ foreign key representation, ... ],
	  "kind": "table"
    }

The input _table representation_ is a long JSON document too verbose to show verbatim in this documentation. Its general structure is a single object with the following fields:

- `schema_name`: whose value is the same _schema name_ addressed in the request URL (optional content in this request)
- `table_name`: whose value is the _table name_ string for the new table
- `comment`: whose value is the human-readable comment string for the new table
- `annotations`: whose value is a sub-object use as a dictionary where each field of the sub-object is an _annotation key_ and its corresponding value a nested object structure representing the _annotation document_ content (as hierarchical content, not as a double-serialized JSON string!)
- `column_definitions`: an array of _column representation_ as described in [Column Creation](#column-creation), interpreted as an ordered list of columns
- `keys`: an array of _key representation_ as described in [Key Creation](#key-creation), interpreted as an unordered set of keys
- `foreign_keys`: an array of _foreign key representation_ as described in [Foreign Key Creation](#foreign-key-creation), interpreted as an unordered set of foreign keys
- `kind`: a string indicating the kind of table
  - normally `table` for a regular mutable table
  - the value `view` MAY be encountered when introspecting existing ERMrest catalogs which may have extended data models not created through the standard ERMrest model management interface; the `view` kind of table supports data retrieval operations but does not support data creation, update, nor deletion;
  - this mechanism MAY be used for future extension so other values SHOULD be detected and the enclosing _table representation_ ignored if a client does not know how to interpret that table kind.

On success, the response is:

    HTTP/1.1 200 OK
	Content-Type: application/json

    table representation

where the body content is the same _table representation_ as the request input content, representing the table as created. This response MAY differ from the input content. It is RECOMMENDED that the service generate a newly serialized representation of the newly created table, and this result MAY differ from the request input.

Typical error response codes include:
- 400 Bad Request
- 403 Forbidden
- 401 Unauthorized
- 409 Conflict

## Table Retrieval

The GET operation is used to retrieve a document describing one table in the data model using
a model-level resource name of the form:

- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/` _table name_

In this operation, content-negotiation SHOULD be used to select the `application/json` representation:

    GET /ermrest/catalog/42/schema/schema_name/table/table_name HTTP/1.1
	Host: www.example.com
	Accept: application/json

On success, the response is:

    HTTP/1.1 200 OK
	Content-Type: application/json
    
    table representation

The response body is a _table representation_ as described in [Table Creation](#table-creation).

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized
- 409 Conflict

## Table Alteration

The PUT operation is used to alter an existing table's definition:

- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_

In this operation, the `application/json` _table representation_ is supplied as input:

    PUT /ermrest/catalog/42/schema/schema_name/table/table_name HTTP/1.1
	Host: www.example.com
	Content-Type: application/json

    {
      "schema_name": destination schema name,
      "table_name": new table name,
      "comment": new column comment,
      "annotations": {
        annotation key: annotation document, ...
      }
    }

The input _table representation_ is as for table creation via the POST request. Instead of creating a new table, the existing table with _table name_ as specified in the URL is altered to match the input representation. Each of these fields, if present, will be processed as a target configuration for that aspect of the table definition:

- `schema_name`: an existing schema name to support moving from _schema name_ to _destination schema name_
- `table_name`: a new name to support renaming from _table name_ to _new table name_
- `comment`: a new comment string
- `annotations`: a replacement annotation map
- `acls`: a replacement ACL set
- `acl_bindings`: a replacement ACL bindings set

Other table fields are immutable through this interface, and such input fields will be ignored.

Absence of a named field indicates that the existing state for that aspect of the definition should be retained without change. For example, an input to rename a table and set a comment would look like:

    {
      "table_name": "the new name",
      "comment": "This is my new named table."
    }

On success, the response is:

    HTTP/1.1 200 OK
	Content-Type: application/json

    table representation

where the body content represents the table status at the end of the request.

*NOTE*: In the case that the table name is changed or the table is relocated to a different schema, the returned document will indicate the new names, and subsequent access to the model resource will require using the updated URL:

- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _new schema name_ `/table/` _new table name_

The old URL will immediately start responding with a table not found error.

Typical error response codes include:
- 400 Bad Request
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

## Table Deletion

The DELETE method is used to delete a table and all its content:

    DELETE /ermrest/catalog/42/schema/schema_name/table/table_name HTTP/1.1
    Host: www.example.com
    
On success, this request yields a description:

    HTTP/1.1 204 No Content

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized
- 409 Conflict

## Column List Retrieval

The GET operation is used to retrieve a list of columns in one table using
a model-level resource name of the form:

- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/` _table name_ `/column`
- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/` _table name_ `/column/`

In this operation, content-negotiation SHOULD be used to select the `application/json` representation:

    GET /ermrest/catalog/42/schema/schema_name/table/table_name/column HTTP/1.1
	Host: www.example.com
	Accept: application/json

On success, the response is:

    HTTP/1.1 200 OK
	Content-Type: application/json
    
    [
	  column representation, ...
    ]

Note, this JSON document is usually quite long and too verbose to show verbatim in this documentation. Its general structure is an array where each element is a _column representation_ as described in [Column Creation](#column-creation).

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

## Column Creation

The POST operation is used to add a column to an existing table's column list resource:

- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/column`
- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/column/`

In this operation, the `application/json` _column representation_ is supplied as input:

    POST /ermrest/catalog/42/schema/schema_name/table/table_name/column HTTP/1.1
	Host: www.example.com
	Content-Type: application/json

    {
      "name": column name,
      "type": column type,
      "default": default value,
      "nullok": boolean,
      "comment": column comment,
      "annotations": {
        annotation key: annotation document, ...
      }
    }

The input _column representation_ is a long JSON document too verbose to show verbatim in this documentation. Its general structure is a single object with the following fields:

- `name`: whose value is the _column name_ string for the new column which must be distinct from all existing columns in the table
- `type`: whose value is the _column type_ drawn from a limited set of supported types in ERMrest
- `default`: whose value is an appropriate default value consistent with the _column type_ or the JSON `null` value to indicate that NULL values should be used (the default when `default` is omitted from the _column representation_)
- `nullok`: JSON `true` if NULL values are allowed or `false` if NULL values are disallowed in this column (default `true` if this field is absent in the input column representation)
- `comment`: whose value is the human-readable comment string for the column
- `annotations`: whose value is a sub-object use as a dictionary where each field of the sub-object is an _annotation key_ and its corresponding value a nested object structure representing the _annotation document_ content (as hierarchical content, not as a double-serialized JSON string!)
- `acls`: whose value is a sub-object specifying ACLs for the new column
- `acl_bindings`: whose value is a sub-object specifying ACL bindings for the new column

On success, the response is:

    HTTP/1.1 200 OK
	Content-Type: application/json

    column representation

where the body content is the same _column representation_ as the request input content, representing the column  as created. This response MAY differ from the input content. It is RECOMMENDED that the service generate a newly serialized representation of the newly created column, and this result MAY differ from the request input.

Typical error response codes include:
- 400 Bad Request
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

## Column Indexing Preferences

During column creation, whether as modification to an existing table or as part of new table creation, a special annotation `tag:isrd.isi.edu,2018:indexing-preferences` MAY be used to supply hints which override implicit service behavior for constructing column indexes in the underlying database.  *These hints are only effective if available during column creation; they have no effect if applied to a column after it already exists in the catalog.

The indexing-preferences annotation can be applied at multiple levels of the catalog's model resource hierarchy, but only has an effect when interpreted with respect to a specific column. The purpose of annotations at other levels are to override default hints to apply in the absence of an indexing-preferences annotation on a specific column:

1. Catalog-level annotation to set default hints for columns created in all tables in that catalog;
2. Schema-level annotation to set default hints for columns created in tables in that schema;
3. Table-level annotation to set default hints for columns created in that table;
4. Column-level annotation to set hints for that column.

Furthermore, the default hints are searched from most specific to least specific model level on a key-by-key basis. Thus, the effective hints for a given column can be a blend of hints supplied at various levels if those hints are sparsely populated rather than fully specifying every sub-field within the annotation.

Example annotation payload to suppress _unnecessary_ btree indexes and GIN tri-gram indexes:

    "annotations": {
      "tag:isrd.isi.edu,2018:indexing-preferences": {
        "btree": false,
        "trgm": false
      }
    }

This could be applied to minimize index maintenance and storage costs on a catalog where search is limited or insensitive to query performance. The service will still create indexes necessary for correct function, such as btree indexes used to enforce key uniqueness and foreign key referential integrity constraints.

Example annotation payload to suppress _unnecessary_ btree indexes but enable built-in GIN tri-gram indexes which are used to accelerate regular-expression matching:

    "annotations": {
      "tag:isrd.isi.edu,2018:indexing-preferences": {
        "btree": false,
        "trgm": true
      }
    }

Example annotation payload to enable a custom btree index and to disable the built-in GIN tri-gram index for a specific column:

    "annotations": {
      "tag:isrd.isi.edu,2018:indexing-preferences": {
        "btree": [ "column1", "column2" ],
        "trgm": false
      }
    }

In practice, this would only be sensible as a column-level annotation on the column named `column1` where it is desired to accelerate search, sort, or joins not just by `column1` but by the ordered pair (`column1`, `column2`).

Example annotation payload to suppress the btree index and enable GIN tri-gram and GIN array indexing for an array-typed column:

    "annotations": {
      "tag:isrd.isi.edu,2018:indexing-preferences": {
        "btree": false,
        "trgm": true,
        "gin_array": true
      }
    }

In practice, this would be sensible as a column-level annotation where you want to accelerate `=` equality filter predicates as well as `::regexp::`/`::ciregexp::` regular-expression predicates on a column storing arrays of values.

## Column Retrieval

The GET operation is used to retrieve a document describing one column in the data model using
a model-level resource name of the form:

- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/` _table name_ `/column/` _column name_

In this operation, content-negotiation SHOULD be used to select the `application/json` representation:

    GET /ermrest/catalog/42/schema/schema_name/table/table_name/column/column_name HTTP/1.1
	Host: www.example.com
	Accept: application/json

On success, the response is:

    HTTP/1.1 200 OK
	Content-Type: application/json
    
    column representation

The response body is a _column representation_ as described in [Column Creation](#column-creation).

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

## Column Alteration

The PUT operation is used to alter an existing column's definition:

- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/column/` _column name_

In this operation, the `application/json` _column representation_ is supplied as input:

    PUT /ermrest/catalog/42/schema/schema_name/table/table_name/column/column_name HTTP/1.1
	Host: www.example.com
	Content-Type: application/json

    {
      "name": new column name,
      "type": new column type,
      "default": new default value,
      "nullok": new boolean,
      "comment": new column comment,
      "annotations": {
        annotation key: annotation document, ...
      }
    }

The input _column representation_ is as for column creation via the POST request. Instead of creating a new column, the existing column with _column name_ as specified in the URL is altered to match the input representation. Each of these fields, if present, will be processed as a target configuration for that aspect of the column definition:

- `name`: a new name to support renaming from _column name_ to _new column name_
- `type`: a new type to support changing from existing to new column type
- `default`: a new default value for future row insertions
- `nullok`: a new nullok status
- `comment`: a new comment string
- `annotations`: a replacement annotation map
- `acls`: a replacement ACL set
- `acl_bindings`: a replacement ACL bindings set

Absence of a named field indicates that the existing state for that aspect of the column definition should be retained without change. For example, an input to rename a column, disallow nulls, and set a new default value would look like:

    {
      "name": "the new name",
      "nullok": false,
      "default": "the new default value"
    }

On success, the response is:

    HTTP/1.1 200 OK
	Content-Type: application/json

    column representation

where the body content represents the column status at the end of the request.

*NOTE*: In the case that the column name is changed with the `"name": ` _new column name_ input syntax, the returned document will indicate the new name, and subsequent access to the model resource will require using the updated URL:

- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/` _table name_ `/column/` _new column name_

The old URL will immediately start responding with a column not found error.

Typical error response codes include:
- 400 Bad Request
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

## Column Deletion

The DELETE method is used to remove a column and all its content from a table:

    DELETE /ermrest/catalog/42/schema/schema_name/table/table_name/column/column_name HTTP/1.1
    Host: www.example.com
    
On success, this request yields a description:

    HTTP/1.1 204 No Content

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

## Key List Retrieval

The GET operation is used to retrieve a list of keys in one table using
a model-level resource name of the form:

- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/` _table name_ `/key`
- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/` _table name_ `/key/`

In this operation, content-negotiation SHOULD be used to select the `application/json` representation:

    GET /ermrest/catalog/42/schema/schema_name/table/table_name/key HTTP/1.1
	Host: www.example.com
	Accept: application/json

On success, the response is:

    HTTP/1.1 200 OK
	Content-Type: application/json
    
    [
	  key representation, ...
    ]

Note, this JSON document is usually quite long and too verbose to show verbatim in this documentation. Its general structure is an array where each element is a _key representation_ as described in [Key Creation](#key-creation).

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

## Key Creation

The POST operation is used to add a key constraint to an existing table's key list resource, or a pseudo-key constraint to a view's key list resource:

- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/key`
- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/key/`

In this operation, the _table name_ MAY be an existing table or view in the named schema, and the `application/json` _key representation_ is supplied as input:

    POST /ermrest/catalog/42/schema/schema_name/table/table_name/key HTTP/1.1
	Host: www.example.com
	Content-Type: application/json

    {
	  "names": [
	    [ schema name, constraint name ], ...
       ],
       "unique_columns": [ column name, ... ],
       "comment": comment,
       "annotations": {
          annotation key: annotation document, ...
       }
    }

The input _key representation_ is a JSON document with one object with the following fields:

- `names`: an array of `[` _schema name_ `,` _constraint name_ `]` pairs representing names of underlying constraints that enforce this unique key reference pattern.
- `unique_columns` has an array value listing the individual columns that comprise the composite key. The constituent columns are listed by their basic _column name_ strings.
- `comment`: whose value is the human-readable comment string for the key
- `annotations`: whose value is a sub-object use as a dictionary where each field of the sub-object is an _annotation key_ and its corresponding value a nested object structure representing the _annotation document_ content (as hierarchical content, not as a double-serialized JSON string!)

During key creation, the `names` field SHOULD have at most one name pair. Other `names` inputs MAY be ignored by the server. When the `names` field is omitted, the server MUST assign constraint names of its own choosing. In introspection, the `names` field represents the actual state of the database and MAY include generalities not controlled by the key creation API:

- ERMrest will refuse to create redundant constraints and SHOULD reject catalogs where such constraints have been defined out of band by the local DBA.
- The chosen _schema name_ for a newly created constraint MAY differ from the one requested by the client.
  - The server MAY create the constraint in the same schema as the constrained table
  - Pseudo keys are qualified by a special _schema name_ of `""` which is not a valid SQL schema name.
  - Pseudo keys MAY have an integer _constraint name_ assigned by the server.

On success, the response is:

    HTTP/1.1 200 OK
	Content-Type: application/json

    key representation

where the body content is the same _key representation_ as the request input content, representing the key as created. This response MAY differ from the input content. It is RECOMMENDED that the service generate a newly serialized representation of the newly created key, and this result MAY differ from the request input.

Typical error response codes include:
- 400 Bad Request
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

## Key Retrieval

The GET operation is used to retrieve a document describing one key in the data model using
a model-level resource name of the form:

- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/` _table name_ `/key/` _column name_ `,` ...

In this operation, content-negotiation SHOULD be used to select the `application/json` representation:

    GET /ermrest/catalog/42/schema/schema_name/table/table_name/key/column_name,... HTTP/1.1
	Host: www.example.com
	Accept: application/json

On success, the response is:

    HTTP/1.1 200 OK
	Content-Type: application/json
    
    key representation

The response body is a _key representation_ as described in [Key Creation](#key-creation).

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

## Key Alteration

The PUT operation is used to alter an existing key's definition:

- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/key/` _key columns_

In this operation, the `application/json` _key representation_ is supplied as input:

    PUT /ermrest/catalog/42/schema/schema_name/table/table_name/key/key_columns HTTP/1.1
	Host: www.example.com
	Content-Type: application/json

    {
      "names": [ [ schema name, new constraint name ] ],
      "comment": new comment,
      "annotations": {
        annotation key: annotation document, ...
      }
    }

The input _key representation_ is as for key creation via the POST request. Instead of creating a new key, the existing key with _key columns_ as specified in the URL is altered to match the input representation. Each of these fields, if present, will be processed as a target configuration for that aspect of the definition:

- `names`: the _new constraint name_, i.e. second field of first element of `names` list, is a replacement constraint name
- `comment`: a new comment string
- `annotations`: a replacement annotation map

Other key fields are immutable through this interface. The `unique_columns` field, if present, must match the _key columns_ in the URL.

Absence of a named field indicates that the existing state for that aspect of the definition should be retained without change. For example, an input to rename a key and set a comment would look like:

    {
      "names": [ ["table schema name", "the new constraint name" ] ],
      "comment": "This is my newly named key."
    }

On success, the response is:

    HTTP/1.1 200 OK
	Content-Type: application/json

    key representation

where the body content represents the key status at the end of the request.

Typical error response codes include:
- 400 Bad Request
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

## Key Deletion

The DELETE method is used to remove a key constraint from a table or a pseudo-key constraint from a view:

    DELETE /ermrest/catalog/42/schema/schema_name/table/table_name/key/column_name,... HTTP/1.1
    Host: www.example.com
    
On success, this request yields a description:

    HTTP/1.1 204 No Content

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

## Foreign Key List Retrieval

The GET operation is used to retrieve a list of foreign key references in one table using
a model-level resource name of the following forms:

- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/` _table name_ `/foreignkey` 
- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/` _table name_ `/foreignkey/` 
- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/` _table name_ `/foreignkey/` _column name_ `,` ...
- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/` _table name_ `/foreignkey/` _column name_ `,` ... `/reference`
- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/` _table name_ `/foreignkey/` _column name_ `,` ... `/reference/`
- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/` _table name_ `/foreignkey/` _column name_ `,` ... `/reference/` _table reference_

These names differ in how many constraints are applied to filter the set of retrieved foreign key references:
1. The list is always constrained to foreign keys stored in _schema name_ : _table name_
1. The list MAY be constrained by the composite foreign key _column name_ list of its constituent keys, interpreted as a set of columns
1. The list MAY be constrained by the _table reference_ of the table containing the composite key or keys referenced by the composite foreign key

In this operation, content-negotiation SHOULD be used to select the `application/json` representation:

    GET /ermrest/catalog/42/schema/schema_name/table/table_name/foreignkey HTTP/1.1
	Host: www.example.com
	Accept: application/json

On success, the response is:

    HTTP/1.1 200 OK
	Content-Type: application/json
    
    [
	  foreign key reference representation, ...
    ]

Note, this JSON document is usually quite long and too verbose to show verbatim in this documentation. Its general structure is an array where each element is a _foreign key reference representation_ as described in [Foreign Key Creation](#foreign-key-creation).

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

## Foreign Key Creation

The POST operation is used to add a foreign key reference constraint or pseudo-constraint to an existing table's or view's foreign key list resource:

- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/foreignkey`
- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/foreignkey/`

In this operation, the `application/json` _foreign key reference representation_ is supplied as input:

    POST /ermrest/catalog/42/schema/schema_name/table/table_name/foreignkey HTTP/1.1
    Host: www.example.com
    Content-Type: application/json

    {
	  "names": [
	    [ schema name, constraint name ], ...
	  ]
      "foreign_key_columns": [
        {
          "schema_name": schema name,
          "table_name": table name,
          "column_name": column name
        }, ...
      ]
      "referenced_columns": [
        {
          "schema_name": schema name,
          "table_name": table name,
          "column_name": column name
        }
      ],
      "comment": comment,
      "annotations": {
        annotation key: annotation document, ...
      },
	  "on_delete": delete action,
	  "on_update": update action
    }

The input _foreign key reference representation_ is a long JSON document too verbose to show verbatim in this documentation. Its general structure is a single object with the following fields:

- `names`: an array of `[` _schema name_ `,` _constraint name_ `]` pairs representing names of underlying constraints that enforce this foreign key reference pattern. For legacy compatibility this is a list, but it will have at most one member.
- `foreign_key_columns`: an array of column reference objects comprising the composite foreign key, each consisting of a sub-object with the fields:
   - `schema_name`: whose value is the same _schema name_ addressed in the request URL (optional content in this request)
   - `table_name`: whose value is the same _table name_ addressed in the request URL (optional content in this request)
   - `column_name`: whose value names the constituent column of the composite foreign key
- `referenced_columns`: an array of column reference objects comprising the referenced composite key, each consisting of a sub-object with the fields:
   - `schema_name`: whose value names the schema in which the referenced table resides
   - `table_name`: whose value names the referenced table
   - `column_name`: whose value names the constituent column of the referenced key
- `comment`: whose value is the human-readable comment string for the foreign key reference constraint
- `annotations`: whose value is a sub-object used as a dictionary where each field field of the sub-object is an _annotation key_ and its corresponding value a nested object structure representing the _annotation document_ content (as hierarchical content, not as a double-serialized JSON string!)
- `on_delete`: whose _delete action_ value describes what happens when the referenced entity is deleted:
   - `NO ACTION` (default) or `RESTRICT`: the reference is unchanged and an integrity violation will block the change to the referenced table. The difference between these two actions is only evident to local SQL clients who ERMrest.
   - `CASCADE`: the referencing entities will also be deleted along with the referenced entity.
   - `SET NULL`: the referencing foreign key will be set to NULL when the referenced entity disappears.
   - `SET DEFAULT`: the referencing foreign key will be set to column-level defaults when the referenced entity disappears.
- `on_Update`: whose _update action_ value describes what happens when the referenced entity's key is modified:
   - `NO ACTION` (default) or `RESTRICT`: the reference is unchanged and an integrity violation will block the change to the referenced table. The difference between these two actions is only evident to local SQL clients who ERMrest.
   - `CASCADE`: the referencing foreign key will be set to the new key value of the referenced entity.
   - `SET NULL`: the referencing foreign key will be set to NULL when the referenced key value is changed.
   - `SET DEFAULT`: the referencing foreign key will be set to column-level defaults when the referenced key value is changed.

During foreign key creation, the `names` field SHOULD have at most one name pair. Other `names` inputs MAY be ignored by the server. When the `names` field is omitted, the server MUST assign constraint names of its own choosing. In introspection, the `names` field represents the actual state of the database and MAY include generalities not controlled by the foreign key creation REST API:

- ERMrest will refuse to create redundant constraints and SHOULD reject catalogs where such constraints have been defined out of band by the local DBA.
- The chosen _schema name_ for a newly created constraint MAY differ from the one requested by the client.
  - The server MAY create the constraint in the same schema as the referencing table, regardless of client request.
  - Pseudo foreign keys are qualified by a special _schema name_ of `""` which is not a valid SQL schema name.
  - Pseudo foreign keys MAY have an integer _constraint name_ assigned by the server.

The two column arrays MUST have the same length and the order is important in that the two composite keys are mapped to one another element-by-element, so the first column of the composite foreign key refers to the first column of the composite referenced key, etc. In the `referenced_columns` list, the _schema name_ and _table name_ values MUST be identical for all referenced columns. If both referencing and referenced _table name_ refer to tables, a real constraint is created; if either referencing or referenced _table name_ refer to a view, a pseudo-constraint is created instead.

On success, the response is:

    HTTP/1.1 200 OK
	Content-Type: application/json

    foreign key reference representation

where the body content is the same _foreign key reference representation_ as the request input content, representing the constraint as created. This response MAY differ from the input content. It is RECOMMENDED that the service generate a newly serialized representation of the newly created constraint, and this result MAY differ from the request input.

Typical error response codes include:
- 400 Bad Request
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

## Foreign Key Retrieval

The GET operation is used to retrieve a document describing one foreign key constraint in the data model using a model-level resource name of the form:

- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/` _table name_ `/foreignkey/` _column name_ `,` ... `/reference/` _table reference_ `/` _key column_ `,` ...

In this operation, content-negotiation SHOULD be used to select the `application/json` representation:

    GET /ermrest/catalog/42/schema/schema_name/table/table_name/foreignkey/column_name,.../reference/table-reference/key_column,... HTTP/1.1
	Host: www.example.com
	Accept: application/json

On success, the response is:

    HTTP/1.1 200 OK
	Content-Type: application/json
    
    foreign key reference representation

The response body is a _foreign key reference representation_ as described in [Foreign Key Creation](#foreign-key-creation).

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

## Foreign Key Alteration

The PUT operation is used to alter an existing foreign key's definition:

- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/foreignkey/` _column name_ `,` ... `/reference/` _table reference_ `/` _key column_ `,` ...

In this operation, the `application/json` _key representation_ is supplied as input:

    PUT /ermrest/catalog/42/schema/schema_name/table/table_name/key/column_name,.../reference/table_referenace/key_column,... HTTP/1.1
	Host: www.example.com
	Content-Type: application/json

    [
      {
        "names": [ [ schema name, new constraint name ] ],
	"on_update": new update action,
	"on_delete": new delete action,
        "comment": new comment,
        "annotations": {
          annotation key: annotation document, ...
        }
      }
    ]

The input _foreign key reference representation_ is as for key creation via the POST request. Instead of creating a new foreign key, the existing one as specified in the URL is altered to match the input representation. To be symmetric with [foreign key retrieval](#foreign-key-retrieval), the input is a JSON array with one sub-document. Each of these object fields, if present, will be processed as a target configuration for that aspect of the definition:

- `names`: the _new constraint name_, i.e. second field of first element of `names` list, is a replacement constraint name
- `on_update`: the _new update action_, e.g. one of `NO ACTION`, `RESTRICT`, `CASCADE`, `SET DEFAULT`, `SET NULL`
- `on_delete`: the _new delete action_, e.g. one of `NO ACTION`, `RESTRICT`, `CASCADE`, `SET DEFAULT`, `SET NULL`
- `comment`: a new comment string
- `acls`: a replacement ACL configuration
- `acl_bindings`: a replacement ACL binding configuration
- `annotations`: a replacement annotation map

Other key fields are immutable through this interface.

Absence of a named field indicates that the existing state for that aspect of the definition should be retained without change. For example, an input to rename a constraint and set a comment would look like:

    {
      "names": [ ["table schema name", "the new constraint name" ] ],
      "comment": "This is my newly named key."
    }

On success, the response is:

    HTTP/1.1 200 OK
	Content-Type: application/json

    foreign key reference representation

where the body content represents the foreign key status at the end of the request.

Typical error response codes include:
- 400 Bad Request
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

## Foreign Key Deletion

The DELETE method is used to remove a foreign key constraint from a table using any of the foreign key list or foreign key resource name forms:

- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/foreignkey` 
- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/foreignkey/` 
- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/foreignkey/` _column name_ `,` ...
- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/foreignkey/` _column name_ `,` ... `/reference`
- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/foreignkey/` _column name_ `,` ... `/reference/`
- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/foreignkey/` _column name_ `,` ... `/reference/` _table reference_
- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/foreignkey/` _column name_ `,` ... `/reference/` _table reference_ `/` _key column_ `,` ...

These names differ in how many constraints are applied to filter the set of retrieved foreign key references:

1. The list is always constrained to foreign keys stored in _schema name_ : _table name_
1. The list MAY be constrained by the composite foreign key _column name_ list of its constituent keys, interpreted as a set of columns
1. The list MAY be constrained by the _table reference_ of the table containing the composite key or keys referenced by the composite foreign key
1. The list MAY be constrained by the composite referenced key _key column_ list

This example uses a completely specified foreign key constraint name:

    DELETE /ermrest/catalog/42/schema/schema_name/table/table_name/key/column_name,.../reference/table_reference/key_column,... HTTP/1.1
    Host: www.example.com
    
On success, this request yields a description:

    HTTP/1.1 204 No Content

The effect is to delete all foreign key constraints from the table matching the resource name used in the request.

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

## Annotations

Annotations are generic sub-resources available within multiple _subject_ resources. The possible _subject_ resources are:

- _service_ `/catalog/` _cid_ [ `@` _revision_ ]
- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ 
- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/` _table name_ 
- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/` _table name_ `/column/` _column name_ 
- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/` _table name_ `/key/` _column name_ `,` ... 
- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/` _table name_ `/foreignkey/` _column name_ `,` ... 

And the annotation sub-resources are named by appending `/annotation/` to the _subject_ resource as described in the following operations.

### Annotation List Retrieval

The GET operation is used to retrieve a document describing a set of annotations on one subject resource:

- _subject_ `/annotation/`

For annotation retrieval, the optional `@` _revision_ qualifier is allowed on the _cid_ of the subject.

In this operation, content-negotiation SHOULD be used to select the `application/json` representation:

    GET subject/annotation/ HTTP/1.1
	Host: www.example.com
	Accept: application/json

On success, the response is:

    HTTP/1.1 200 OK
	Content-Type: application/json
    
    {
      annotation key: annotation document, ...
    }

Its general structure is a single object containing the `annotations` dictionary from the enclosing _subject_ resource. Each field of the object is an _annotation key_ and its corresponding value is the nested _annotation document_ content.

Typical error response codes include:
- 403 Forbidden
- 401 Unauthorized

### Annotation Creation

The PUT operation is used to add or replace a single annotation:

- _subject_ `/annotation/` _annotation key_

For annotation creation, the `@` _revision_ qualifier is *not allowed* on the _cid_ of the subject.

In this operation, the `application/json` _annotation document_ is supplied as input:

    PUT subject/annotation/annotation_key HTTP/1.1
	Host: www.example.com
	Content-Type: application/json
    
    annotation document

The input _annotation document_ is a arbitrary JSON payload appropriate to the chosen _annotation key_.

On success, the response is:

    HTTP/1.1 201 Created

or:

    HTTP/1.1 200 OK

without any response body. The `200` response indicates the _annotation document_ replaces a previous one, while `201` responses indicate that a new _annotation key_ has been added to the parent resource.

Typical error response codes include:
- 403 Forbidden
- 401 Unauthorized

### Annotation Bulk Update

The PUT operation can also replace the whole annotation list at once:

- _subject_ `/annotation`

For annotation bulk update, the `@` _revision_ qualifier is *not allowed* on the _cid_ of the subject.

In this operation, the `application/json` _annotation list_ is supplied as input to specify all _annotation key_ and _annotation document_ values at once:

    PUT subject/annotation HTTP/1.1
    Host: www.example.com
    Content-Type: application/json
    
    {
      annotation key: annotation document, ...
    }

This operation completely replaces any existing annotations, including dropping any which were present under an _annotation key_ not specified in the bulk input list. This is most useful to an administrator who is intentionally clearing stale annotation content.

Typical error response codes include:
- 403 Forbidden
- 401 Unauthorized

### Annotation Retrieval

The GET operation is used to retrieve a document describing one annotation using a model-level resource name of the form:

- _subject_ `/annotation/` _annotation key_

For annotation retrieval, the optional `@` _revision_ qualifier is allowed on the _cid_ of the subject.

In this operation, content-negotiation SHOULD be used to select the `application/json` representation:

    GET subject/annotation/annotation_key HTTP/1.1
	Host: www.example.com
	Accept: application/json

On success, the response is:

    HTTP/1.1 200 OK
	Content-Type: application/json
    
    annotation document

Its general structure is a single object containing _annotation document_ content associated with _annotation key_.

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

### Annotation Deletion

The DELETE method is used to delete an annotation using a model-level resource name of the form:

- _subject_ `/annotation/` _annotation key_

For annotation deletion, the `@` _revision_ qualifier is *not allowed* on the _cid_ of the subject.

The request does not require content-negotiation since there is no response representation:

    DELETE subject/annotation/annotation_key HTTP/1.1
    Host: www.example.com
    
On success, this request yields a description:

    HTTP/1.1 204 No Content

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

## Comments

Comments are generic sub-resources available within multiple _subject_ resources. The possible _subject_ resources are:

- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ 
- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/` _table name_ 
- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/` _table name_ `/column/` _column name_ 
- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/` _table name_ `/key/` _column name_ `,` ... 
- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/` _table name_ `/foreignkey/` _column name_ `,` ... 

And the comment sub-resources are named by appending `/comment` to the _subject_ resource as described in the following operations.

### Comment Creation

The PUT operation is used to add or replace a single comment:

- _subject_ `/comment`
- _subject_ `/comment/`

For comment creation, the optional `@` _revision_ qualifier is *not allowed* on the _cid_ of the subject.

In this operation, the `text/plain` _comment text_ is supplied as input:

    POST subject/comment/ HTTP/1.1
	Host: www.example.com
	Content-Type: text/plain
    
    comment text

The input _comment text_ is a arbitrary UTF-8 text payload.

On success, the response is:

    HTTP/1.1 200 OK

without any response body.

Typical error response codes include:
- 403 Forbidden
- 401 Unauthorized

### Comment Retrieval

The GET operation is used to retrieve a document describing one comment using a model-level resource name of the form:

- _subject_ `/comment`

For comment retrieval, the optional `@` _revision_ qualifier is allowed on the _cid_ of the subject.

In this operation, content-negotiation is not necessary:

    GET subject/comment HTTP/1.1
	Host: www.example.com

On success, the response is:

    HTTP/1.1 200 OK
	Content-Type: text/plain
    
    comment text

Its general structure is raw _comment text_.

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

### Comment Deletion

The DELETE method is used to delete an comment using a model-level resource name of the form:

- _subject_ `/comment`

For comment deletion, the optional `@` _revision_ qualifier is *not allowed* on the _cid_ of the subject.

The request does not require content-negotiation since there is no response representation:

    DELETE subject/comment HTTP/1.1
    Host: www.example.com
    
On success, this request yields a description:

    HTTP/1.1 204 No Content

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

## Access Control Lists

Access control lists (ACLs) are generic sub-resources available within multiple _subject_ resources. The possible _subject_ resources are:

- _service_ `/catalog/` _cid_ [ `@` _revision_ ]
- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ 
- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/` _table name_ 
- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/` _table name_ `/column/` _column name_ 
- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/` _table name_ `/foreignkey/` _column name_ `,` ... 

And the ACL sub-resources are named by appending `/acl` to the _subject_ resource as described in the following operations.

### Access Control Lists Retrieval

The GET method is used to get a summary of all access control (ACL)
lists:

    GET subject/acl HTTP/1.1
	Host: www.example.com

On success, this request yields the ACL content as an object with one value list for each named ACL:

    HTTP/1.1 200 OK
    Content-Type: application/json
    
    {
      "owner": ["user1", "group2"],
      "select": ["*"],
      "update": [],
      "delete": [],
      "insert": [],
      "enumerate": []
    }

White-space is added above for readability. This legacy representation is likely to change in future revisions.

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

### Bulk Access Control List Update

The PUT method can be used to reconfigure all access control lists on a single _subject_ resource at once:

    PUT subject/acl HTTP/1.1
    Content-Type: application/json

    {
      "owner": ["user1", "group2"],
      "select": ["*"],
      "update": [],
      "delete": [],
      "insert": [],
      "enumerate": []
    }

The previous configuration of the _subject_ access control lists is completely replaced. When _subject_ is a whole catalog, absent ACL names are interpreted as implicitly present with value `[]`. When _subject_ is any other mode sub-resource, absent ACL names are interpreted as implicitly present with the value `null`.

On success, this request produces no content:

    204 No Content

### Access Control List Creation

The PUT method is used to set the state of a specific access control list (the `owner` ACL in this example):

    PUT subject/acl/owner HTTP/1.1
    Content-Type: application/json
    
    ["user1", "group2"]

On success, this request produces no content:

    204 No Content

### Access Control List Retrieval

The GET method is used to get the state of a specific access control list (the `owner` ACL in this example):

    GET subject/acl/owner HTTP/1.1
	Host: www.example.com

On success, this request yields the ACL content as a value list:

    HTTP/1.1 200 OK
    Content-Type: application/json
    
    ["user1", "group2"]

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

### Access Control List Deletion

The DELETE method is used to delete an access control list (the `owner` ACL in this example):

    DELETE subject/acl/owner HTTP/1.1
    Host: www.example.com

On success, this request yields an empty response:

    HTTP/1.1 204 No Content

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

## Access Control List Bindings

Access control list bindings (ACL bindings) are generic sub-resources available within multiple _subject_ resources. The possible _subject_ resources are:

- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/` _table name_ 
- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/` _table name_ `/column/` _column name_ 
- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/` _table name_ `/foreignkey/` _column name_ `,` ... 

And the ACL binding sub-resources are named by appending `/acl_binding` to the _subject_ resource as described in the following operations.

### Access Control List Bindings Retrieval

The GET method is used to get a summary of all access control list bindings:

    GET subject/acl_binding HTTP/1.1
	Host: www.example.com

On success, this request yields the ACL content as an object with one value list for each named ACL:

    HTTP/1.1 200 OK
    Content-Type: application/json
    
    {
      "my_example_binding": {
        "types": ["owner"],
        "projection": "My Owner Column",
        "projection_type": "acl"
      },
      "my_example_binding2": {
        "types": ["select"],
        "projection": [{"filter": "Is Public", "operand": true}, "Is Public"],
        "projection_type": "nonnull"
      }
    }

White-space is added above for readability. This legacy representation is likely to change in future revisions.

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

### Bulk Access Control List Binding Update

The PUT method can be used to reconfigure all access control list bindings on a single _subject_ resource at once:

    PUT subject/acl HTTP/1.1
    Content-Type: application/json

    {
      "my_example_binding": {
        "types": ["owner"],
        "projection": "My Owner Column",
        "projection_type": "acl"
      },
      "my_example_binding2": {
        "types": ["select"],
        "projection": [{"filter": "Is Public", "operand": true}, "Is Public"],
        "projection_type": "nonnull"
      }
    }

The previous configuration of access control list bindings on _subject_ is completely replaced.

On success, this request produces no content:

    204 No Content

### Access Control List Binding Creation

The PUT method is used to set the state of a specific access control list binding:

    PUT subject/acl_binding/my_example_binding HTTP/1.1
    Content-Type: application/json
    
    {
      "types": ["owner"],
      "projection": "My Owner Column",
      "projection_type": "acl"
    }

On success, this request produces no content:

    204 No Content

### Access Control List Binding Retrieval

The GET method is used to get the state of a specific access control list binding:

    GET subject/acl_binding/my_example_binding HTTP/1.1
	Host: www.example.com

On success, this request yields the ACL content as a value list:

    HTTP/1.1 200 OK
    Content-Type: application/json
    
    {
      "types": ["owner"],
      "projection": "My Owner Column",
      "projection_type": "acl"
    }

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

### Access Control List Binding Deletion

The DELETE method is used to delete an access control list binding:

    DELETE subject/acl_binding/my_example_binding HTTP/1.1
    Host: www.example.com

On success, this request yields an empty response:

    HTTP/1.1 204 No Content

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

