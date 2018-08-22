
# Static ACL Technical Reference

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

### Restrictions on Wildcard Policies

The wildcard ACL entry `"*"` matches any client including anonymous
users. For safety, ERMrest will not accept ACLs containing wildcards
for ACLs granting mutation privileges. For existing catalogs which may
have acquired such policies before this safety check was introduced,
anonymous clients will be rejected for mutation requests, even though
the existing ACL has a wildcard.

The wildcard is only permitted for:

1. The `"enumerate"` ACL name, allowing model elements to be seen.
2. The `"select"` ACL name, allowing data to be queried.
3. The `"insert"` and `"update"` ACL names on foreign key constraints.
   - Unlike other resources, foreign keys have a default ACL value of `["*"]` rather than `null`. This idiom is preserved for convenience.
   - To actually mutate data in the catalog, the client must also have mutation rights on the table row and table columns, so safety is maintained.
