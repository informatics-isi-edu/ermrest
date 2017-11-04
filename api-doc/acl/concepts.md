
# ERMrest Access Control

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
- A key constraint is only visible if the columns it governs are selectable.
- A foreign key constraint is only visible if the columns it governs are selectable.

The last two dependencies above are more strict than necessary.  A
constraint can be well-defined if its constituent columns are
enumerable. But, in practice most clients cannot do anything useful
with the constraint unless it can also see the data, and the presence
of the useless constraint would only confuse most model-driven clients.

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
references to be expressed.

Reference ACLs are set to `["*"]` if not otherwise specified in the
request.  In practice, reference ACLs are less often restricted and so
this default simplifies common configurations. A model which needs to
restrict expression of foreign keys SHOULD explicitly override the
default ACLs; to completely disable expression of foreign keys, the
reference ACL set `{"insert": [], "update": []}` MAY be used.

Reference constraints are considered part of the enclosing table
resource and do not have separable ownership.

[Dynamic reference ACL bindings](#dynamic-reference-acls) can augment
reference ACLs to enable expression of only a subset of data in a
column governed by that reference constraint. These ACLs are actually
managed on foreign key reference constraints, but their effect is to
limit what new values can be expressed in the foreign key's
constituent columns.

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
  
Column-level dynamic ACLs are not involved in row insertion nor
deletion decisions.

As a convenience, columns inherit the dynamic ACL bindings of their
table. Thus, if no column-level ACL bindings are specified, the column
allows whatever operation the table would allow for that row. The
column-level policy MAY apply a special binding value of `false` to
suppress an ACL binding inherited from the table under the same name.

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

