# ERMrest Data Resource Naming

The [ERMrest](http://github.com/informatics-isi-edu/ermrest) data resource names always have a common structure:

- _service_ `/catalog/` _cid_ `/` _api_ `/` _path_
- _service_ `/catalog/` _cid_ `/` _api_ `/` _path_ _suffix_
- _service_ `/catalog/` _cid_ `/` _api_ `/` _path_ _suffix_ `?` _query parameters_
    
where the components in this structure are:

- _service_: the ERMrest service endpoint such as `https://www.example.com/ermrest`.
- _cid_: the catalog identifier for one dataset such as `42`.
- _api_: the API or data resource space identifier such as `entity`, `attribute`, `attributegroup`, or `aggregate`.
- _path_: the data path which identifies one filtered entity set with optional joined context.
- _suffix_: additional content that depends on the _api_
  - the group keys associated with `attributegroup` resources
  - the projection associated with `attribute`, `attributegroup`, and `aggregate` resources
- _query parameters_: optional parameters which may affect interpretation of the data name

## Entity Names

The `entity` resource space denotes whole entities using names of the form:

- _service_ `/catalog/` _cid_ `/entity/` _path_

The primary naming convention, without query parameters, denotes the final entity set referenced by _path_, as per the [data path rules](#data-paths). The denoted entity set has the same tuple structure as the final table instance in _path_ and may be a subset of the entities based on joining and filtering criteria encoded in _path_. The set of resulting tuples are distinct according to the key definitions of that table instance, i.e. any joins in the path may be used to filter out rows but do not cause duplicate rows.

## Attribute Names

The `attribute` resource space denotes projected attributes of entities using names of the form:

- _service_ `/catalog/` _cid_ `/attribute/` _path_ `/` _column reference_ `,` ...

The _path_ is interpreted identically to the `entity` resource space. However, rather than denoting a set of whole entities, the `attribute` resource space denotes specific fields *projected* from that set of entities.  The projected _column reference_ list elements can be in one of several forms:

- [ _out alias_ `:=` ] _column name_
  - A field is projected from the final table instance of _path_.
  - An optional _out alias_ can be assigned to rename the output column, and by default the output column will be named by the unqualified _column name_.
- `*`
  - A wildcard that expands to all of the columns from the final table instance of _path_.
  - The output columns are automatically named by their unqualified column names.
- [ _out alias_ `:=` ] _alias_ `:` _column name_
  - A field is projected from a table instance bound to _alias_ in _path_.
  - An optional _out alias_ can be assigned to rename the output column, and by default the output column will be named by the unqualified _column name_.
- _alias_ `:` `*`
  - A wildcard that expands to all of the columns from a table instance bound to _alias_ in _path_.
  - The output columns are automatically named by their _alias_ qualified column names to prevent collisions between the multiple wildcard-expansions that are possible within one complex _path_. If a projection `A:*` is used for a table instance with a column named `foo` in it, the output data will then have a column with the literal name `A:foo`. Special attention must be paid when trying to reference such columns using the [sort modifier](#sort-modifier), as this modifier uses the output name `A:foo` as a user-supplied literal and therefore the `:` must be escaped as in `@sort(A%3Afoo)`.

Like in the `entity` resource space, joined tables may cause filtering but not duplication of rows in the final entity set. Thus, when projecting fields from aliased table instances in _path_, values are arbitrarily selected from one of the joined contextual rows if more than one such row was joined to the same final entity.

## Aggregate Names

The `aggregate` resource space denotes computed (global) aggregates using names of the form:

- _service_ `/catalog/` _cid_ `/aggregate/` _path_ `/` _aggregate_ `,` ...

The _path_ is interpreted identically to the `attribute` resource space. However, rather than denoting a set of whole entities, the `aggregate` resource space denotes a single aggregated result computed over that set. The computed _aggregate_ list elements can be in one of several forms:

- _out alias_ `:=` _function_ `(` _column name_ `)`
- _out alias_ `:=` _function_ `(*)`
- _out alias_ `:=` _function_ `(` _in alias_ `:` _column name_ `)`
- _out alias_ `:=` _function_ `(` _in alias_ `:` `*` `)`

The _out alias_ is the name given to the computed field. The _function_ is one of a limited set of aggregate functions supported by ERMrest:

  - `min`: the minimum non-NULL value (or NULL)
  - `max`: the maximum non-NULL value (or NULL)
  - `cnt_d`: the count of distinct non-NULL values
  - `cnt`: the count of non-NULL values
  - `array`: an array containing all values (including NULL)

These aggregate functions are evaluated over the set of values projected from the entity set denoted by _path_. The same column resolution rules apply as in other projection lists: a bare _column name_ MUST reference a column of the final entity set while an alias-qualified column name MUST reference a column of a table instance bound to _alias_ in the _path_.

As a special case, the psuedo-column `*` can be used in several idiomatic forms:

  - `cnt(*)`: a count of entities rather than of non-NULL values is computed
  - `array(`_alias_`:*)`: an array of records rather than an array of values is computed

TODO: document other variants?

## Attribute Group Names

The `attributegroup` resource space denotes groups of entities by arbitrary grouping keys and computed (group-level) aggregates using names of the form:

- _service_ `/catalog/` _cid_ `/attributegroup/` _path_ `/` _group key_ `,` ...
- _service_ `/catalog/` _cid_ `/attributegroup/` _path_ `/` _group key_ `,` ... `;` _aggregate_ `,` ...

The _path_ is interpreted slightly differently than in the `attribute` resource space. Rather than denoting a set of entities drawn from the final table instance in _path_, it denotes a set of entity combinations, meaning that there is a potential for a combinatoric number of records depending on how path entity elements are linked. This denoted set of entity combinations is reduced to groups where each group represents a set of entities sharing the same _group key_ tuple, and optional _aggregate_ list elements are evaluated over this set of entities to produce a group-level aggregate value.

The _group key_ list elements use the same notation as the _column reference_ elements in the `attribute` resource space. The _aggregate_ list elements use the same notation as the _aggregate_ elements in the `aggregate` resource space or the _column reference_ elements in the `attribute` resource space. An _aggregate_ using _column reference_ notation denotes an example value chosen from an arbitrary member of each group.

## Data Paths

ERMrest introduces a general path-based syntax for naming data resources with idioms for navigation and filtering of entity sets. The _path_ element of the data resource name always denotes a set of entities or joined entities.  The path must be interpreted from left to right in order to understand its meaning. The denoted entity set is understood upon reaching the right-most element of the path and may be modified by the resource space or _api_ under which the path occurs.

### Path Root

A path always starts with a direct table reference:

- _table name_
- _schema name_ `:` _table name_

which must already be defined in the catalog under the corresponding model resource:

- `/schema/` _schema name_ `/table/` _table name_

The unqualified _table name_ MAY be used in a path if it is the only occurrence of that table name across all schemata in the catalog, i.e. only if it is unambiguous.

A path consisting of only one table reference denotes the entities within that table.

### Path Filters

A filter element can augment a path with a filter expression:

- _parent path_ `/` _filter_

after which the combined path denotes a filtered subset of the entities denoted by _parent path_ where the _filter_ expressed in the [filter language](#filter-language) evaluates to a true value.  The accumulative affect of several filter path elements is a logical conjunction of all the filtering criteria in those elements. It is also intuitive to think of a chain of filter elements as a filtering pipeline or sieve, each eliminating data which does not match the filter criteria.

### Entity Links

An entity link element can augment a path with an additional related or joined table:

- _parent path_ `/` _table name_
- _parent path_ `/` _schema name_ `:` _table name_

as in the path root, _table name_ may be explicitly schema qualified or left unqualified if it is unambiguous within the catalog. In order for this basic table link element to be valid, there must be an unambiguous foreign-key relationship linking the entity set denoted by _parent path_ and the table denoted by _table name_. The link may point in either direction, i.e. the _parent path_ entity set may contain foreign keys which reference _table name_ or _table name_ may contain foreign keys which reference the _parent path_ entities.

When there are multiple possible linkages to choose from, such a basic entity link element is ambiguous. In these cases, a more precise entity link element can identify an endpoint of the linkage as a set of columns:

- _parent path_ `/(` _column name_, ... `)`
- _parent path_ `/(` _table name_ `:` _column name_, ... `)`
- _parent path_ `/(` _schema name_ `:` _table name_ `:` _column name_, ... `)`

This set of columns MUST comprise either a primary key or a foreign key which unambiguously identifies a single possible linkage between the _parent path_ and a single possible linked entity table.  The resolution procedure for these column sets is as follows:

1. Column resolution:
  1. Each bare _column name_ MUST be a column of the entity set denoted by _parent path_;
  1. Each qualified name pair _table name_ `:` _column name_ MUST be a column in a table instance within _parent path_ if _table name_ is bound as an alias in _parent path_ (see following sub-section on table instance aliases);
  1. Each qualified name pair _table name_ `:` _column name_ MUST be a column in a table known unambiguously by _table name_ if _table name_ is not bound as an alias in _parent path_;
  1. Each qualified name triple _schema name_ `:` _table name_ `:` _column name_ MUST be a column within a table in the catalog.
1. Endpoint resolution:
  1. All columns in the column set MUST resolve to the same table in the catalog or the same table instance in the _parent path_;
  1. The set of columns MUST comprise either a foreign key or a key in their containing table but not both.
1. Link resolution:
  1. If the endpoint is a key or foreign key in a table in the catalog, that endpoint MUST unambiguously participate in exactly one link between that table and the entity set denoted by _parent path_;
  1. If the endpoint is a key or foreign key of a table instance in _parent path_ (whether referenced by alias-qualified or unqualified column names), that endpoint MUST unambiguously participate in exactly one link between that table instance and exactly one table in the catalog.
  
The path extended with an entity link element denotes the entities of a new table drawn from the catalog and joined to the existing entities in _parent path_, with the default entity context of the extended path being the newly joined (i.e. right-most) table instance.

### Table Instance Aliases

The root element or an entity link element may be decorated with an alias prefix:

- _alias_ `:=` _table name_
- _parent path_ `/` _alias_ `:=` _table name_
- _parent path_ `/` _alias_ `:=(` _column name_, ... `)`

This denotes the same entity set as the plain element but also binds the _alias_ as a way to reference a particular table instance from other path elements to the right of the alias binding. All aliases bound in a single path must be distinct. The alias can form a convenient short-hand to avoid repeating long table names, and also enables expression of more complex concepts not otherwise possible.

### Path Context Reset

A path can be modified by resetting its denoted entity context:

- _parent path_ `/$` _alias_

where _alias name_ MUST be a table instance alias already bound by an element within _parent path_.

This has no effect on the overall joining structure nor filtering of the _parent path_ but changes the denoted entity set to be that of the aliased table instance. It also changes the column resolution logic to attempt to resolve unqualified column names within the aliased table instance rather than right-most entity link element within _parent path_.

A path can chain a number of entity link elements from left to right to form long, linear joining structures. With the use of path context resets, a path can also form tree-shaped joining structures, i.e. multiple chains of links off a single ancestor table instance within the _parent path_.  It can also be used to "invert" a tree to have several joined structures augmenting the final entity set denoted by the whole path.

## Filter Language

The [filter element](#path-filters) of data paths uses a general filter language described here. There are unary and binary filter predicates, logical combinations, negation, and parenthetic grouping. Together, these language elements allow arbitrarily complex boolean logic functions to be expressed directly, in [conjunctive normal form](#conjunctive-normal-form), or in [disjunctive normal form](#disjunctive-normal-form).

The operator precedence is as follows:

1. Parenthetic grouping overrides precedence, causing the expression inside the parenthetic group to be evaluated and its result used as the value of the parenthetic group.
1. Negation has the highest precedence, negating the immediately following predicate or parenthetic group.
1. Conjunction using the `&` operator has the next highest precedence, combining adjacent parenthetic groups, negated predicates, predicates, and conjunctions.
1. Disjunction using the `;` operator has the next highest precedence, combining adjacent parenthetic groups, negated predicates, predicated, conjunctions, and disjunctions.
1. The path separator `/` has the lowest precedence, adding complete logical expressions to a path.

### Unary Filter Predicate

A unary predicate has the form:

- _column reference_ _operator_

There is currently only one unary operator, `::null::`, which evaluates True if and only if the column is NULL for the row being tested.

### Binary Filter Predicate

A binary predicate as the form:

- _column reference_ _operator_ _literal value_

| operator | meaning | notes |
|----------|---------|-------|
| `=`| column equals value | |
| `::lt::` | column less than value | |
| `::leq::` | column less than or equal to value | |
| `::gt::` | column greater than value | |
| `::geq::` | column greater than or equal to value | |
| `::regexp::` | column matches regular expression value | also allowed on `*` free-text psuedo column |
| `::ciregexp::` | column matches regular expression value case-insensitively | also allowed on `*` free-text psuedo column |
| `::ts::` | column matches text-search query value | also allowed on `*` free-text psuedo column |

### Negated Filter

Any predicate or parenthetic filter may be prefixed with the `!` negation operator to invert its logical value:

- `!` _predicate_
- `!` `(` _logical expression_ `)`

The negation operator has higher precedence than conjunctive or disjunctive operators, meaning it negates the nearest predicate or parenthetic expression on the right-hand side before logical operators apply.

### Parenthetic Filter

Any predicate, conjunction, or disjunction may be wrapped in parentheses to override any implicit precedence for logical composition:

- `(` _logical expression_ `)`

### Conjunctive Filter

A conjunction (logical AND) uses the `&` separator: 

- _predicate_ `&` _conjunction_
- _predicate_ `&` _predicate_
- _predicate_ `&` `!` _predicate_
- _predicate_ `&` `(` _logical expression_ `)`
- _predicate_ `&` `!` `(` _logical expression_ `)`

Individual filter elements in the path are also conjoined (logical AND), but the path separator `/` cannot appear in a parenthetic group. 

### Disjunctive Filter

A disjunction (logical OR) uses the `;` separator:

- _predicate_ `;` _disjunction_
- _predicate_ `;` _conjunction_
- _predicate_ `;` _predicate_
- _predicate_ `;` `!` _predicate_
- _predicate_ `;` `(` _logical expression_ `)`
- _predicate_ `;` `!` `(` _logical expression_ `)`

### Conjunctive Normal Form

A filter in conjunctive normal form (CNF) is a conjunction of disjunctions over a set of possibly negated predicate terms. To write a CNF filter in a data resource name, use a sequence of filter path elements, separated by `/`, to express the top-level conjunction.  Use the disjunction separator `;` and optional negation prefix `!` on individual predicate terms in each disjunctive clause.

### Disjunctive Normal Form

A filter in disjunctive normall form (DNF) is a disjunction of conjunctions over a set of possibly negated predicate terms. To write a DNF filter in a data resource name, use a single filter path element using the `;` separator to express the top-level disjunction. Use the conjunction separator `&` and optional negation prefix `!` on individual predicate terms in each conjunctive clause.

## Sort Modifier

An optional sorting modifier can modify the ordering of elements in the set-based resources denoted by `entity`, `attribute`, and `attributegroup` resource names. This modifier applies sorting based on output columns available in the set-based resource representation and may increase service cost significantly. The modifier has the form:

- `@sort(` _output column_ `,` ... `)`
- `@sort(` _output column_ `::desc::` `,` ... `)`

where the optional `::desc::` direction indicator can apply a descending sort to that sort key to override the default ascending sort order. The list of sort keys goes left-to-right from primary to secondary etc.  The individual _output column_ names are user-supplied values and therefore must be URL-escaped if they contain any special characters, including the `:` character in implicitly named output columns introduced using the _alias_ `:` `*` wildcard syntax in projected [attribute names](#attribute-names) or [aggregate names](#aggregate-names).

The modifier appears as an optional suffix to data names, but before any query parameters in the URL:

- _service_ `/catalog/` _cid_ `/entity/` _path_ `@sort(` _sort key_ `,` ... `)`
  - Each _sort key_ MUST be a column name in the denoted entities since no column renaming is supported in `entity` resources.
  - The sort modifies the order of the entity records in the external representation.
- _service_ `/catalog/` _cid_ `/attribute/` _path_ `/` _projection_ `,` ... `@sort(` _sort key_ `,` ... `)`
  - Each _sort key_ MUST refer to a column in the external representation, i.e. after any renaming has been applied.
  - The sort modifies the order of the entity records in the external representation.
- _service_ `/catalog/` _cid_ `/attributegroup/` _path_ `/` _group key_ `,` ... `;` _projection_ `,` ... `@sort(` _sort key_ `,` ... `)`
  - Each _sort key_ MUST refer to a column in the external representation, i.e. after any renaming has been applied.
  - The sort modifies the order of the group records in the external representation, i.e. groups are sorted after aggregation has occurred. Sorting by a _projection_ value means sorting by a computed aggregate or an arbitrarily chosen example value when projecting bare columns.

The sort modifier is only meaningful on retrieval requests using the `GET` method described in [Data Operations](#data-operations).

## Limit Query Parameter

An optional `limit` query parameter can truncate the length of set-based resource representations denoted by `entity`, `attribute`, and `attributegroup` resource names:

- _service_ `/catalog/` _cid_ `/entity/` _path_ `?limit=` _n_
- _service_ `/catalog/` _cid_ `/entity/` _path_ `@sort(` _sort key_ `,` ... `)` `?limit=` _n_
- _service_ `/catalog/` _cid_ `/attribute/` _path_ `/` _projection_ `,` ... `?limit=` _n_
- _service_ `/catalog/` _cid_ `/attribute/` _path_ `/` _projection_ `,` ... `@sort(` _sort key_ `,` ... `)` `?limit=` _n_
- _service_ `/catalog/` _cid_ `/attributegroup/` _path_ `/` _group key_ `,` ... `;` _projection_ `,` ... `?limit=` _n_
- _service_ `/catalog/` _cid_ `/attributegroup/` _path_ `/` _group key_ `,` ... `;` _projection_ `,` ... `@sort(` _sort key_ `,` ... `)` `?limit=` _n_

If the set denoted by the resource name (without the limit modifier) has _k_ elements, the denoted limited subset will have _n_ members if _n_ < _k_ and will otherwise have all _k_ members. When combined with a sort modifier, the first _n_ members will be returned, otherwise an arbitrary subset will be chosen.

The `limit` query parameter is only meaningful on retrieval requests using the `GET` method described in [Data Operations](#data-operations).

## Data Paging

The [sort modifier](#sort-modifier), [limit parameter](#limit-query-parameter), and [path filters](#path-filters) can be combined to express paged access to set-based data resources:

1. The sort order defines a stable sequence of set elements.
1. The path filter selects set elements following the last-visited element.
1. The limit parameter defines the number of set elements in the page.

This allows sequential paging or scrolling of large result sets. Because ERMrest supports concurrent retrieval and modification of data resources by multiple clients, it is not sensible to randomly access set elements by stream offset (whether by element or page count) because you might skip or repeat elements if preceding elements have been inserted or removed from the sequence in between page requests. With element-based page keying, a concurrent insertion may appear in a scrolled set, and a concurrent deletion may disappear from a scrolled set, but all elements that existed throughout the period of scrolling will be visited once.

### Simple Paging by Entity Key

If the client needs to page through entity records, i.e. `entity` or `attribute` resources, and the client does not need a particular visitation order for the set-based resource elements, it is recommended that paging be performed by the primary key on the entity. Of course, the method described here is also then applicable if the client desired to visit the elements in primary key order.

For example, assuming `table1` has a single key column `keycol`, fetch the first page of results using a sorted and limited data resource:

- _service_ `/catalog/` _cid_ `/entity/` _path_ `@sort(keycol)?limit=` _page size_
- _service_ `/catalog/` _cid_ `/attribute/` _path_ `/` _projection_ `,` ... `@sort(keycol)?limit=` _page size_

Fetch additional pages by sorting and limiting a filtered data resource that only includes elements with key value following the _previous key_ value encountered in the last element of the preceding page:

- _service_ `/catalog/` _cid_ `/entity/` _path_ `/keycol::gt::` _previous key_ `@sort(keycol)?limit=` _page size_
- _service_ `/catalog/` _cid_ `/attribute/` _path_ `/keycol::gt::` _previous key_ `/` _projection_ `,` ... `@sort(keycol)?limit=` _page size_

These examples use the `::gt::` or "greater than" filter operator which means only records where `keycol` > _previous key_ are included in the results. A reverse order scroll can be achieved by using the `::desc::` sort direction and the `::lt::` or "less than" filter operator.

Because sort is applied after projection, such paging is only possible for `attribute` resources if the key column(s) are included in the projection list.

### Paging with Application Sort Order

If the client needs sort elements by a column other than the primary key, a more complex data name is required to simultaneously provide the application sort and a secondary sort that allows page-based segmentation by unique row keys. Two complications are introduced here: the application sort values may be shared by multiple rows and they may also be absent (NULL) for some rows.

For example, assuming `table1` has a single key column `keycol` and the client wants to sort by an application-specific column `appcol`, fetch the first page of results using a sorted and limited data resource:

- _service_ `/catalog/` _cid_ `/entity/` _path_ `@sort(appcol,keycol)?limit=` _page size_
- _service_ `/catalog/` _cid_ `/attribute/` _path_ `/` _projection_ `,` ... `@sort(appcol,keycol)?limit=` _page size_

Fetch additional pages by sorting and limiting a filtered data resource that only includes elements with application value and key value following the _V0_ and _K0_ encountered in the last element of the preceding page:

- _service_ `/catalog/` _cid_ `/entity/` _path_ `/appcol=` _V0_ `&keycol::gt::` _K0_ `;appcol::gt::` _V0_ `;appcol::null::` `@sort(appcol,keycol)?limit=` _page size_
- _service_ `/catalog/` _cid_ `/attribute/` _path_ `/appcol=` _V0_ `&keycol::gt::` _K0_ `;appcol::gt::` _V0_ `;appcol::null::` `/` _projection_ `,` ... `@sort(appcol,keycol)?limit=` _page size_

The subsequent page filters express conditions for three kinds of row which might appear in the next page:

1. A set of rows sharing the same `appcol` value _V0_ and subsequent `keycol` keys
1. A set of rows with subsequent `appcol` values
1. A set of rows with `NULL` `appcol`

these logical cases are rewritten into conjunctive normal form using the available filter syntax of ERMrest.  If the last encountered element has a `NULL` `appcol` value, a different page request is needed:

- _service_ `/catalog/` _cid_ `/entity/` _path_ `/appcol::null::/keycol::gt::` _K0_ `@sort(appcol,keycol)?limit=` _page size_
- _service_ `/catalog/` _cid_ `/attribute/` _path_ `/appcol::null::/keycol::gt::` _K0_`/` _projection_ `,` ... `@sort(appcol,keycol)?limit=` _page size_

this alternate resource name is required because `NULL` is not a value which can be used in `::gt::` or `::lt::` comparison operations.

Because sort is applied after projection, such paging is only possible for `attribute` resources if the application and key sort column(s) are included in the projection list.

