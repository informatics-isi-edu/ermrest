# ERMrest Model Operations

The model operations configure the entity-relationship model that will be used to structure tabular data in the [ERMrest](http://example.com/TBD) catalog.  The model must be configured before use, but it may continue to be adjusted throughout the lifecycle of the catalog, interleaved with data operations.

## Schemata Retrieval

The GET operation is used to retrieve a document describing the entire catalog data model using
a model-level resource name of the form:

- _service_ `/catalog/` _cid_ `/schema`
- _service_ `/catalog/` _cid_ `/schema/`

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

- _service_ `/catalog/` _cid_ `/schema/` _schema name_

In this operation, content-negotiation SHOULD be used to select the `application/json` representation:

    GET /ermrest/catalog/42/schema/schema_name HTTP/1.1
	Host: www.example.com
	Accept: application/json

On success, the response is:

    HTTP/1.1 200 OK
	Content-Type: application/json
    
    {
      "schema_name": schema name,
	  "tables": {
	    table name: table representation, ...
      }
    }

Note, this JSON document is usually quite long and too verbose to show verbatim in this documentation. Its general structure is a single field `schema_name` whose value is the _schema name_ addressed in the retrieval request and a field `tables` which in turn is a sub-object used as a dictionary mapping. Each field name of the sub-object is a _table name_ and its corresponding value is a _table representation_ as described in [Table Creation](#table-creation).

Typical error response codes include:
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

- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table`
- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/`

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
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

## Table Retrieval

The GET operation is used to retrieve a document describing one table in the data model using
a model-level resource name of the form:

- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_

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

## Column List Retrieval

The GET operation is used to retrieve a list of columns in one table using
a model-level resource name of the form:

- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/column`
- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/column/`

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
      "comment": column comment,
      "annotations": {
        annotation key: annotation document, ...
      }
    }

The input _column representation_ is a long JSON document too verbose to show verbatim in this documentation. Its general structure is a single object with the following fields:

- `name`: whose value is the _column name_ string for the new column which must be distinct from all existing columns in the table
- `type`: whose value is the _column type_ drawn from a limited set of supported types in ERMrest
- `default`: whose value is an appropriate default value consistent with the _column type_ or the JSON `null` value to indicate that NULL values should be used (the default when `default` is omitted from the _column representation_)
- `comment`: whose value is the human-readable comment string for the new column
- `annotations`: whose value is a sub-object use as a dictionary where each field of the sub-object is an _annotation key_ and its corresponding value a nested object structure representing the _annotation document_ content (as hierarchical content, not as a double-serialized JSON string!)

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

## Column Retrieval

The GET operation is used to retrieve a document describing one column in the data model using
a model-level resource name of the form:

- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/column/` _column name_

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

- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/key`
- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/key/`

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

The POST operation is used to add a key constraint to an existing table's key list resource:

- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/key`
- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/key/`

In this operation, the `application/json` _key representation_ is supplied as input:

    POST /ermrest/catalog/42/schema/schema_name/table/table_name/key HTTP/1.1
	Host: www.example.com
	Content-Type: application/json

    {
      "unique_columns": [ column name, ... ]
    }

The input _key representation_ is a JSON document with one object whose single field `unique_columns` has an array value listing the individual columns that comprise the composite key. The constituent columns are listed by their basic _column name_ strings.

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

- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/key/` _column name_ `,` ...

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

## Key Deletion

The DELETE method is used to remove a key constraint from a table:

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

- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/foreignkey` 
- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/foreignkey/` 
- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/foreignkey/` _column name_ `,` ...
- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/foreignkey/` _column name_ `,` ... `/references`
- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/foreignkey/` _column name_ `,` ... `/references/`
- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/foreignkey/` _column name_ `,` ... `/references/` _table reference_

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

The POST operation is used to add a foreign key reference constraint to an existing table's foreign key list resource:

- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/foreignkey`
- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/foreignkey/`

In this operation, the `application/json` _foreign key reference representation_ is supplied as input:

    POST /ermrest/catalog/42/schema/schema_name/table/table_name/foreignkey HTTP/1.1
	Host: www.example.com
	Content-Type: application/json

    {
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
      ]
    }

The input _foreign key reference representation_ is a long JSON document too verbose to show verbatim in this documentation. Its general structure is a single object with the following fields:

- `foreign_key_columns`: an array of column reference objects comprising the composite foreign key, each consisting of a sub-object with the fields:
  - `schema_name`: whose value is the same _schema name_ addressed in the request URL (optional content in this request)
  - `table_name`: whose value is the same _table name_ addressed in the request URL (optional content in this request)
  - `column_name`: whose value names the constituent column of the composite foreign key
- `referenced_columns`: an array of column reference objects comprising the referenced composite key, each consisting of a sub-object with the fields:
  - `schema_name`: whose value names the schema in which the referenced table resides
  - `table_name`: whose value names the referenced table
  - `column_name`: whose value names the constituent column of the referenced key

The two arrays MUST have the same length and the order is important in that the two composite keys are mapped to one another element-by-element, so the first column of the composite foreign key refers to the first column of the composite referenced key, etc. In the `referenced_columns` list, the _schema name_ and _table name_ values MUST be identical for all referenced columns.

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

- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/foreignkey/` _column name_ `,` ... `/references/` _table reference_ `/` _key column_ `,` ...

In this operation, content-negotiation SHOULD be used to select the `application/json` representation:

    GET /ermrest/catalog/42/schema/schema_name/table/table_name/foreignkey/column_name,.../references/table-reference/key_column,... HTTP/1.1
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

## Foreign Key Deletion

The DELETE method is used to remove a foreign key constraint from a table using any of the foreign key list or foreign key resource name forms:

- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/foreignkey` 
- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/foreignkey/` 
- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/foreignkey/` _column name_ `,` ...
- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/foreignkey/` _column name_ `,` ... `/references`
- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/foreignkey/` _column name_ `,` ... `/references/`
- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/foreignkey/` _column name_ `,` ... `/references/` _table reference_
- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/foreignkey/` _column name_ `,` ... `/references/` _table reference_ `/` _key column_ `,` ...

These names differ in how many constraints are applied to filter the set of retrieved foreign key references:
1. The list is always constrained to foreign keys stored in _schema name_ : _table name_
1. The list MAY be constrained by the composite foreign key _column name_ list of its constituent keys, interpreted as a set of columns
1. The list MAY be constrained by the _table reference_ of the table containing the composite key or keys referenced by the composite foreign key
1. The list MAY be constrained by the composite referenced key _key column_ list

This example uses a completely specified foreign key constraint name:

    DELETE /ermrest/catalog/42/schema/schema_name/table/table_name/key/column_name,.../references/table_reference/key_column,... HTTP/1.1
    Host: www.example.com
    
On success, this request yields a description:

    HTTP/1.1 204 No Content

The effect is to delete all foreign key constraints from the table matching the resource name used in the request.

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

