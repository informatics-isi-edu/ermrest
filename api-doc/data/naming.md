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

The _path_ is interpreted slightly differently than in the `attribute` resource space. Rather than denoting a set of entities drawn from the final table instance in _path_, it denotes a set of entity combinations, meaning that there is a potential for a combinatoric number of intermediate records depending on how path entity elements are linked. This denoted set of entity combinations is reduced to a single _aggregate_ tuple. The computed _aggregate_ tuple elements can be in one of several forms:

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

## Attribute Binning

In order to group numerical values into bins, e.g. for histogram presentation, a special *binning* operator is allowed in attribute or group key projections in place of a bare column reference:

- `bin(` _column name_ `;` _nbins_ `;` _minval_ `;` _maxval_ `)`
- `bin(` _in alias_ `:` _column name_ `;` _nbins_ `;` _minval_ `;` _maxval_ `)`

The binning operator determines which bucket the value in _column name_ belongs to, dividing the requested range from _minval_ (inclusive) to _maxval_ (exclusive) into _nbins_ equal-width intervals. The result is always a three-element JSON array `[` _bucket_ `,` _lower_ `,` _upper_ `]` describing the bucket.

- _bucket_: The bin number which the value falls into.
    - `null`: The `null` bin captures all NULL values.
	- 0: The zero bin captures all values below the requested range.
    - 1: The first bin in the requested range.
	- _nbins_: The last bin in the requested range.
	- _bins_ + 1: The final bin captures all values above the requested range.
- _lower_: The lower bound (inclusive) of the bin, or `null`.
- _upper_: The upper bound (exclusive) of the bin, or `null`.

If the client does not wish to consider NULL or out-of-range values, they MAY include an appropriate filter to exclude those rows from the query.

A useful idiom is to use binning as a group-key in the `attributegroup` API with `cnt(*)` to count all matching rows within each bin. The results will be sparse: only bins with a non-zero row count will appear as grouped output rows. The sort modifier MAY be applied to the binning group key.

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

as in the path root, _table name_ may be explicitly schema qualified or left unqualified if it is unambiguous within the catalog. In order for this basic table link element to be valid, there must be at least one foreign-key relationship linking the entity set denoted by _parent path_ and the table denoted by _table name_. The links may point in either direction, i.e. the _parent path_ entity set may contain foreign keys which reference _table name_ or _table name_ may contain foreign keys which reference the _parent path_ entities.

When there are multiple possible linkages to choose from, the link is formed using the disjunction of all applicable link conditions.

#### Linkage by Foreign-Key Endpoint

A more precise entity link element can choose one link condition by identifying an endpoint of the linkage as a set of columns:

- _parent path_ `/(` _column name_ `,` ... `)`
- _parent path_ `/(` _table name_ `:` _column name_ `,` ... `)`
- _parent path_ `/(` _schema name_ `:` _table name_ `:` _column name_ `,` ... `)`

This set of columns MUST comprise either a primary key or a foreign key which unambiguously identifies a single possible linkage between the _parent path_ and a single possible linked entity table. As a convenience, the _schema name_ and _table name_ need not be repeated for additional _column name_ elements in the list after the first one; each unqualified _column name_ will be resolved against the same table as the first _column name_ in the sequence.

The resolution procedure for these column sets is as follows:

1. First column resolution:
  1. Each bare _column name_ MUST be a column of the entity set denoted by _parent path_;
  1. Each qualified name pair _table name_ `:` _column name_ MUST be a column in a table instance within _parent path_ if _table name_ is bound as an alias in _parent path_ (see following sub-section on table instance aliases);
  1. Each qualified name pair _table name_ `:` _column name_ MUST be a column in a table known unambiguously by _table name_ if _table name_ is not bound as an alias in _parent path_;
  1. Each qualified name triple _schema name_ `:` _table name_ `:` _column name_ MUST be a column within a table in the catalog.
1. Endpoint resolution:
  1. All columns in the column set MUST resolve to the same table in the catalog or the same table instance in the _parent path_;
  1. When a sequence of more than one _column name_ is presented, the second and subsequent column names MAY be unqualified and are resolved first to the table associated with the first (possibly qualified) _column name_ in the sequence.
  1. The set of columns MUST comprise either a foreign key or a key in their containing table but not both.
1. Link resolution:
  1. If the endpoint is a key or foreign key in a table in the catalog, that endpoint MUST unambiguously participate in exactly one link between that table and the entity set denoted by _parent path_;
  1. If the endpoint is a key or foreign key of a table instance in _parent path_ (whether referenced by alias-qualified or unqualified column names), that endpoint MUST unambiguously participate in exactly one link between that table instance and exactly one table in the catalog.
  
The path extended with an entity link element denotes the entities of a new table drawn from the catalog and joined to the existing entities in _parent path_, with the default entity context of the extended path being the newly joined (i.e. right-most) table instance.

#### Linkage by Explicit Column Mapping

When one endpoint is not sufficient to unambiguously select path linkage, a fully explicit join condition can be specified as a sequence of left-hand columns which are equated to a corresponding sequence of right-hand columns:

- _parent path_ `/(` _left column name_ `,` ... `)=(` _right table name_ `:` _right column name_ `,` ... `)`
- _parent path_ `/(` _left column name_ `,` ... `)=(` _right schema name_ `:` _right table name_ `:` _right column name_ `,` ... `)`

This notation requires that the _left hand column_ list resolve from _parent path_ and the _right hand column_ list resolve from a table found in the model. This notation resolves the first and subsequent columns of each list as per the preceding column resolution rule. However, it relaxes the other endpoint and link resolution rules. Because it fully expresses an unambiguous join condition, it does not require a corresponding foreign key reference link to be found in the catalog model.  For a hypothetical join condition:

- _parent path_ `/(L1,L2,L3)=(T:R1,R2,R3)`

The indicated join condition corresponds to the SQL `L1 = T.R1 AND L2 = T.R2 AND L3 = T.R3`. Each positional _left column_ and _right column_ MUST have compatible types in order for their values to be tested for equality.

#### Outer-Join Linkage by Column Mapping

With the preceding notation, an optional join type is also allowed as a prefix to the column mapping notation:

- _parent path_ `/left(` _left columns_ ... `)=(` _right columns_ ... `)`
- _parent path_ `/right(` _left columns_ ... `)=(` _right columns_ ... `)`
- _parent path_ `/full(` _left columns_ ... `)=(` _right columns_ ... `)`

These three keywords `left`, `right`, and `full` denote a "left outer join", "right outer join", or "full outer join", respectively. When no such keyword is present, the default join type is an "inner join". Presently, the outer-join modes are only available with fully explicit column mapping notation.

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

where the optional `::desc::` direction indicator can apply a descending sort to that sort key to override the default ascending sort order. ERMrest **always sorts NULL values last** while sorting non-NULL values in ascending or descending order. This differs from the default behavior of the SQL language.

The list of sort keys goes left-to-right from primary to secondary etc.  The individual _output column_ names are user-supplied values and therefore must be URL-escaped if they contain any special characters, including the `:` character in implicitly named output columns introduced using the _alias_ `:` `*` wildcard syntax in projected [attribute names](#attribute-names) or [aggregate names](#aggregate-names).

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

## Paging Modifiers

Optional paging modifiers can designate results that come _before_ or _after_ a designated page key in a sorted sequence. A page key is a vector of values taken from a row that falls outside the page, with one component per field in the sort modifier.

The modifier MUST be accompanied by a sort modifier to define the ordering of rows in the result set as well as the ordering of fields of the page key vector. The paging modifiers support a special symbol `::null::` to represent a NULL column value in a page key. For determinism, page keys SHOULD include a non-null, unique key as the least significant key.

Supported combinations:

| `@after(...)` | `@before(...)` | `?limit`    | Result set |
|---------------|----------------|-------------|------------|
| _K1_          | absent         | absent      | All records *after* _K1_ |
| _K1_          | absent         | _N_         | First records *after* _K1_ limited by page size |
| _K1_          | _K2_           | _N_         | First records *after* _K1_ limited by page size or _K2_ whichever is smaller |
| _K1_          | _K2_           | absent      | All records *between* _K1_ and _K2_ |
| absent        | _K2_           | _N_         | Last records *before* _K2_ limited by page size |

### Before Modifier

The `@before` modifier designates a result set of rows immediately antecedent to the encoded page key, unless combined with the `@after` modifier:

- `@sort(` _output column_ ...`)@before(` `,` ... `)` (i.e. empty string)
- `@sort(` _output column_ ...`)@before(` _value_ `,` ... `)` (i.e. literal string)
- `@sort(` _output column_ ...`)@before(` `::null::` `,` ... `)` (i.e. NULL)

For each comma-separated output column named in the sort modifier, the corresponding comma-separated value represents a component in the page key vector. The denoted result MUST only include rows which come _immediately before_ the page key according to the sorted sequence semantics (including optional ascending/descending direction and NULLS last). This means that at the time of evaluation, no rows exist between the returned set and the row identified by the page key vector.

The `@before` modifier MUST be combined with the `@after` modifier and/or the `?limit=N` query parameter.

### After Modifier

The `@after` modifier designates a result set of rows immediately subsequent to the encoded page key:

- `@sort(` _output column_ ...`)@after(` `,` ... `)` (i.e. empty string)
- `@sort(` _output column_ ...`)@after(` _value_ `,` ... `)` (i.e. literal string)
- `@sort(` _output column_ ...`)@after(` `::null::` `,` ... `)` (i.e. NULL)

For each comma-separated output column named in the sort modifier, the corresponding comma-separated value represents a component in the page key vector. The denoted result MUST only include rows which come _immediately after_ the page key according to the sorted sequence semantics (including optional ascending/descending direction and NULLS last). This means that at the time of evaluation, no rows exist between the returned set and the row identified by the page key vector.

The `@after` modifier MAY be combined with the `@before` modifier and/or the `?limit=N` query parameter.

## Accept Query Parameter

An optional `accept` query parameter can override the `Accept` HTTP header and content-negotiation in data access:

- _service_ `/catalog/` _cid_ `/entity/` _path_ ... `?accept=` _t_
- _service_ `/catalog/` _cid_ `/attribute/` _path_ `/` _projection_  ... `?accept=` _t_
- _service_ `/catalog/` _cid_ `/attributegroup/` _path_ `/` _group key_  `;` _projection_  ... `?accept=` _t_
- _service_ `/catalog/` _cid_ `/aggregate/` _path_ `/` _projection_ ... `?accept=` _t_

If the specified MIME content-type _t_ is one of those supported by the data API, it is selected in preference to normal content-negotiation rules. Otherwise, content-negotiation proceeds as usual. Two short-hand values are recognized:

- `accept=csv` is interpreted as `accept=text%2Fcsv`
- `accept=json` is interpreted as `accept=application%2Fjson`

Note that the content-type _t_ MUST be URL-escaped to protect the `/` character unless using the short-hands above.

## Download Query Parameter

An optional `download` query parameter can activate a `Content-Disposition: attachment` response header for GET operations on data resources.

- _service_ `/catalog/` _cid_ `/entity/` _path_ ... `?download=` _bn_
- _service_ `/catalog/` _cid_ `/attribute/` _path_ `/` _projection_  ... `?download=` _bn_
- _service_ `/catalog/` _cid_ `/attributegroup/` _path_ `/` _group key_  `;` _projection_  ... `?download=` _bn_
- _service_ `/catalog/` _cid_ `/aggregate/` _path_ `/` _projection_ ... `?download=` _bn_

The specified file base-name _bn_ MUST be non-empty and SHOULD NOT include a file-extension suffix to indicate the download file type. The _bn_, when URL-decoded, MUST be a valid UTF-8 string. The service SHOULD append an appropriate suffix based on the negotiated response content type, e.g. `.json' or `.csv`.

As an example:

    GET /ermrest/catalog/1/entity/MyTable?download=My%20File

will produce a response like:

    200 OK
	Content-Type: application/json
	Content-Length: 3
	Content-Disposition: attachment; download*=UTF-8''My%20File.json
	
	[]

which the browser will interpret to suggest a local filename such as `My File.json`.

## Defaults Query Parameter

An optional `defaults` query parameter can be used with the `POST` operation on the `entity` API:

- _service_ `/catalog/` _cid_ `/entity/` _schema name_ `:` _table name_ `?defaults=` _column name_ `,` ...

A list of one or more _column name_ indicates columns of the target table which should be populated using server-assigned defaults values, ignoring any values provided by the client. See the [Entity Creation with Defaults](rest.md#entity-creation-with-defaults) operation documentation for more explanation.

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

The [sort modifier](#sort-modifier), [limit parameter](#limit-query-parameter), and [paging modifers](#paging-modifiers) can be combined to express paged access to set-based data resources:

1. The sort order defines a stable sequence of set elements.
1. The paging modifiers select set elements following (or preceding) the last-visited element.
1. The limit parameter defines the number of set elements in the retrieved page.

This allows sequential paging or scrolling of large result sets with reversing/rewind to earlier pages. Because ERMrest supports concurrent retrieval and modification of data resources by multiple clients, it is not sensible to randomly access set elements by stream position offsets (whether by element or page count) because you might skip or repeat elements if preceding elements have been inserted or removed from the sequence in between page requests. 

A client can choose an arbitrary application-oriented sort order with paging. However, the client SHOULD include row-level unique key material in the sort and page key to avoid hazards of missing rows that have identical sorting rank due to non-unique page keys. This can be achieved by appending unique key columns to the application sort as the lowest precedence sort criteria, i.e. sort first by an interesting but non-unique property and then finally break ties by a unique serial ID or similar property.

1. Fetch first page:
  - _service_ `/catalog/` _cid_ `/entity/` _path_ `@sort(` _sort key_ `,` ... `)` `?limit=` _n_
1. Fetch subsequent page by encoding a page key projected from the **last** row of the preceding page:
  - _service_ `/catalog/` _cid_ `/entity/` _path_ `@sort(` _sort key_ `,` ... `)` `@after(` _limit value_ `,` ...`)` `?limit=` _n_
1. Fetch antecedent page by encoding a page key projected from the **first** row of the subsequent page:
  - _service_ `/catalog/` _cid_ `/entity/` _path_ `@sort(` _sort key_ `,` ... `)` `@before(` _limit value_ `,` ...`)` `?limit=` _n_

Realize that a sequence of forward and backward page requests through a dataset might not land on the same page boundaries on both visits!

- Rows might be inserted during a traversal. An inserted row MAY appear in the traversal or MAY be skipped depending on where it falls in the sorted sequence.
- Rows might be deleted during a traversal. A deleted row MAY appear in the traversal or MAY be skipped depending on where it falls in the sorted sequence.
- Rows might be mutated such that they change positions in the sorted sequence during a traversal. A mutated table row contains one tuple of data before the mutation and another tuple of data after. A single traversal concurrent with that mutation MAY encounter zero, one, or two copies of the row depending on where they fall in the sorted sequence.
