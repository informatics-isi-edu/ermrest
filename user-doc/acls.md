
# ERMrest Access Control

## Overall Goals

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
    - Help clients anticipate authorization decisions to customize GUI presentations etc.
3. Allow for efficient and correct implementation of the authorization decisions within ERMrest.
    - Pre-evaluate static policies before accessing data.
	- Compile data-dependent decisions into SQL queries.
	- Produce SQL amenable to fast query plans.
4. Limit policy model to access-control list metaphors:
    - Effective ACL can be determined for given resource access decision.
    - Decision based on intersection of client attributes with effective ACL.
	- No attempt to address arbitrary computable decisions as allowed in PostgreSQL RLS policy expressions.

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
	- Delegation doesn't take away original owner rights, i.e. nothing in a resource tree is hidden from root owner
    - Authorize additional owners for sub-resources
	- Delegate management of specific table's structure and constraints
    - Delegate creation of new schema (while protecting other schemas)
	- Delegate creation of new table (while protecting other tables)
4. Make sure simple policies are still simple to manage
    - Entire catalog visible to one group
	- Entire catalog data mutable by one group
	- Entire catalog model managed by one group
	
