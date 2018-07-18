# ERMrest Data Operations

The [ERMrest](http://github.com/informatics-isi-edu/ermrest) data operations manipulate tabular data structured according to the existing entity-relationship model already configured as schemata resources in the catalog.

In the following examples, we illustrate the use of specific data formats. However, content negotiation allows any of the supported tabular data formats to be used in any request or response involving tabular data.

## Entity Creation

The POST operation is used to create new entity records in a table, using an `entity` resource data name of the form:

- _service_ `/catalog/` _cid_ `/entity/` _table name_
- _service_ `/catalog/` _cid_ `/entity/` _schema name_ `:` _table name_

In this operation, complex entity paths with filter and linked entity elements are not allowed.  The request input includes all columns of the table, thus supplying full entity records of data:

    POST /ermrest/catalog/42/entity/schema_name:table_name HTTP/1.1
    Host: www.example.com
    Content-Type: text/csv
    Accept: text/csv

    column1,column2
    1,foo
    2,foo
    3,bar
    4,baz

The input data MUST observe the table definition including column names and types, uniqueness constraints for key columns, and validity of any foreign key references. It is an error for any existing key in the stored table to match any key in the input data, as this would denote the creation of multiple rows with the same keys.

For convenience, the ERMrest system columns (`RID`, `RCT`, `RMT`, `RCB`, `RMB`) are implicitly supplied with default values during entity creation.

On success, the response is:

    HTTP/1.1 200 OK
    Content-Type: text/csv

    column1,column2
    1,foo
    2,foo
    3,bar
    4,baz

Typical error response codes include:
- 400 Bad Request
- 409 Conflict
- 403 Forbidden
- 401 Unauthorized

### Entity Creation with Defaults

The POST operation is also used to create new entity records in a table where some values are assigned default values, using an entity resource data name of the form:

- _service_ `/catalog/` _cid_ `/entity/` _table name_ `?defaults=` _column name_
- _service_ `/catalog/` _cid_ `/entity/` _schema name_ `:` _table name_ `?defaults=` _column name_ `,` ...
- _service_ `/catalog/` _cid_ `/entity/` _table name_ `?defaults=` _column name_ `&nondefaults=` _column name_ `,` ...

In this operation, complex entity paths with filter and linked entity elements are not allowed.  The request input includes all columns of the table, thus supplying full entity records of data:

    POST /ermrest/catalog/42/entity/schema_name:table_name?defaults=column1 HTTP/1.1
    Host: www.example.com
    Content-Type: text/csv
    Accept: text/csv

    column1,column2
    1,foo
    1,bar
    1,baz
    1,bof

The input data MUST observe the table definition including column names and types, uniqueness constraints for key columns, and validity of any foreign key references. If multiple columns are to be set to defaults, they are provided as a comma-separated list of column names on the right-hand-side of the `defaults=...` query parameter binding.

All columns should still be present in the input. However, the values for the column (or columns) named in the `defaults` query parameter will be ignored and server-assigned values generated instead. It is an error for any existing key in the stored table to match any key in the input data, as this would denote the creation of multiple rows with the same keys.

For convenience, columns lacking `enumerate` privilege and the ERMrest system columns (`RID`, `RCT`, `RMT`, `RCB`, `RMB`) are implicitly supplied with default values during entity creation, even if they are not listed in the `defaults` query parameter. The optional `nondefaults` query parameter can be used to suppress this implicit behavior, e.g. to allow a client to import or relocate table content from another catalog while preserving its originally assigned `RID`, `RCT`, and `RCB` values. NOTE: the server will also allow a privileged client to send values for `RMT` and `RMB`, but the current implementation of system columns will always override with a system-determined value reflecting the actual data mutation request transaction metadata.

On success, the response is:

    HTTP/1.1 200 OK
    Content-Type: text/csv

    column1,column2
    4,foo
    5,bar
    6,baz
    7,bof

In this example, a presumed `serial4` type used for `column1` would lead to a sequence of serial numbers being issued for the default column.

Typical error response codes include:
- 400 Bad Request
- 409 Conflict
- 403 Forbidden
- 401 Unauthorized

## Entity Update

The PUT operation is used to update entity records in a table, using an `entity` resource data name of the form:

- _service_ `/catalog/` _cid_ `/entity/` _table name_
- _service_ `/catalog/` _cid_ `/entity/` _schema name_ `:` _table name_

In this operation, complex entity paths with filter and linked entity elements are not allowed.  The request input includes all columns of the table, thus supplying full entity records of data:

    PUT /ermrest/catalog/42/entity/schema_name:table_name HTTP/1.1
    Host: www.example.com
    Content-Type: text/csv
    Accept: text/csv

    column1,column2
    1,foo
    2,foo
    3,bar
    4,baz

The input data MUST observe the table definition including column names and types, uniqueness constraints for key columns, and validity of any foreign key references. Any input row with keys matching an existing stored row will cause an update of non-key columns to match the input row.  Any input row with keys not matching an existing stored row will cause creation of a new row.

On success, the response is:

    HTTP/1.1 200 OK
    Content-Type: text/csv

    column1,column2
    1,foo
    2,foo
    3,bar
    4,baz

Typical error response codes include:
- 400 Bad Request
- 409 Conflict
- 403 Forbidden
- 401 Unauthorized

## Entity Retrieval

The GET operation is used to retrieve entity records, using an `entity` resource data name of the form:

- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/entity/` _path_

In this operation, complex entity paths with filter and linked entity elements are allowed, for example:

    GET /ermrest/catalog/42/entity/table1/column1=value1/table2/column2=value2 HTTP/1.1
    Host: www.example.com
    Accept: text/csv

On success, the response is:

    HTTP/1.1 200 OK
    Content-Type: text/csv

    column1,column2
    1,foo
    2,foo
    3,bar
    4,baz

Each result row will correspond to an entity in the entity set denoted by _path_. This will be a filtered subset of entities from the table instance context of _path_ considering all filtering and joining criteria.

Typical error response codes include:
- 409 Conflict
- 403 Forbidden
- 401 Unauthorized

## Entity Deletion

The DELETE operation is used to delete entity records, using an `entity` resource data name of the form:

- _service_ `/catalog/` _cid_ `/entity/` _path_

In this operation, complex entity paths with filter and linked entity elements are allowed.

    DELETE /ermrest/catalog/42/entity/table1/column1=value1/table2/column2=value2 HTTP/1.1
	Host: www.example.com

On success, the response is:

    HTTP/1.1 204 No Content

The result of the operation is that each of the entity records denoted by _path_ are deleted from the catalog. This operation only (directly) affects the right-most table instance context of _path_. Additional joined entity context may be used to filter the set of affected rows, but none of the contextual table instances are targeted by deletion. However, due to constraints configured in the model, it is possible for a deletion to cause side-effects in another table, e.g. deletion of entities with key values causing foreign key references to those entities to also be processed by a cascading delete or update.

Typical error response codes include:
- 409 Conflict
- 403 Forbidden
- 401 Unauthorized

## Attribute Retrieval

The GET operation is used to retrieve projected attribute records, using an `attribute` resource data name of the form:

- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/attribute/` _path_ `/` _projection_ `,` ...

In this operation, complex entity paths with filter and linked entity elements are allowed and projection can draw values from any entity element of _path_, for example:

    GET /ermrest/catalog/42/attribute/A:=table1/column1=value1/table2/column2=value2/x:=A:column1,y:=column3 HTTP/1.1
    Host: www.example.com
    Accept: text/csv

where output column `x` is drawn from column `column1` of the `table1` table instance aliased with `A`, while output column `y` is drawn from column `column3` of the `table2` table instance context of _path_.

On success, the response is:

    HTTP/1.1 200 OK
    Content-Type: text/csv

    x,y
    1,foo
    2,foo
    3,bar
    4,baz

Each result row will correspond to an entity in the entity set denoted by _path_ but the result row will be populated with the specified projection values rather than the denoted entity fields. This will be a filtered subset of entities from the table instance context of _path_ considering all filtering and joining criteria.

Typical error response codes include:
- 409 Conflict
- 403 Forbidden
- 401 Unauthorized

## Attribute Deletion

The DELETE operation is used to clear attributes to their default value (usually NULL), using an `attribute` resource data name of the form:

- _service_ `/catalog/` _cid_ `/attribute/` _path_ `/` _target_ `,` ...

In this operation, complex entity paths with filter and linked entity elements are allowed but only attributes from the _path_ entity context can be specified as the target for deletion, rather than the generalized projection possible with retrieval.

    DELETE /ermrest/catalog/42/attribute/table1/column1=value1/table2/column2=value2/column3 HTTP/1.1
	Host: www.example.com

On success, the response is:

    HTTP/1.1 204 No Content

The result of the operation is that each of the entity records denoted by _path_ are modified in the catalog, changing their _target_ columns to default value (usually `NULL` or whatever default value is configured for that column in the model). This operation only (directly) affects the right-most table instance context of _path_. Additional joined entity context may be used to filter the set of affected rows, but none of the contextual table instances are targeted by deletion. However, due to constraints configured in the model, it is possible for a deletion to cause side-effects in another table, e.g. modification of key values causing foreign key references to those entities to also be processed by a cascading update.

Typical error response codes include:
- 409 Conflict
- 403 Forbidden
- 401 Unauthorized

## Attribute Group Retrieval

The GET operation is used to retrieve projected attribute group records, using an `attributegroup` resource data name of the form:

- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/attributegroup/` _path_ `/` _group key_ `,` ... 
- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/attributegroup/` _path_ `/` _group key_ `,` ... `;` _projection_ `,` ...

In this operation, complex entity paths with filter and linked entity elements are allowed, for example:

    GET /ermrest/catalog/42/attributegroup/A:=table1/column1=value1/table2/column2=value2/y:=column3;x:=A:cnt(column1),z:=A:column1 HTTP/1.1
    Host: www.example.com
    Accept: text/csv

On success, the response is:

    HTTP/1.1 200 OK
    Content-Type: text/csv

    y,x,z
    foo,2,1
    bar,1,3
    baz,1,4

Each result row will correspond to a distinct _group key_ tuple existing in the joined records denoted by _path_ and the result row will be populated with the _group key_ tuple and additional _projection_ values. Unlike the `entity` and `attribute` resource spaces which have outputs corresponding to entities in the context of _path_, the `attributegroup` resource space changes the semantics of _path_ to denote a permutation set of joined rows based on all the entity-relationship linkages between the elements of _path_; this permutation set is further sub-setted by any filters in _path_.

Typical error response codes include:
- 409 Conflict
- 403 Forbidden
- 401 Unauthorized

## Attribute Group Update

The PUT operation is used to update attributes in a table, using an `attributegroup` resource data name of the form:

- _service_ `/catalog/` _cid_ `/attributegroup/` _path_ `/` _group key_ `,` ... `;` _target_ `,` ...

In this operation, complex entity paths with filter and linked entity elements are not allowed:

    PUT /ermrest/catalog/42/attributegroup/table/column1;column2 HTTP/1.1
    Host: www.example.com
    Content-Type: text/csv
    Accept: text/csv

    column1,column2
    1,foo
    2,foo
    3,bar
    4,baz

The input data MUST NOT have more than one row with the same _group key_ tuple of values. Any input row with _group key_ columns matching an existing stored row will cause an update of _target_ columns to match the input row.  Any input row with _group key_ columns not matching an existing stored row will cause an error.

On success, the response contains updated row information:

    HTTP/1.1 200 OK
    Content-Type: text/csv

    column1,column2
    1,foo
    2,foo
    3,bar
    4,baz

TODO: clarify the meaning of this result content.

Typical error response codes include:
- 400 Bad Request
- 409 Conflict
- 403 Forbidden
- 401 Unauthorized

### Attribute Group Update with Renaming

As with retrieval of attribute groups, update supports renaming of stored columns within the external representation, so that it is even possible to rewrite the key columns as in this example:

    PUT /ermrest/catalog/42/attributegroup/table1/original:=column1;replacement:=column1 HTTP/1.1
    Host: www.example.com
    Content-Type: text/csv
    Accept: text/csv

    original,replacement
    foo,foo-prime
    bar,bar-prime
    baz,baz-prime

Here, the stored rows with `column1` matching values in `original` of the input will have `column1` rewritten to the corresponding value in `replacement`.

On success, the response is:

    HTTP/1.1 200 OK
    Content-Type: text/csv

    original,replacement
    foo,foo-prime
    bar,bar-prime
    baz,baz-prime

## Aggregate Retrieval

The GET operation is used to retrieve projected aggregates, using an `aggregate` resource data name of the form:

- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/aggregate/` _path_ `/` _projection_ `,` ...

In this operation, complex entity paths with filter and linked entity elements are allowed, for example:

    GET /ermrest/catalog/42/aggregate/A:=table1/column1=value1/table2/column2=value2/y:=cnt_d(column2),x:=A:cnt(column1),z:=A:column1 HTTP/1.1
    Host: www.example.com
    Accept: text/csv

On success, the response is:

    HTTP/1.1 200 OK
    Content-Type: text/csv

    y,x,z
    3,4,1

A single result row will summarize the joined records denoted by _path_ and the result row will be populated with _projection_ values. Like the `attributegroup` resource space, the `aggregate` resource space changes the semantics of _path_ to denote a permutation set of joined rows based on all the entity-relationship linkages between the elements of _path_; this permutation set is further sub-setted by any filters in _path_ and then reduced to a single aggregate summary value by _projection_ values using an aggregate function or by choosing an arbitrary example value for _projection_ values referencing a bare column.

Typical error response codes include:
- 409 Conflict
- 403 Forbidden
- 401 Unauthorized
