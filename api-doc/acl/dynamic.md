
# ERMrest Access Control

## Dynamic ACL Binding Technical Reference

### Available Dynamic ACL Types

Some of the previously described [access modes](#access-modes) have a
corresponding dynamic ACL type associated with them. Because dynamic ACLs
are for data-dependent access, they have more restrictive applicability:

| Type   | Mode        | Implies                        | Supported Resources |
|--------|-------------|--------------------------------|---------------------|
| owner  | Write data  | insert, update, delete, select | table, column, reference |
| insert | Insert data |                                | reference           |
| update | Modify data |                                | table, column, reference |
| delete | Delete data |                                | table, column       |
| select | View data   |                                | table, column       |

Table and column-level dynamic ACLs are only applicable to access
requests against existing database content. Insertion of new rows can
only be granted by a static policy. However, reference-level dynamic
ACLs can grant or deny the ability to specify specific foreign keys 
even during row insertion.

Dynamic data rights do not imply model access. Model access must be
determined in a data-independent manner in order to even pose an
access request which might be granted by dynamic access rights.


### Dynamic ACL Binding Representation

The data-dependent ACL bindings are encoded in an `"acl_bindings"`
sub-resource of the governed resource. This is a hash-map keyed by ACL
binding name. For example, a table resource has a canonical
representation as in the following example:

    {
	  "schema_name": "My Schema",
	  "table_name": "My Table",
	  "kind": "table",
	  "comment": "The purpose of My Table is...",
	  "annotations": ...,
	  "column_definitions": ...,
	  "keys": ...,
	  "foreign_keys": ...,
	  "acls": {
		"write": ["some/curator/URI"]
	  },
	  "acl_bindings": {
	    "My Binding": {
		  "types": ["owner"],
		  "projection": "Managed By",
		  "projection_type": "acl"
		}
	  }
	}

This example has an explicitly set, data-independent curator group who
can modify all rows in the table, while other data-independent ACLs
are inherited from the enclosing schema. A dynamic ACL binding called
`My Row Owners` specifies that an ACL stored in the `Managed By`
column of the table grants `owner` dynamic access type for individual
rows. The representation uses an array for the `type` so that multiple
access modes can be more easily configured without having to repeat the
same projection many times.

#### Inheritence and False Binding

As a convenience, columns effectively inherit the ACL bindings of
their table. A column whose `"acl_bindings"` document is empty will
permit all operations that the table would allow for each row. To
grant fewer writes, the column-level `"acl_bindings"` MUST override
the named bindings inherited from the table.

- Replacement: the column MAY provide a different binding document under the same binding name.
- Suppression: the column MAY provide a literal `false` value instead of a binding document.

#### Projection Document

The `"projection"` field of the ACL binding is a document representing
a parsed *abstract syntax tree* for an attribute query fragment. The
general form of the ACL document is an array of path elements:

- `[` _element_ `,` ... `,` _column_ `]`

This corresponds to the serialized query fragment `element/.../column`
to project ACL content from an implicit base entity context using the
ERMrest `/attribute/base` API.  The final _column_ MUST be a string
literal naming a column in the effective entity-path context. Each
anterior _element_ MAY use one of the following sub-document
structures:

- `{ "context":` _leftalias_ `,` _direction_ `:` _fkeyname_  `, "alias":` _rightalias_ `}`
    - Links a new table instance to the existing path via inner join
	- The left-hand path context is the table instance named by _leftalias_ or the immediately preceding path context if _leftalias_ is `null` or absent.
	    - The alias `"base"` is implicitly bound to the base table to which this ACL is bound.
	- The joining condition is determined by the named foreign key constraint _fkeyname_ where one end is tied to the left-hand path context and the other to the newly added table instance.
	- The _direction_ of the joining condition is `"inbound"` or `"outbound"` and MUST be specified.
	- The _rightalias_ string literal is bound to the new table instance unless it is `null` or absent.
	    - The alias `"base"` is reserved and cannot be bound as a _rightalias_.
- `{ "and": [` _filter_ `,` ... `], "negate": ` _negate_ `}`
    - A logical conjunction of multiple _filter_ clauses is applied to the query to constrain matching rows.
	- The logical result is negated only if _negate_ is `true`.
	- Each _filter_ clause may be a terminal filter element, conjunction, or disjunction.
- `{ "or": [` _filter_ `,` ... `], "negate": ` _negate_ `}`
    - A logical disjunction of multiple _filter_ clauses is applied to the query to constrain matching rows.
	- The logical result is negated only if _negate_ is `true`.
	- Each _filter_ clause may be a terminal filter element, conjunction, or disjunction.
- `{ "filter": [` _leftalias_ `,` _column_ `], "operand":` _value_ `, "operator":` _operator_ `, "negate":` _negate_ `}`
    - An individual filter _element_ is applied to the query or individual _filter_ clauses participate in a conjunction or disjunction.
	- The filter constrains a named _column_ in the table named by _leftalias_ or the current path context if _leftalias_ is `null`.
	- The _operator_ specifies the constraint operator via one of the valid operator names in the ERMrest REST API.
	- The _value_ specifies the constant operand for a binary constraint operator.
	- The logical result of the constraint is negated only if _negate_ is `true`.

Many fields may be omitted from the above structures to allow concise
projection documents:

- Many `null` or absent values have a default semantics defined:
    - _leftalias_ is omitted to get a default path-based entity context
	- _rightalias_ is omitted if no alias binding is required
	- _negate_ is omitted for normal (non-negated) logical decisions
	- _operator_ is omitted for regular `"="` equality comparisons
    - _value_ is omitted when the unary `"::null::"` operator is used
- A few fields are required to be present with a non-null value
    - _direction_ and _fkeyname_ MUST always be present in link documents.
	- _filter_ MUST always be present in conjunction and disjunction documents.
	- _column_ MUST always be present in filter clauses.
	- _value_ MUST always be present with each binary _operator_ including the default `"="`
- Two syntactic short-hands are allowed for bare column names:
    - An single-element projection `[` _column_ `]` MAY omit the array and specify just the string literal _column_.
	- An unqualified filter column `[ null,` _column_ `]` MAY omit the array and specify just the string literal _column_.

#### Effective ACL Projection Query

The [projection document](#projection-document) assumes that a *base
row query* similar to `/ermrest/catalog/N/attribute/Base/key=X/` will
be formulated by the system, and the projection document describes the
suffix necessary to turn this into an ACL projection query. E.g. in
the [dynamic ACL example](#dynamic-acl-binding-representation) above,
the projection string `"Managed%20By"` names a column `Managed By`
could be appended to a base-row URL to form a complete ACL projection
query URL:

    /ermrest/catalog/N/attribute/My%20Schema:My20Table/key=X/Managed%20By

For more complicated projection documents, there is a similar
mechanical transformation which can produce an effective ACL
projection query. The supported projection language covers a subset of
all possible query URLs.

#### Projection Types

Zero or one rows MAY be returned as the query result. Several
projected column types are supported, and more than one projection
type is supported. See the following matrix:

Projected Column Type | Supported `"projection_type"` | Description
----------|---------------------|-------------------------
`text[]`  | `acl` (default)     | The projected array is interpreted as ACL content.
`text`    | `acl` (default)     | The projected text is interpreted as if it were an array containing the single value.
*any*     | `nonnull` | A non-null projected value is interpreted as a `true` authorization decision.

The `nonnull` projection type is supported by all column types. The
`acl` projection type is only supported for the projected column types
shown above.

