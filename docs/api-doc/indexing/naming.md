
# Live Index Resource Naming

This section is about naming of indexes on the catalog's backing
database. As such, it there are APIs to manage indexes on tables in
the "live" model and the history-tracking tables that support access
to catalog snapshots.

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
- _service_ `/catalog/` _cid_ `/history/table/` _table RID_ `/index/` _index name_

These naming stereotypes cover indexes on two types of table:

1. Each live table is known by a schema-qualified name. This name can change over time, but is coherent with the current catalog model.
2. Each history table is known by a unique and stable RID. This RID unabiguously references the history storage table even if the corresponding live table has been renamed, dropped, or had its definition revised.

Each named index resource has a representation which summarizes its key characteristics. However, unlike ERMrest's structured table definitions, the index representation is relatively opaque and is a "leaky abstraction", revealing PostgreSQL back-end details.

Each existing index representation repeats its name elments, a few boolean properties, and an opaque SQL DDL string describing how PostgreSQL understands it. A client must interpret this DDL string to gain insight into the index function; ERMrest itself has little understanding of the structure of existing indexes.

As described in the index management REST API section, index creation is conceptually asymmetric. It takes a different input form which is at a higher level of abstraction that ERMrest understands. But, ERMrest exposes 

## Index Listing of a Table

Each index is reified as a sub-resource under its target table:

- _service_ `/catalog/` _cid_ `/schema/` _schema name_ `/table/` _table name_ `/index/`
- _service_ `/catalog/` _cid_ `/history/table/` _table RID_ `/index/`

Without an explicit _index name_ in the resource name, the parent is a listing of all indexes for the given live or history table.
