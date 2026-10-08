
# Live Index Resource Naming

This section is about naming of indexes on the catalog's live tables.

ERMrest data API performance is sensitive to the indexes available to
and used by the underlying PostgreSQL query planner.

ERMrest automatically creates some indexes while provisioning table
and column resources:

1. Mandatory indexes supporting unique key constraints.
2. Optional indexes on other data colums, influenced by indexing-preferences annotations in the model.

However, long-term management of a catalog may require adjustments to
the indexing strategy on existing tables and columns.

## Index Names

Each index is reified as a sub-resource under its target table:

- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/index/` _index name_

This named index resource has a representation which summarizes its key characteristics. However, unlike ERMrest's structured table definitions, the index is relatively opaque and is a "leaky abstraction" revealing PostgreSQL back-end details.

Each index has a name, a few boolean properties, and an opaque SQL DDL string describing how it is created, according to PostgreSQL. A client must interpret this DDL string to gain insight into the index function; ERMrest itself has little

## Index Listing of a Table

Each index is reified as a sub-resource under its target table:

- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/index/`

Without an explicit _index name_ in the resource name, the parent is a listing of all indexes for the given table.
