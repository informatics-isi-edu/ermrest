# Deprecated textfacet API

The entire /textfacet API was an undocumented experiment.  It is now
**DEPRECATED** and will disappear in some future release. The
original implementation was replaced with the addition of fine-grained ACLs features.
It provides some transitional backwards-compatibility.

## Configuring textfacet API

Temporary config options:

- `"textfacet_policy": false` (default)
   - API quickly returns zero matches
- `"textfacet_policy": true`
   - API returns matches for table column where the client has **static** `select` rights
   - the API may search all tables
   - this may be too slow on very large schemas and databases
- `"textfacet_policy":` _policy_
   - a hierarchical policy for individual schemas, tables, columns

Format for the hierarchical _policy_:

1. Top level is a catalog-wide policy map
2. Second level is a per-schema policy map
3. Third level is a per-table policy map
4. Fourth level is a per-column policy boolean

The hierarchical policy can be truncated at any mapping level with a
`true` or `false` value to set a common decision for all
descendants. Each mapping level may also be sparse and the default
`false` policy is applied to any model elements not configured by the
policy document.

Example:

    {
      "S1": true,
      "S2": {
        "T1": true,
        "T2": {
          "C1": true
        }
      }
    }

Interpreting example (subject to static `select` rights checks):

- Everything in schema `S1` will be considered
- Every column in `S2`:`T1` will be considered
- Column `S2`:`T2`:`C1` will be considered
- All other schemas, e.g. `S3`... will be excluded
- All other tables in `S2`, e.g. `T3`... will be excluded
- All other columns in `S2`:`T2`, e.g. `C2`... will be excluded

## Tuning performance

The current implementation produces a large SQL `UNION ALL` query
where each sub-query searches one candidate column.

The core sub-query is a case-insensitive regular expression query
with a `WHERE` clause of the form:

    WHERE _ermrest.astext("column name") ~* 'pattern'

Hence, tuning the performance of this interface involves several
choices:

1. Having an appropriate tri-gram index for the `WHERE` clauses
2. Using policy to limit the number of columns in the search
3. Adjusting PostgreSQL query planner settings

Because this interface is deprecated, we do not anticipate significant
implementation improvements before it is finally removed from a future
version of ERMrest.
