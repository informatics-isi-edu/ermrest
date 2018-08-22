
# Access Control

**NOTE**: much of the documentation previously found here has been
merged into the [ERMrest API docs](../api-doc/index.md) since it is
now part of the service interface.  What remains here are a few notes
and sketches pertaining to possible future development.

## Proposal for Domain queries

The `"domain_queries"` sub-document on a foreign key will specify an
ERMrest query URL which shows the set of allowed values for a given
access mode. For foreign keys with dynamic ACL bindings, this query
may encode extra filtering on the domain. Without dynamic ACL
bindings, the query simply encodes the source of the domain values for
the foreign-key reference constraint.

## Proposal for Row-Level Rights Summary

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

