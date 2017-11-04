
# ERMrest Access Control

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
	- Keys and foreign keys will be hidden if their constituent columns disallow data selection.
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

### Row-Level Rights Summary

When dynamic ACL bindings are in effect, the static rights described
in the preceding section MAY replace the boolean `true` or `false`
access right decision with `null` meaning the decision cannot be
statically determined. In this case, a row-level rights summary can
be consulted to understand access rights on existing data.

### Predicting Access Decisions

To predict whether a given request will be permitted, all of the
static and row-level rights summaries must be consulted together:

1. All involved model resources must be visible in the enumerated model document.
2. The operation must be allowed by all involved model resources
   - Model rights must allow model access operations
   - Static data-access rights must not disallow data access operations
      - Affected table or tables must not disallow access in rights advertised on table
      - Affected column or columns must not disallow access in rights advertised on columns
3. Row-dependent access rights must not disallow access on existing data
   - Affected rows must be visible in a query
   - Affected row rights must not disallow data modification operations

Keep in mind, even when all rights seem to allow an operation, the
subsequent operation may still fail due to either asynchronous changes
to server state or due to other integrity constraints and operational
considerations not included in the policy system introspection.

