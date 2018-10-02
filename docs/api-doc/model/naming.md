# Model Resource Naming

Unlike general web architecture, [ERMrest](http://github.com/informatics-isi-edu/ermrest) expects clients to understand the URL internal structure and permits (or even encourages) reflection on URL content to understand how one resource name relates to another. To support introspection and management, the data model of a catalog is exposed as a set of model-level resources. These model elements also influence the [naming of data resources](../data/naming.md).

## Catalog Names

The ERMrest model resources belong to a catalog resource:

- _service_ `/catalog/` _cid_ [ `@` _revision_ ]

where the components of this root path are:

- _service_: the ERMrest service endpoint such as `https://www.example.com/ermrest`.
- _cid_: the catalog identifier for one dataset such as `42`.
- _revision_: (optional) timestamp identifying a historical snapshot of the catalog.

The catalog resource has a representation which provides basic information about it including access control lists.

In general, the optional `@` _revision_ modifier allows reference and
read-only retrieval of historical resource representations. Only the
latest, *live* catalog represented by _cid_ without a _revision_
supports mutation.

## Generic Model Sub-Resources

A number of different resource types in the model hierarchy all
support sub-resources with very similar interfaces. Rather than
describing each sub-resource independently, we summarize them here.

### Annotations

Annotations are reified as sub-resources:

- _subject_ `/annotation/` _annotation key_

| Subject Kind              | Purpose |
|---------------------------|---------|
| [catalog](#catalog-names) | Annotations about whole catalog |
| [schema](#schema-names)   | Annotations about one named schema |
| [table](#table-names)     | Annotations about one named table |
| [column](#column-names)   | Annotations about one named column |
| [key](#key-names)         | Annotations about one key constraint |
| [foreign key](#foreign-key-names) | Annotations about one foreign key constraint |

Each keyed annotation has a simple representation which is a machine-readable document in `application/json` format. The expected content and interpretation of the JSON document is externally defined and associated with the _annotation key_ which SHOULD be a URL (escaped with standard URL-encoding before embedding in this annotation name URL). The purpose of the _annotation key_ is to allow different user communities to organize their own annotation standards without ambiguity.

Additionally, a composite resource summarizes all existing annotations on one annotated resource, for convenient discovery and bulk retrieval:

- _annotated resource_ `/annotation`
- _annotated resource_ `/annotation/`

### Comments

Comments are reified as a sub-resources:

- _subject_ `/comment`

| Subject Kind              | Purpose |
|---------------------------|---------|
| [schema](#schema-names)   | Comment about one named schema |
| [table](#table-names)     | Comment about one named table |
| [column](#column-names)   | Comment about one named column |
| [key](#key-names)         | Comment about one key constraint |
| [foreign key](#foreign-key-names) | Comment about one foreign key constraint |

This resource has a simple representation which is just human readable text in `text/plain` format.

### ACLs

Access control lists (ACLs) are reified as sub-resources:

- _subject_ `/acl/` _acl name_

| Subject Kind              | Purpose |
|---------------------------|---------|
| [catalog](#catalog-names) | ACLs granting access to whole catalog |
| [schema](#schema-names)   | ACLs granting access to one named schema |
| [table](#table-names)     | ACLs granting access to one named table |
| [column](#column-names)   | ACLs granting access to one named column |
| [foreign key](#foreign-key-names) | ACLs granting access to one foreign key constraint |

Each keyed ACL has a simple representation which is a machine-readable array of authorized client attribute strings or a `null` value in `application/json` format.

### ACL Bindings

Dynamic access control list bindings (ACL bindings) are reified as sub-resources:

- _subject_ `/acl_binding/` _binding name_

| Subject Kind              | Purpose |
|---------------------------|---------|
| [table](#table-names)     | ACL bindings granting access to one named table |
| [column](#column-names)   | ACL bindings granting access to one named column |
| [foreign key](#foreign-key-names) | ACL bindings granting access to one foreign key constraint |

Each keyed ACL binding has a simple representation which is a machine-readable object or a `false` value in `application/json` format.

## Model Names

The ERMrest model resources are named under a root collection of schemata for a particular catalog:

- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/`

where the components of this root path are:

- _service_: the ERMrest service endpoint such as `https://www.example.com/ermrest`.
- _cid_: the catalog identifier for one dataset such as `42`.
- _revision_: (optional) timestamp identifying a historical snapshot of the catalog schemata.

This root schemata resource has a representation which summarizes the entire data model of the catalog as a single document.

## Schema Names

Each schema or namespace of tables in a particular catalog is reified as a model-level resource:

- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_

This named schema resource has a representation which summarizes the data model of all tables qualified by the _schema name_ namespace.

## Table Names

Each table is reified as a model-level resource:

- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/` _table name_

This named table resource has a representation which summarizes its data model including columns, keys, and foreign keys. Within data resource names, a table may be referenced by _table name_ only if that name is unique within the catalog or by a fully qualified _schema name_ `:` _table name_. Concrete examples of such names might be `table1` or `schema1:table1`.

### Column Names

Each column is reified as a model-level resource:

- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/` _table name_ `/column/` _column name_

This named column resource has a representation which summarizes its data model including name and type. Within data resource names, a column may be referenced by:

- _column name_ when resolving within an implicit table context;
- _table alias_ : _column name_ when resolving against a context where _table alias_ has been bound as an alias to a specific table instance;
- _table name_ : _column name_ when resolving against the model and _table name_ is unique within the catalog;
- _schema name_ : _table name_ : _column name_ when resolving against the model and _table name_ might otherwise be ambiguous.

### Key Names

Each (composite) key constraint is reified as a model-level resource:

- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/` _table name_ `/key/` _column name_ `,` ...

This named constraint has a representation which summarizes its set of constituent key columns. The meaning of a key constraint is that the combination of listed columns must be a unique identifier for rows in the table, i.e. no two rows can share the same combination of values for those columns.

ERMrest also supports pseudo-keys on views, which allow the uniqueness properties of views to be asserted both for clients introspecting the catalog model and for ERMrest itself to reason about queries on the view. Psuedo-keys are chosen automatically when an authorized client creates a key constraint on a view, while real database constraints are used when the client creates a key constraint on a table.

  - *NOTE* pseudo-keys are advisory, *not enforced* in the database, and *not validated* by ERMrest. A client SHOULD NOT assert inaccurate psuedo-key constraints as it could mislead other clients who introspect the schema or lead to unexpected query results as ERMrest formulates relational queries assuming the constraints are true.
  - Future ERMrest releases MAY enforce validation on psuedo-keys so clients SHOULD NOT depend on the ability to create inaccurate psuedo-constraints.

Additionally, a composite resource summarizes all existing key constraints on one table for convenient discovery and bulk retrieval:

- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/` _table name_ `/key`
- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/` _table name_ `/key/`

### Foreign Key Names

Each (composite) foreign key constraint is reified as a model-level resource:

- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/` _table name_ `/foreignkey/` _column name_ `,` ... `/reference/` _table reference_ `/` _key column_ `,` ...

This named constraint has a representation which summarizes its set of constituent foreign key columns, another referenced table, and the set of key columns that form the composite key being referenced in that other table, including the mapping of each foreign key _column name_ to each composite key _key column_. The _table reference_ can be a qualified table name, e.g. `schema1:table1` or an unqualified table name, e.g. `table1`.  The meaning of this constraint is that each combination of non-NULL values in _schema name_:_table name_ MUST reference an existing combination of values forming a composite key for a row in _table reference_.

ERMrest also supports pseudo-foreign keys on views, which allow the reference links of views to be asserted both for clients introspecting the catalog model and for ERMrest itself to reason about queries on the view. Psuedo-foreign keys are chosen automatically when an authorized client creates a foreign key constraint on a view or referencing a view, while real database constraints are used when the client creates a foreign key constraint on a table referencing another table.

  - *NOTE* pseudo-foreign keys are advisory, *not enforced* in the database, and *not validated* by ERMrest. A client SHOULD NOT assert inaccurate psuedo-foreign key constraints as it could mislead other clients who introspect the schema or lead to unexpected query results as ERMrest formulates relational queries assuming the constraints are true.
  - Future ERMrest releases MAY enforce validation on psuedo-foreign keys so clients SHOULD NOT depend on the ability to create inaccurate psuedo-constraints.

Additionally, a composite resource summarizes all foreign key constraints on one table for discovery and bulk retrieval purposes:

- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/` _table name_ `/foreignkey`
- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/` _table name_ `/foreignkey/`

Additionally, a composite resource summarizes all foreign key constraints involving one composite foreign key _column name_ list:

- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/` _table name_ `/foreignkey/` _column name_ `,` ...
- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/` _table name_ `/foreignkey/` _column name_ `,` ... `/reference`
- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/` _table name_ `/foreignkey/` _column name_ `,` ... `/reference/`

Finally, a composite resource summarizes all foreign key constraints involving one composite foreign key _column name_ list and one _table reference_:

- _service_ `/catalog/` _cid_ [ `@` _revision_ ] `/schema/` _schema name_ `/table/` _table name_ `/foreignkey/` _column name_ `,` ... `/reference/` _table reference_

(While highly unusual, it is possible to express more than one foreign key constraint from the same composite foreign key _column name_ list to different composite key _key column_ lists in the same or different _table reference_ tables.)
