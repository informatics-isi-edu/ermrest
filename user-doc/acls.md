
# ERMrest Access Control

## Scope of Use Cases to Address

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
    - Authorize additional owners for sub-resources (can't suppress/mask parent owners from sub-resources)
	- ~~Delegate management of specific table's structure and constraints~~
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

We will initially require policy administrators to reconcile most of
these problems by forming well coordinated schemas and policies. In
some cases, we may be able to improve usability by having the system
automatically detect conflicts and/or reconcile them?

## Core Concepts

### Catalog Resource Hierarchy

Policy will be expressed over the hierarchical catalog model, with
policies attached to specific resources in the following model
hierarchy (already present in ERMrest catalog introspection):

- Catalog
	- Schema
		- Table
			- Column
			- Constraint

### Access Modes

A number of distinct access modes are defined such that permission can
be granted or denied for each mode separately. Some modes are short-hand
for a combination of distinct modes, where a general level of access
can be further sub-divided into very specific scenarios you might control
separately:

- Own model element (can do everything)
	- Create new child model element
	- Enumerate existing model element
	- Write data (can make any data change)
		- Reference to key
		- Insert new data
		- Modify existing data
		- Delete existing data
	- Select existing data

Ownership is not quite an access mode but convenient to think about as
the superior mode to all other modes.

The precise meaning of some data access modes varies by resource type:

| Mode   | Table              | Column                        | Reference     |
|--------|--------------------|-------------------------------|---------------|
| Insert | Create new row     | Set value during row insert   | Make reference to key (during row insert) |
| Update | Modify row         | Replace value                 | Make reference to key (during row update) |
| Delete | Remove row         | Reset to default value        | N/A           |
| Select | Observe/detect row | Observe/detect value          | N/A           |

Foreign key reference resources offer control of value expression:
rather than limiting what row or field can change, they can limit what
values are allowed to be placed into a field. They complement the row
and column-level access controls which can only consider the current
values of data rather than the proposed new value.

### Policy Scoping and Resource Dependencies

A policy attached to a resource will govern access to that
resource. Because many forms of access depend on multiple resources, a
complete request will be granted or denied based on the conjunction of
policies governing each resource involved in the request.

For example:
- Joined sets can only be viewed if all involved data can be viewed.
- Data can only be viewed if the enclosing table is visible.
- A table can only be accessed if its enclosing schema is visible.
- A schema can only be access if its enclosing catalog is visible.
- A column can only be modified if its governing reference constraints allow the new value.

### Data-Dependent Policies

Some, but not all, fine-grained access decisions involve data values.
Model-level Access Control Lists (ACLs) support *data-independent*
decisions, i.e. granting access to all rows of a table uniformly.
Dynamic ACL bindings support *data-dependent* decisions, i.e. granting
access to specific rows of a table.

Data-dependent policies can grant more selective rights to a client
that would not be possible with a static policy. The decision process
depends on the configured policy:

1. A data-access request is not well-formed if it depends model elements that are invisible to the client.
2. Data-visibility policies determine whether a request is allowed:
    - If data-independent policies permit an access, it is allowed
	- If data-dependent policies permit an access, it is allowed
	- If neither, it is denied
	
In practice, this means that ERMrest can statically solve some policy
decisions and make a decision without investigating actual data
values. But, in the worst case, it needs to include dynamic policy
checks to decide if a particular access is allowed or denied.

When data-dependent data viewing policies are active, the effective
result set is *filtered* by the visibility policy. When only static
viewing policies are in effect, the request will be denied rather than
returning an empty result set.

### Policy Inheritance and Implication

A resource owner **always owns all sub-resources**. Any sub-resource
ownership policy can only extend the privilege to more clients but can
never block the owners *inherited* from the enclosing resource.

Similarly, a more general access right **always implies all
sub-rights**. Any sub-mode policy can extend the privilege to more
clients but can never block the parent mode. For example, a client
with "data write" privileges also has "data insert" privileges, even
if the an explicit "data insert" policy is empty on the same resource.

For non-ownership policies, a locally unconfigured (`null`) policy on
a sub-resource means the policy will be inherited from the enclosing
resource. However, any other value including an empty policy (`[]`)
will *override* the inherited policy for that access mode. Thus,
lesser privileges may be selectively blocked on specific
sub-resources.

- A local policy can *restrict* access compared to the enclosing resource
    - One table is read-only in an otherwise read-write schema
    - One column is hidden in an otherwise read-write table
    - But ownership can never be restricted in sub-resources
- A local policy can *broaden* access compared to the enclosing resource
    - One table is writable in an otherwise read-only schema
    - One column is mutable in an otherwise read-only table
    - Ownership can be extended to more parties on sub-resources
- A more specific access mode can be *extended* to more clients
    - One table is writable by a curator group, and another group can only insert new rows
	- One column is writable by a curator group, and another group can only set values during row insertion
	- But a curator group with general write access can not be denied row insert access
- But, access decisions still involve resource dependencies
	- An invisible catalog hides all schemas inside it
	- An invisible schema hides all tables inside it
	- An invisible table hides all columns inside it

### Model-level ACLs

ACLs are distributed throughout the hierarchical model of the catalog.

1. The predefined *name* of each ACL identifies the type of access governed.
2. The *resource* to which the ACL is attached identifies the scope of the access governed.
3. The *content* of each ACL is a list of disjunctive matching choices which may include the wildcard `*` matching any client.

#### Catalog ACLs

A catalog-level ACL describes what access to permit on the whole
catalog. Catalogs do not inherit ACLs from elsewhere, so an
unconfigured catalog ACL is not possible.

During catalog creation the *owner* defaults to the requesting
client. Other ACLs are set to empty `[]` if not otherwise specified in
the request.

For catalogs and all other ERMrest resources described below, it is
impossible for a client to create or manage a resource while
disclaiming ownership in the request. They may set the ownership more
broadly, e.g. to a group for which they are a member, rather than
listing their client ID as the sole owner. But, they can never
configure a owner ACL which would prevent them from being an owner at
the end of the request. The only way to transfer resource ownership is
to add an additional owner, and then have that other owner strip the
original owner identity from the owner ACL. Alternatively, ownership
can be assigned to a particular owners group and then the group
membership can fluctuate due to external management without changing
the ERMrest ACL content.

#### Schema ACLs

A schema-level ACL describes what access to permit on the whole
schema. When not configured locally, the effective schema-level ACL is
inherited from the catalog.

During schema creation, the *owner* defaults to the requesting client
or to `null` if the client is also an owner of the catalog at the time
of creation; all other schema ACLs are set to `null` if not otherwise
specified in the request.

#### Table ACLs

A table-level ACL describes what access to permit on the whole
table. When not configured locally, the effective table-level ACL is
inherited from the schema.

During table creation, the *owner* defaults to the requesting client
or to `null` if the client is also an owner of the table at the time
of creation; all other table ACLs are set to `null` if not otherwise
specified in the request.

[Dynamic table-level ACL bindings](#dynamic-table-acls) can augment
table-level ACLs to enable access to only a subset of data rows.  The
presence of dynamic ACL bindings for data retrieval access modes
suppresses a `403 Forbidden` response which would otherwise be
generated in the absence of a static ACL granting read access;
instead, a `200 OK` response is generated where any denied row is
absent from the result set.

All static and dynamic table ACLs are disjunctively considered when
deciding row access. Any access denied decision for data modifying
requests will continue to raise a `403 Forbidden` response.

#### Column ACLs

A column-level ACL describes what access to permit on the whole
column. When not configured locally, the effective column-level ACL is
inherited from the table.

Columns are considered part of the enclosing table resource and do not
have separable ownership. Column ACLs are set to `null` if not
otherwise specified in the request.

[Dynamic column ACL bindings](#dynamic-column-acls) can augment
column-level ACLs to enable access to only a subset of data fields in
this column.  The presence of dynamic ACL bindings for data retrieval
access modes suppresses a `403 Forbidden` response which would
otherwise be generated in the absence of a static ACL granting read
access; instead, a `200 OK` response is generated where any denied
field is replaced with a NULL value.

#### Reference ACLs

A reference-level ACL describes whether to permit foreign key
references to be expressed. When not configured locally, the effective
reference-level ACL is inherited from the constituent foreign key
columns (any value is allowed if the column write would be allowed,
subject to normal foreign key reference integrity constraints).

Reference constraints are considered part of the enclosing table
resource and do not have separable ownership. Reference ACLs are set
to `null` if not otherwise specified in the request.

[Dynamic reference ACL bindings](#dynamic-reference-acls) can augment
column-level ACLs to enable expression of only a subset of data in a
column governed by that constraint. These bindings only affect data
modification requests. These ACLs are actually managed on foreign key
reference constraints, but their effect is to limit what new values
can be expressed in the foreign key's constituent columns.

### Dynamic ACL Bindings

Dynamic ACL bindings configure sources of ACL content associated with
each individual tuple or datum, i.e. a query which projects
user attributes out of the data catalog itself:

1. The predefined *type* of each ACL binding identifies the mode of access governed.
2. An arbitrary *name* of each ACL binding facilitates subsequent management tasks on the policy.
3. The *resource* to which the ACL binding is attached identifies the scope of the access governed.
4. The *projection* of each ACL binding describes how to retrieve ACL content.

ACL binding projections are a form of ERMrest attribute query in which
the query path and projection syntax is specified without the base
table instance. The base table instance is inferred from the resource
scope of the binding.

It is the responsibility of the data modeler to create self-consistent
policies. For example, a dynamic ACL binding is only effective for
access control if the ACL storage itself is protected from unwanted
changes. Because the ACL storage is within the database and subject to
data modification APIs, appropriately restrictive policies must be
defined to protect the stored ACL content.

### Dynamic Defaults

TBD. Provide some remotely manageable mechanism to do basic
provenance-tracking idioms where we currently need to use SQL
triggers?  I.e. store a client identity, client object, or some data
determined indirectly via a query constrained by client attributes?

#### Dynamic Table ACLs

A table-level ACL binding describes how to retrieve ACLs which govern
access to rows of a table.

- The base table for the projection is the bound table itself.
    - ACLs can be stored in columns of the table itself
    - ACLs can be stored in related entities
- Governed access modes cover whole-entity access:
    - Row visibility (invisible rows are filtered from results)
    - Row writing
        - Row update
        - Row delete

#### Dynamic Column ACLs

A column-level ACL binding describes how to retrieve ACLs which govern
access to fields within rows of a table.

- The base table for the projection is the enclosing table resource for the bound column.
    - ACLs can be stored in sibling columns of the same table
    - ACLs can be stored in related entities
- Governed access modes cover individual field (table cell) access:
    - Field visibility (invisible fields are replaced with NULLs)
	- Field writing
        - Field targeted during row updates
		- Field cleared by attribute deletes
  
Column-level dynamic ACLs are not involved in row deletion decisions.

#### Dynamic Reference ACLs

A reference-level ACL binding describes how to retrieve ACLs which
govern expression of data within fields which are subject to a foreign
key reference constraint.

- The base table for the projection is the referenced table resource, i.e. the domain table for the constraint.
    - ACLs can be stored in sibling columns of the referenced key
    - ACLs can be stored in related entities of the referenced entities
- Governed access modes cover individual domain datum access:
    - Value writing during row insertion or update
	
No access control distinction is allowed between reference value
insertion during row creation and reference value insertion during row
update.
  
Reference-level dynamic ACLs are not involved in row deletion
decisions nor in default value expression during row creation.

## Technical Reference

### Available Static ACL Names

Most of the previously described [access modes](#access-modes) have a
corresponding static ACL name associated with them. Some model access rights
are not separately controlled and instead require full ownership
rights. This might change in future revisions.

Because more general access mode rights imply lesser access mode
rights and sub-resources inherit ACLs, brevity in policy
configurations can be achieved:
- A small set of owners need not be repeated in other ACLs
- Less privileged roles are mentioned only in their corresponding lesser ACLs
- Sub-resource ACLs can be set to `null` unless local overrides are needed

Available ACL names and applicability to specific model elements:

| ACL Name  | Catalog    | Schema     | Table           | Column            | Reference         |
|-----------|------------|------------|-----------------|-------------------|-------------------|
| owner     | all access | all access | all access      | N/A *note1*       | N/A *note1*       |
| create    | add schema | add table  | N/A             | N/A               | N/A               |
| select    | *note2*    | *note2*    | observe row     | observe value     | N/A               |
| insert    | *note2*    | *note2*    | add row         | set value *note3* | set value *note3* |
| update    | *note2*    | *note2*    | change row      | set value *note3* | set value *note3* |
| write     | *note2*    | *note2*    | all data access | set value *note3* | set value *note3* |
| delete    | *note2*    | *note2*    | delete row      | N/A               | N/A               |
| enumerate | introspect | introspect | introspect      | introspect        | introspect        |

When a new schema is added to a catalog, or a new table is added to a
schema, the requesting client becomes the owner of the newly added
element.

Notes:
- `N/A`: The named ACL is not supported on this kind of model element.
- *note1*: Columns and references are considered part of the table and so cannot have local ownership settings.
- *note2*: Data access ACLs on catalogs and schemas only serve to set inherited access policies for the tables which are sub-resources within those containers respectively. These only have effect if the table does not have a locally configured policy for the same named ACL, and they grant no special access to the catalog or schema itself.
- *note3*: The insert/update ACLs on columns and references configure whether values can be supplied during that type of operation on the containing row.

As described previously, some access rights imply other rights:

| ACL Name  | Implies  |
|-----------|----------|
| enumerate |          |
| create    | enumerate |
| select    | enumerate |
| insert    | enumerate |
| update    | select, enumerate |
| delete    | select, enumerate |
| write     | insert, update, delete, select, enumerate |
| owner     | create, insert, update, delete, select, enumerate |

Ownership is inherited even if a sub-resource specifies a locally
configured owner ACL. The effective owner policy is the disjunction of
inherited owner and local owner policies. Other locally configured ACLs
override their respective inherited ACL and so may grant fewer rights
than would be granted with the inherited policy.

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
		"select": ["*"]
	  }
	}

This example has locally configured ACLs for the schema owner and
permits public access to enumerate the schema and select data, but
inherits other ACLs from the enclosing catalog. For brevity, ACL names
with `null` configuration are omitted from the canonical
representation. Specifying each such ACL name with a literal `null`
has the same meaning.

### ACL Management

The ACL sub-resources are managed by a simple REST API. They can be
embedded in the enclosing resource description during resource update
or resource retrieval. For ACL management on existing resources, a
sub-API is supported on each resource to address one ACL by name.

- `.../acl`: collection of all named ACLs
  - GET: retrieve ACL collection
  - PUT: replace all ACLs in collection
  - DELETE: unconfigure all ACLs in collection
- `.../acl/name`: individually named ACL
  - GET: retrieve one ACL
  - PUT: replace one ACL
  - DELETE: unconfigure one ACL

An ACL collection is the sub-resource described previously: an object
keyed by ACL name where unconfigured ACLs are omitted. Each individual
ACL is a JSON array of strings.

| Governed Resource | Example for ACL name `A`  |
|-------------------|---------------------------|
| Catalog           | /catalog/N/acl/A          |
| Schema            | /catalog/N/schema/S/acl/A |
| Table             | /catalog/N/schema/S/table/T/acl/A |
| Column            | /catalog/N/schema/S/table/T/column/C/acl/A |

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
		  "projection": "Managed%20By",
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

#### Projection Strings

The `"projection"` field of the ACL binding is a string using the
ERMrest URL syntax defined for the `/attribute/` API. It assumes that
a *base row query* similar to
`/ermrest/catalog/N/attribute/Base/key=X/` will be formulated by the
system, and the projection string is the suffix necessary to turn this
into an ACL projection query. E.g. in the
[dynamic ACL example](#dynamic-acl-binding-representation) above, the
projection string `Managed%20By` could be appended to a base-row URL
to form a complete ACL projection query:

    /ermrest/catalog/N/attribute/My%20Schema:My20Table/key=X/Managed%20By

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

| Governed Resource | Example ACL Binding URL                                       |
|-------------------|---------------------------------------------------------------|
| Table             | /ermrest/catalog/N/schema/S/table/T/acl\_binding/My%20Binding |
| Column            | /ermrest/catalog/N/schema/S/table/T/column/C/acl\_binding/My%20Binding |
| Foreign Key       | /ermrest/catalog/N/schema/S/table/T/foreignkey/C1/reference/S2:T2/C2/acl\_binding/My%20Binding |

## Access Decision Introspection

Because many user-interfaces benefit from anticipating policy
decisions and customizing the options presented to the user, ERMrest
exposes decision information summarizing the effects of currently
active policy. These rights summaries take into account the requesting
client's privileges.

The decision information is presented in different ways depending
on the resource and access mode:

1. An invisible catalog will raise an access error for all access requests.
2. An invisible model element will be omitted from the catalog introspection response and raise an error for all direct access or dependent access requests (i.e. a client guessing at model elements not shown in the introspection).
    - Schemas can be entirely hidden.
	- Tables can be entirely hidden.
	- Columns can be entirely hidden.
3. Some access rights will be advertised on model elements in the introspection document.
4. An invisible row or datum will be filtered during queries (both for data retrieval and queries in support of data-modifying requests).
5. Datum-specific access rights will be advertised on retrieved data rows.
6. Datum-specific expression rights will be advertised on foreign key reference constraints as a filtered domain query.

### Static Rights Summary

The `"rights"` sub-resources appear throughout the schema
introspection document to describe the requesting client's rights. The
following illustrates where these rights are distributed on sub-resources:

	{
	  "rights": {
	    "owner": bool,
	    "create": bool
	  },
	  "schemas": {
	    "S": {
	      "rights": {
		    "owner": bool,
	        "create": bool
	      },
	      "tables": {
	        "T": {
	          "rights": {
			    "owner": bool,
	            "insert": bool,
	            "update": bool,
	            "delete": bool,
	            "select": bool
	          },
	          "column_definitions": [
	            {
	              "name": "C",
	              "rights": {
	                "insert": bool,
	                "update": bool,
	                "delete": bool,
	                "select": bool
	              }
	            },
	            ...
	          ],
	   	      "foreign_keys": [
	            {
	              "domain_queries": {
					"insert": url,
					"update": url
	              },
	              ...
	            },
	            ...
	          ]
	        },
	        ...
	      }
	    },
	    ...
	  }
	}

Model enumeration access is not indicated through the `"rights"`
sub-document. Rather, a model element which does not grant enumeration
will be omitted from the catalog introspection results. The rights
sub-document does not include fields for all ACLs which may be present
on a given model element, but only for the subset of actual access
modes which apply to the model element itself. E.g. data access modes
can be configured globally on catalogs or schemas, but they only grant
actual access rights for operations applied to tables or columns.

The `"domain_queries"` sub-document on a foreign key will specify an
ERMrest query URL which shows the set of allowed values for a given
access mode. For foreign keys with dynamic ACL bindings, this query
may encode extra filtering on the domain. Without dynamic ACL
bindings, the query simply encodes the source of the domain values for
the foreign-key reference constraint.

### Row-Level Rights Summary

When dynamic ACL bindings are in effect, the static rights described
in the preceding section MAY replace the boolean `true` or `false`
access right decision with `null` meaning the decision cannot be
statically determined. In this case, a row-level rights summary can
be consulted to understand access rights on existing data.

The `ermrights` virtual column is available on data rows and has the following
structure in each row:

	{
	  "update": bool,
	  "delete": bool,
	  "column_rights": {
	    "Column Name": {
	      "update": bool,
	      "delete": bool
	    },
	    ...
	  }
	}

The `"update"` and `"delete"` fields describe row-level mutation
rights. The `"update"` field may again be `null` if an update decision
cannot be made for the entire row but instead must consider the scope
of affected fields within the row.  The `"column_rights"`
sub-document summarizes field-level rights within the row.

There are several compact encoding conventions for this document:

- The entire document may be `null` if static rights completely
  describe the client's access privileges.
- Individual columns may be omitted from the `"column_rights"`
  sub-document if static column rights completely describe the
  client's access privileges.
- Only `update` and `delete` access modes are summarized, since any
  query results will already be filtered to only show row or column
  data where `select` is `true`, and row-level policy cannot control
  insertion of new rows.
- The `"column_rights"` sub-document may be omitted if it is empty.

### Predicting Access Decisions

To predict whether a given request will be permitted, all of the
static and row-level rights summaries must be consulted together:

1. All involved model resources must be visible in the enumerated model document.
2. The operation must be allowed by all involved model resources
	- Model rights must allow model access operations
	- Static data-access rights must not disallow data access operations
		- Affected table or tables must not disallow access in rights advertised on table
		- Affected column or columns must not disallow access in rights advertised on columns
		- Foreign key values must be found in domain queries advertised on foreign key reference constraints
3. Row-dependent access rights must not disallow access on existing data
	- Affected rows must be visible in a query
    - Affected row rights must not disallow data modification operations
	- Affected row-column rights must not disallow data modification operations

Keep in mind, even when all rights seem to allow an operation, the
subsequent operation may still fail due to either asynchronous changes
to server state or due to other integrity constraints and operational
considerations not included in the policy system introspection.

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

