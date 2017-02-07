
# ERMrest Access Control

## Goals

Overall goals:

1. Cover a broad set of differentiated access control use cases identified through pilot projects:
    - Fine-grained authorization decisions within a single catalog based on web client authentication context.
	- Static policies scoped to levels of data model hierarchy.
	- Data-dependent policies:
	  - Row or datum visibility.
	  - Row or datum insertion, update, or deletion.
	  - Datum expression.
2. Provide remotely-managed access control policy resources as part of the REST API.
    - Integrated with model management APIs for bulk and per-policy management.
	- In-place upgrade of existing catalogs to add this feature set.
	- Minimal disruption and incompatibility for legacy users and client scripts.
	- Incremental effort required for incremental complexity in policies.
    - Help clients anticipate authorization decisions to customize GUI presentations etc.
3. Allow for efficient and correct implementation of the authorization decisions within ERMrest.
    - Pre-evaluate static policies before accessing data.
	- Compile data-dependent decisions into SQL queries.
	- Produce SQL amenable to fast query plans.
4. Limit policy model to access-control list metaphors:
    - Effective ACL can be determined for given resource access decision.
    - Decision based on intersection of client attributes with effective ACL.
	- No attempt to address arbitrary computable decisions as allowed in PostgreSQL RLS policy expressions.

### Scope of Use Cases to Address

The ERMrest resource hierarchy supports a rich set of possible
resource operations. We intend to provide fine-grained control of
these operations, differentiating rights of one user from another in a
shared system:

1. Make some content invisible
    - An entire catalog
	- An entire schema
	- An entire table
	- An entire column of a table
	- Some rows of a table (as if row does not exist)
	- Some fields of some rows of a table (as if the value is NULL)
2. Prevent modification of some content
    - Access control policy
	- Table structure
	- Table constraints
	- Row insertion
	- Row modification
	- Row deletion
	- Field modification (can change parts of row but not all parts)
	- Value expression (can apply some values but not others in a given field)
3. Delegate some rights within a community
	- Delegation doesn't take away original owner rights, i.e. nothing in a resource tree is hidden from root owner
    - Authorize additional owners for sub-resources
	- Delegate management of specific table's structure and constraints
    - Delegate creation of new schema (while protecting other schemas)
	- Delegate creation of new table (while protecting other tables)
4. Make sure simple policies are still simple to manage
    - Entire catalog visible to one group
	- Entire catalog data mutable by one group
	- Entire catalog model managed by one group
	
### Complications

Controlling visibility is complicated, particularly when done to the
extent desired by some use cases we've observed.

1. Most forms of access depend on other access
    - Must see model to make sense of data APIs
	- Must see data to make use of data modification APIs
	- Must see related data to make sense of reference constraints
	- Must see policy to make sense of what access mechanisms are available
2. Reference constraints can expose "hidden" data
    - Rows can be hidden in a domain table's policy
	- Referring rows might still be visible due to a referring table's more open policy
	- Presence of hidden domain data is revealed
3. Integrity constraints can expose "hidden" columns
    - A hidden column will receive default values on insert
	- A default expression is not guaranteed to satisfy integrity constraints
	- The conflict error will reveal information about the hidden column
	  - That a column with this name exists
	  - What the default value looks like
	  - What kind of constraint is violated by the default value

We will initially require policy administrators to reconcile these
problems by forming well coordinated schemas and policies. In some
cases, we may be able to improve usability by having the system
automatically detect conflicts and/or reconcile them?

## Core Concepts

Policy will be expressed over the hierarchical catalog model, with
policies attached to specific resources in the following model
hierarchy:

- Catalog
  - Schema
    - Table
      - Column
      - Constraint

Constraints are potentially composed of multiple columns, and a column
is potentially governed by multiple constraints. In ERMrest, this
resource graph is presented as a flattened tree where each constraint
or column is instantiated only once as a manageable resource under the
containing table resource.

### Access Modes

For the purpose of access control decisions, a number of distinct
access modes are defined such that permission can be granted or denied
for each mode separately. Some modes are sub-modes of a more abstract
mode, allowing easier control of settings when fine control is not
needed:

- Own
  - Write model
    - Insert new model element
    - Modify existing model element
    - Delete existing model element
  - View existing model element
  - Write data
    - Insert new data
    - Modify existing data
    - Delete existing data
  - View existing data

Ownership is not quite an access mode but convenient to think about as
the superior mode to all other modes.

### Policy Scoping and Resource Dependencies

A policy attached to a resource will govern access to that
resource. Because many forms of access depend on multiple resources, a
complete request will be granted or denied based on the conjunction of
policies governing each resource involved in the request.

For example:
- Data can only be accessed if the enclosing table is visible.
- A table can only be accessed if its enclosing schema is visible.
- A schema can only be access if its enclosing catalog is visible.
- A column can only be modified if its governing reference constraints also allow it.

### Data-Dependence

Some, but not all, fine-grained access decisions involve data values:

- Model-level Access Control Lists (ACLs) support *data-independent* decisions, i.e. granting access to all rows of a table uniformly.
- Dynamic ACL bindings support *data-dependent* decisions, i.e. granting access to specific rows of a table.

For a particular access mode, the final decision involves a
disjunction of any data-independent and data-dependent policy in
effect on that resource. In other words, either policy is sufficient
to grant access.

| ACL grants access? | Dynamic ACL is bound? | Decision process |
|--------------------|-----------------------|------------------|
| No                 | No                    | Static (deny)    |
| No                 | Yes                   | Dynamic          |
| Yes                | No                    | Static (grant)   |
| Yes                | Yes                   | Static (grant)   |

When a dynamic decision process is needed, ERMrest can compile an
appropriate SQL query with the current client identity encoded as
static conditions in the `WHERE` clause, such that PostgreSQL can
effectively plan the use of indexed ACL storage columns to determine
data visibility and compute final access decisions. When a static
decision is possible, this query complexity can be avoided.

### Policy Inheritance

The policy system will be able to distinguish empty `[]` policies
(i.e. grant nothing) from unconfigured `null` policies (i.e. no local
policy is expressed). An unconfigured policy means that all access to
the resource is governed by the policy of its enclosing resource.

In effect, the enclosing policy is *inherited* by the sub-resource
unless the sub-resource has its own more specific policy. This allows
simplified management of many resources subject to an identical
policy, while allowing targeted overriding of other sibling or
sub-resources.

- A local policy can *restrict* access compared to the enclosing resource
  - One table is read-only in an otherwise read-write schema
  - One column is hidden in an otherwise read-write table
- A local policy can *broaden* access compared to the enclosing resource
  - One table is writable in an otherwise read-only schema
  - One column is mutable in an otherwise read-only table
- But, access decisions still involve resource dependencies
  - A table cannot be visible in an invisible schema
  - A column cannot be accessed in an invisible table

### Model-level ACLs

ACLs are distributed throughout the hierarchical model of the catalog.

1. The predefined *name* of each ACL identifies the type of access governed.
2. The *resource* to which the ACL is attached identifies the scope of the access governed.
3. The *content* of each ACL is a list of disjunctive matching choices which may include the wildcard `*`.

#### Catalog ACLs

A catalog-level ACL describes what access to permit on the whole
catalog. Catalogs do not inherit ACLs from elsewhere, so an
unconfigured ACL is not defined.

During catalog creation the *owner* is set to the requesting client
and other ACLs are set to empty `[]` if not otherwise specified in the
request.

#### Schema ACLs

A schema-level ACL describes what access to permit on the whole
schema. When not configured locally, the effective schema-level ACL is
inherited from the catalog.

During schema creation, the *owner* is set to the requesting client or
to `null` if the client is also an owner of the catalog; all other
schema ACLs are set to `null` if not otherwise specified in the
request.

#### Table ACLs

A table-level ACL describes what access to permit on the whole
table. When not configured locally, the effective table-level ACL is
inherited from the schema.

During table creation, the *owner* is set to the requesting client or
to `null` if the client is also an owner of the table; all other
table ACLs are set to `null` if not otherwise specified in the
request.

[Dynamic table-level ACL bindings](#dynamic-table-acls) can augment
table-level ACLs to enable access to only a subset of data rows.

All static and dynamic table ACLs are disjunctively considered when
deciding access.

#### Column ACLs

A column-level ACL describes what access to permit on the whole
column. When not configured locally, the effective column-level ACL is
inherited from the table.

During column creation, the *owner* is set to the requesting client or
to `null` if the client is also an owner of the column; all other
column ACLs are set to `null` if not otherwise specified in the
request.

[Dynamic column-level ACL bindings](#dynamic-column-acls) can augment
column-level ACLs to enable access to only a subset of data fields in
this column.

[Dynamic constraint-level ACL bindings](#dynamic-reference-acls) can
augment column-level ACLs to enable expression of only a subset of
data in a column governed by that constraint.

All static and dynamic column ACLs are disjunctively considered when
deciding access.

### Dynamic ACL Bindings

Dynamic ACL bindings configure sources of ACL content associated with
each individual tuple or datum, i.e. a query which projects
user attributes out of the data catalog itself:

1. An arbitrary *name* of each ACL binding facilitates subsequent management tasks on the policy.
2. The predefined *type* of each ACL binding identifies the type of access governed.
3. The *resource* to which the ACL binding is attached identifies the scope of the access governed.
4. The *projection* of each ACL binding describes how to retrieve ACL content.

ACL binding projections are a form of ERMrest attribute query in which
the query path and projection syntax is specified without the base
table instance. The base table instance is implicitly defined by the
resource scope in which the binding is declared.

### Dynamic Defaults

TBD. Provide some remotely manageable mechanism to do basic
provenance-tracking idioms where we currently need to use SQL
triggers?

#### Dynamic Table ACLs

A table-level ACL binding describes how to retrieve ACLs which govern
access to rows of a table.

- The base table for the projection is the bound table itself.
  - ACLs can be stored in columns of the table itself
  - ACLs can be stored in related entities
- Governed access modes cover whole-entity access:
  - Row visibility
  - Insert
  - Update
  - Delete

#### Dynamic Column ACLs

A column-level ACL binding describes how to retrieve ACLs which govern
access to fields within rows of a table.

- The base table for the projection is the enclosing table resource for the bound column.
  - ACLs can be stored in sibling columns of the same table
  - ACLs can be stored in related entities
- Governed access modes cover individual field (table cell) access:
  - Datum visibility
  - Datum expression during row inserts
  - Datum mutation during row updates
  
Column-level dynamic ACLs are not involved in row deletion decisions.

#### Dynamic Reference ACLs

A reference-level ACL binding describes how to retrieve ACLs which
govern access to fields within rows of a table which are subject to a
foreign key reference constraint.

- The base table for the projection is the referenced table resource for the bound reference constraint.
  - ACLs can be stored in sibling columns of the referenced key
  - ACLs can be stored in related entities of the referenced domain
- Governed access modes cover individual domain datum access:
  - Reference visibility
  - Reference expression during row inserts
  - Reference mutation during row updates
  
Reference-level dynamic ACLs are not involved in row deletion decisions.

## Technical Reference

### Available ACL Names

All of the previously described [access modes](#access-modes) have a
corresponding ACL name associated with them.

| ACL Name      | Mode         | Implies                |
|---------------|--------------|------------------------|
| owner         | Own          | \*                     |
| model\_write  | Write model  | model\_\*, data\_\*    |
| model\_insert | Insert model |                        |
| model\_update | Update model | model\_read            |
| model\_delete | Delete model | model\_read            |
| model\_read   | View model   |                        |
| data\_write   | Write data   | model\_read, data\_\*  |
| data\_insert  | Insert data  | model\_read            |
| data\_update  | Modify data  | model\_read, data\_read |
| data\_delete  | Delete data  | model\_read, data\_read |
| data\_read    | View data    | model\_read            |

- Ownership rights imply all access rights to the same resource.
- Model mutation rights imply model viewing rights to the same resource.
- Data access rights imply model viewing rights to the same resource.
- Data mutation rights imply data viewing rights to the same data.

### ACL Representation

The data-independent ACLs are encoded in an `"acls"` sub-resource of the
governed resource. This is a hash-map keyed by ACL name. For example,
a schema resource has a canonical representation as in the following
example:

    {
	  "schema_name": "My Schema",
	  "comment": "The purpose of My Schema is...",
	  "annotations": ...,
	  "tables": ...,
	  "acls": {
	    "owner": ["some/user/URI"],
		"model_read": ["*"]
	  }
	}

This example has locally configured ACLs for the schema owner and the
schema readers, but inherits other ACLs from the enclosing
catalog. For brevity, ACL names with `null` configuration are omitted
from the canonical representation. Specifying each such ACL name with 
a literal `null` has the same meaning.

### ACL Management

The ACL sub-resources are managed by a simple REST API. They can be
embedded in the enclosing resource description during resource update
or resource retrieval. For ACL management on existing resources, a
sub-API is supported on each resource to address one ACL by name.

- `.../acl`: collection of all named ACLs
  - GET: retrieve ACL collection
  - PUT: replace ACL collection
  - DELETE: unconfigure ACL collection
- `.../acl/name`: individually named ACL
  - GET: retrieve one ACL
  - PUT: replace one ACL
  - DELETE: unconfigure one ACL

An ACL collection returns a JSON representation identical to that
described previously, providing an object keyed by ACL name where
unconfigured ACLs are omitted. Each individual ACL is a JSON array of
strings.

| Governed Resource | Example ACL URL                                                   |
|-------------------|-------------------------------------------------------------------|
| Catalog           | /catalog/N/acl/owner |
| Schema            | /catalog/N/schema/S/acl/owner |
| Table             | /catalog/N/schema/S/table/T/acl/owner |
| Column            | /catalog/N/schema/S/table/T/column/C/acl/owner |

### Available Dynamic ACL Types

Some of the previously described [access modes](#access-modes) have a
corresponding dynamic ACL type associated with them.

| ACL Type     | Mode         | Implies                |
|--------------|--------------|------------------------|
| data\_owner  | Own data     | data\_\*               |
| data\_insert | Insert data  |                        |
| data\_update | Modify data  | data\_read             |
| data\_delete | Delete data  | data\_read             |
| data\_read   | View data    |                        |

- Dynamic data rights do not imply model access. Model access must be determined in a data-independent manner.
- Dynamic ownership rights imply all dynamic data access rights to the same data.
- Dynamic data mutation rights imply dynamic data viewing rights to the same data.
- Dynamic insertion rights are only applicable to foreign key reference constraints where they govern the use of a domain datum during insertion to the referring table.

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
		"data_write": ["some/curator/URI"]
	  },
	  "acl_bindings": {
	    "My Row Owners": {
		  "type": "data_owner",
		  "projection": "Managed%20By"
		}
	  }
	}

This example has an explicitly set, data-independent curator group who
can modify all rows in the table, while other data-independent ACLs
are inherited from the enclosing schema. A dynamic ACL binding called
`My Row Owners` specifies that an ACL stored in the `Managed By`
column of the table grants `data_owner` access type for individual
rows.

#### Projection Strings

The `"projection"` field of the ACL binding is a string using the
ERMrest URL syntax defined for the `/attribute/` API. It assumes that
a *base row query* similar to
`/ermrest/catalog/N/attribute/Base/key=X` will be formulated by the
system, and the projection string is the suffix necessary to turn this
into an ACL projection query. E.g. in the
[dynamic ACL example](#dynamic-acl-binding-representation) above, the
projection string `Managed%20By` could be appended to a base-row URL
to form a complete ACL projection query:

    /ermrest/catalog/N/attribute/My%20Schema:My20Table/key=X/Managed%20By

The projection MUST be a single column of type `text` or
`text[]`. Zero or more rows MAY be returned for a given base URL,
representing the dynamic ACL content for that one base row. For type
`text`, the effective ACL is the aggregated list of all returned text
values, each representing one user attribute. For type `text[]`, the
effective ACL is the union of all returned arrays, each containing
zero or more user attributes.

### Dynamic ACL Binding Management

The ACL binding sub-resources are managed by a simple REST API. They
can be embedded in the enclosing resource description during resource
update or resource retrieval. For ACL binding management on existing
resources, a sub-API is supported on each resource to address one ACL
binding by name.

- `.../acl_binding`: collection of all named ACL bindings
  - GET: retrieve ACL binding collection
  - PUT: replace ACL binding collection
  - DELETE: unconfigure ACL binding collection
- `.../acl_binding/name`: individually named ACL binding
  - GET: retrieve one ACL
  - PUT: replace one ACL
  - DELETE: unconfigure one ACL

An ACL binding collection returns a JSON representation identical to
that described previously, providing an object keyed by ACL binding
name. Each individual ACL binding is a JSON object with `"type"` and
`"projection"` fields.

| Governed Resource | Example ACL Binding URL                                           |
|-------------------|-------------------------------------------------------------------|
| Table             | /ermrest/catalog/N/schema/S/table/T/acl\_binding/My%20Binding |
| Column            | /ermrest/catalog/N/schema/S/table/T/column/C/acl\_binding/My%20Binding |
| Foreign Key       | /ermrest/catalog/N/schema/S/table/T/foreignkey/C1/reference/S2:T2/C2/acl\_binding/My%20Binding |

## Usage Scenarios

More illustrations might be helpful. Or, a separate cookbook document?

### Backwards-Compatible Catalog ACLs

To get the same effective behavior as older versions of ERMrest, set
catalog-level ACLs, leave all other sub-resource ACLs as unconfigured
`null` values, and do not define any dynamic ACL bindings.

### Sparse Table Restrictions

Starting with a
[backwards-compatible catalog scenario](#backwards-compatible-catalog-acls),
set a more limited ACL on one table. This table will now be subject to
more stringent access requirements than the rest of the catalog.

### Sparse Table Exposure

Starting with a
[backwards-compatible catalog scenario](#backwards-compatible-catalog-acls),
set a more inclusive ACL on one table. This table will now be subject
to less stringent access requirements than the rest of the catalog.

### Sparse Row-Level Restrictions

Starting with a
[restricted table scenario](#sparse-table-restrictions), make sure the
table-level ACLs exclude a class of user to whom you wish to grant
limited row-level rights (dynamic ACLs are only effective if they
grant extra permissions that are not already granted by a
data-independent policy). Then, add a dynamic ACL binding which can
selectively grant access on a row-by-row basis.

