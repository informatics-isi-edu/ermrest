# ERMrest API

[ERMrest](http://github.com/informatics-isi-edu/ermrest) (rhymes with "earn rest") is a general relational data storage service for web-based, data-oriented collaboration.  See the [ERMrest overview](../README.md) for a general description and motivation.

This technical document specifies the web service protocol in terms of resources, resource representations, resource naming, and operations.

## URL Conventions

Any ERMrest URL is a valid HTTP URL and contains user-generated content which may need to be escaped. Several reserved characters from RFC 3986 are used as meta-syntax in ERMrest and MUST be escaped if they are meant to be part of a user-generated identifiers or literal data and MUST NOT be escaped if they are meant to indicate the ERMrest meta-syntax:

- The `/` or forward-slash, used as a path separator character
- The `:` or colon, used as a separator and in multi-character tokens
- The `;` or semi-colon, used as a separator
- The `,` or comma, used as a separator
- The `=` or equals sign, used as an operator and as part of multi-character tokens
- The `?` or question-mark, used to separate a resource name from query-parameters
- The `&` or ampersand, used as a separator
- The `(` and `)` parentheses, used for nested grouping
- TODO: more syntax to list here

All other reserved characters should be escaped in user-generated content in URLs, but have no special meaning to ERMrest when appearing in unescaped form.

## Resource and Service Model

At its core, ERMrest is a multi-tenant service that can host multiple datasets, each with its own entity-relationship model.  The dataset, model, and data are further decomposed into web resources to allow collaborative management and interaction with the data store.

### Graph of Web Resources

The ERMrest web service model exposes resources to support management of datasets, the entity-relationship model, and the actual data stored using that model:

1. Service: the entire multi-tenant service end-point
1. [Catalog](model/naming.md#catalog-names): a particular dataset (in one service)
1. [Schema or model resources](model/naming.md)
  1. [Schemata](model/naming.md#schemata-names): entire data model of a dataset (in one catalog)
  1. [Schema](model/naming.md#schema-names): a particular named subset of a dataset (in one catalog)
    1. [Schema comment](model/naming.md#schema-comments): human-readable documentation for a schema
    1. [Schema annotation](model/naming.md#schema-annotations): machine-readable documentation for a schema
    1. [Table definition](model/naming.md#table-names): a particular named set of data tuples (in one schema)
      1. [Table comment](model/naming.md#table-comments): human-readable documentation for a table
      1. [Table annotation](model/naming.md#table-annotations): machine-readable documentation for a table
      1. [Column definition](model/naming.md#column-names): a particular named field of data tuples (in one table)
        1. [Column comment](model/naming.md#column-comments): human-readable documentation for a column
        1. [Column annotation](model/naming.md#column-annotations): machine-readable documentation for a column
      1. [Key definition](model/naming.md#key-names): a composite key constraint (in one table)
        1. [Key comment](model/naming#key-comments): human-readable documentation for a key constraint
        1. [Key annotation](model/naming#key-annotations): machine-readable documentation for a key constraint
      1. [Foreign key definition](model/naming.md#foreign-key-names): a composite foreign key constraint (in one table)
        1. [Foreign key comment](model/naming.md#foreign-key-comments): human-readable documentation for a foreign key constraint
        1. [Foreign key annotation](model/naming.md#foreign-key-annotations): machine-readable documentation for a foreign key constraint
1. [Data resources](data/naming.md)
  1. [Entity](data/naming.md#entity-names): a set of data tuples corresponding to a (possibly filtered) table
  1. [Attribute](data/naming.md#attribute-names): a set of data tuples corresponding to a (possibly filtered) projection of a table
  1. [Attribute group](data/naming.md#attribute-group-names): a set of data tuples corresponding to a (possibly filtered) projection of a table grouped by group keys
  1. [Aggregate](data/naming.md#aggregate-names): a data tuple summarizing a (possibly filtered) projection of a table

Rather than treating data resources as nested sub-resources of the model resources, ERMrest treats them as separate parallel resource spaces often thought of as separate APIs for model and data-level access.  The reality is that these resources have many possible semantic relationships in the form of a more general graph structure, and any attempt to normalize them into a hierarchical structure must emphasize some relationships at the detriment of others.  We group model elements hierarchically to assist in listing and to emphasize their nested lifecycle properties.  We split out data resources because they can have a more complex relationship to multiple model elements simultaneously.

#### Model Annotations

The machine-readable annotation mechanism in ERMrest enables a three-level interpretation of datasets:

1. The tabular data itself, which can be processed by any client capable of understanding tabular data representations.
1. The relational meta-model describing the structure of the tabular data, which can be processed by or adapted for any client capable of introspecting on relational data structures.
1. Semantic or presentation guidance, which can be processed by a client capable of augmenting the structural schemata with additional hints.

As an openly extensible, machine-readable interface, the annotations are keyed by globally unique identifiers (URIs) and contain arbitrary document content which can be understood according to rules associated with that key URI.  A client SHOULD ignore annotations stored using a key that the client does not understand.  A client MAY ignore all annotations and simply work with the underlying relational data based on its inherent structure with or without any additional contextual knowledge to guide its interpretation.

### Data Resource Naming Language

The [data resources](data/naming.md) make use of a model-driven language for denoting sub-parts of an entity-relationship modeled dataset. The language has several main syntactic components:

1. [Data Paths](data/naming.md#data-paths)
  1. [Path Root](data/naming.md#path-root)
  1. [Path Filters](data/naming.md#path-filters)
  1. [Entity Links](data/naming.md#entity-links)
    1. [Linkage by Foriegn-Key Endpoint](data/naming.md#linkage-by-foreign-key-endpoint)
    1. [Linkage by Explicit Column Mapping](data/naming.md#linkage-by-explicit-column-mapping)
    1. [Outer-Join Linkage by Column Mapping](data/naming.md#outer-join-linkage-by-column-mapping)
  1. [Table Instance Alias](data/naming.md#table-instance-alias)
  1. [Path Context Reset](data/naming.md#path-context-reset)
1. [Filter Language](data/naming.md#filter-language)
  1. [Unary Filter Predicate](data/naming.md#unary-filter-predicate)
  1. [Binary Filter Predicate](data/naming.md#binary-filter-predicate)
  1. [Negated Filter](data/naming.md#negated-filter)
  1. [Parenthetic Filter](data/naming.md#parenthetic-filter)
  1. [Conjunctive Filter](data/naming.md#conjunctive-filter)
  1. [Disjunctive Filter](data/naming.md#disjunctive-filter)
  1. [Conjunctive Normal Form](data/naming.md#conjunctive-normal-form)
  1. [Disjunctive Normal Form](data/naming.md#disjunctive-normal-form)
1. Data Projection
  1. [Attribute Projection](data/naming.md#attribute-names)
  1. [Aggregate Projection](data/naming.md#aggregate-names)
  1. [Grouped Attribute Projection](data/naming.md#attribute-group-names)
  1. [Attribute Binning](data/naming.md#attribute-binning) i.e. for histograms
1. [Sort Modifer](data/naming.md#sort-modifier)
1. [Paging Modifiers](data/naming.md#paging-modifiers)
  1. [Before Modifier](data/naming.md#before-modifier)
  1. [After Modifier](data/naming.md#after-modifier)
1. [Accept Query Parameter](data/naming.md#accept-query-parameter)
1. [Download Query Parameter](data/naming.md#download-query-parameter)
1. [Defaults Query Parameter](data/naming.md#defaults-query-parameter)
1. [Limit Query Parameter](data/naming.md#limit-query-parameter)

The sort, paging, and limit syntax together can support [paged data access](data/naming.md#data-paging):
  1. [Simple Paging by Entity Key](data/naming.md#simple-paging-by-entity-key)
  1. [Paging with Application Sort Order](data/naming.md#paging-with-application-sort-order)

### RESTful Operations Overview

The ERMrest interface supports typical HTTP operations to manage these different levels of resource:

1. [Catalog-level operations](rest-catalog.md)
  1. [Catalog Creation](rest-catalog.md#catalog-creation)
  1. [Catalog Retrieval](rest-catalog.md#catalog-retrieval)
  1. [Catalog Deletion](rest-catalog.md#catalog-deletion)
	 1. [ACL Retrieval](rest-catalog.md#access-control-list-retrieval)
1. [Model-level operations](model/rest.md)
  1. [Schemata Retrieval](model/rest.md#schemata-retrieval)
  1. [Bulk Schemata and Table Creation](model/rest.md#bulk-schemata-and-table-creation)
  1. [Schema Creation](model/rest.md#schema-creation)
  1. [Schema Retrieval](model/rest.md#schema-retrieval)
  1. [Schema Deletion](model/rest.md#schema-deletion)
    1. [Table List Retrieval](model/rest.md#table-list-retrieval)
    1. [Table Creation](model/rest.md#table-creation)
    1. [Table Retrieval](model/rest.md#table-retrieval)
    1. [Table Deletion](model/rest.md#table-deletion)
      1. [Column List Retrieval](model/rest.md#column-list-retrieval)
      1. [Column Creation](model/rest.md#column-creation)
      1. [Column Retrieval](model/rest.md#column-retrieval)
      1. [Column Deletion](model/rest.md#column-deletion)
      1. [Key List Retrieval](model/rest.md#key-list-retrieval)
      1. [Key Creation](model/rest.md#key-creation)
      1. [Key Retrieval](model/rest.md#key-retrieval)
      1. [Key Deletion](model/rest.md#key-deletion)
      1. [Foreign Key List Retrieval](model/rest.md#foreign-key-list-retrieval)
      1. [Foreign Key Creation](model/rest.md#foreign-key-creation)
      1. [Foreign Key Retrieval](model/rest.md#foreign-key-retrieval)
      1. [Foreign Key Deletion](model/rest.md#foreign-key-deletion)
  1. [Model Annotations](model/rest.md#model-annotations)
    1. [Annotation List Retrieval](model/rest.md#annotation-list-retrieval)
    1. [Annotation Creation](model/rest.md#annotation-creation)
    1. [Annotation Bulk Update](model/rest.md#annotation-bulk-update)
    1. [Annotation Retrieval](model/rest.md#annotation-retrieval)
    1. [Annotation Deletion](model/rest.md#annotation-deletion)
  1. [Model Comments](model/rest.md#model-comments)
    1. [Comment Creation](model/rest.md#comment-creation)
    1. [Comment Retrieval](model/rest.md#comment-retrieval)
    1. [Comment Deletion](model/rest.md#comment-deletion)
1. [Data operations](data/rest.md)
  1. [Entity Creation](data/rest.md#entity-creation)
    1. [Entity Creation with Defaults](data/rest.md#entity-creation-with-defaults)
  1. [Entity Update](data/rest.md#entity-update)
  1. [Entity Retrieval](data/rest.md#entity-retrieval)
  1. [Entity Delete](data/rest.md#entity-delete)
  1. [Attribute Retrieval](data/rest.md#attribute-retrieval)
  1. [Attribute Delete](data/rest.md#attribute-delete)
  1. [Attribute Group Retrieval](data/rest.md#attribute-group-retrieval)
  1. [Attribute Group Update](data/rest.md#attribute-group-update)
    1. [Attribute Group Update with Renaming](data/rest.md#attribute-group-update-with-renaming)
  1. [Aggregate Retrieval](data/rest.md#aggregate-retrieval)

These operations produce and/or consume representations of the resources. ERMrest defines its own JSON representations for catalog and model elements, and supports common representations of tabular data.

### HTTP Concurrency Control

ERMrest supports opportunistic concurrency control using an entity tag ("ETag") as per the HTTP standards to identify versions of web resources. The ETag is a version identifier that composes with a URL to fully identify a resource version. In other words, ETag strings are meaningless when separated from the resource address.

#### Precondition Processing

1. A response header `ETag` carries an ETag representing the resource version _at the conclusion of request processing_.
  - A `HEAD` response with an ETag identifies the version of the resource currently present in the server.
  - A `GET` response with an ETag identifies the version of the resource being represented in the output.
  - A `PUT`, `POST`, or `DELETE` response with an ETag identifies the version of the server-side resource after it was modified by the request.
2. Request headers `If-Match` and `If-None-Match` carry one or more ETags (or the wildcard `*`) specifying constraints on the resource version _at the start of request processing_.
  - The `If-Match` header requires that the server-side resource match one of the specified ETag values in order to permit processing of the request.
  - The `If-None-Match` header requires that the server-side resource *not* match any of the specified ETag values in order to permit processing of the request.
  - The wildcard `*` in either header trivially matches any server-side resource version.
  - The combination of both headers is a logical conjunction of all constraints, meaning both headers' respective conditions must be met in order to permit processing of the request.
3. HTTP methods conditionalize their behavior and response when precondition headers are present in requests.
  - A `PUT`, `POST`, or `DELETE` operation returns a normal `200 OK` or `201 Created` in the absence of preconditions or if preconditions are met. They return `412 PreconditionFailed` when preconditions are not met; in this case, the operation has no effect on server-side resource state.
  - A `GET` operation returns a normal `200 OK` in the absence of preconditions or if preconditions are met. It returns `304 Not Modified` when preconditions are not met. This alternative status code is required by the HTTP standard due to its idiomatic use for cache-control of `GET` responses; the "not modified" status means the client can reuse a representation when an `If-None-Match` header is used to specify the ETag associated with the representation previously retrieved by that client.

#### Atomic Retrieval of Multiple Resources

An example of concurrency control is to dump a set of data values from several tables with confidence that they are transactionally consistent. ERMrest provides basic atomicity at the HTTP request level, but this is insufficient to guarantee consistency of several different requests. Instead, a client might follow this workflow:

1. Plan the set of resources it needs to retrieve (e.g. a list of ERMrest URLs for schema and/or data resources).
2. Pre-fetch each resource using an unconditional `GET` request and save both the representation and corresponding ETag from the response.
3. Re-probe each resource using a conditional `GET` request with `If-None-Match` header specifying the ETag from the previous response for that URL.
  - A `304 Not Modified` response indicates that the resource is still at the same version on the server.
  - A `200 OK` response indicates that the server-side state has changed, so save both the representation and corresponding ETag from the response.
4. Repeat step (3) until an entire cycle of visits to all resources yielded `304 Not Modified`, indicating that no resource changed state since their states were retrieved.

#### Atomic Change of a Resource

Another example of concurrency control is to change a resource while ensuring that other clients' modifications are not clobbered:

1. Fetch a resource representation and its corresponding ETag.
2. Send a revision of the data an appropriate `PUT`, `POST`, or `DELETE` to the same URL including an `If-Match` header with the previously retrieved ETag.
  - A `200 OK`, `201 Created`, and/or `204 No Content` indicates that the mutation was performed safely.
  - A `412 Precondition Failed` response indicates that someone else modified the resource since you last fetched it, so repeat the process from step (1).

ERMrest always makes an atomic change for one request, but the above workflow protects against concurrent access to the resource while the client is interpreting the first representation it retrieved, planning the mutation, and requesting that the change be applied. When an update hazard is identified by the `412 Precondition Failed` response, the client has avoided making an unsafe change and repeats the entire inspect, plan, execute cycle.

#### Atomic Change of Multiple Resources

The two preceding workflows can be combined in order to determine consistent modification of multiple data or schema resources, with some caveats:

1. Perform [atomic retrieval of multiple resources](#atomic-retrieval-of-multiple-resources) until a consistent set of <URL, representation, ETag> triples are known.
2. Plan a set of update operations for the same URLs.
3. Perform a variant of [atomic change of a resource](#atomic-change-of-a-resource) once for each URL.
  A. Perform the mutation request immediately with an `If-Match` header bearing the ETag obtained in step (1) of this bulk workflow.
  B. Any `200 OK`, `201 Created`, and/or `204 No Content` response indicates that part of the update has completed. Save the update revision ETag associated with this response.
  C. If any `412 Precondition Failed` response is encountered, a concurrent modification has been detected. The client should stop and analyze the situation!

Unfortunately, a concurrent change detected in step (3.C.) above leaves the server in an inconsistent state. The client is aware that they have partially applied updates and they must now formulate a compensation action which depends on domain knowledge and more sophisticated client behaviors.  For example:

- A client might be able to restart the whole workflow, determine the new state of all resources, and reformulate or "re-base" its plan as a set of revised updates.
- If a `HEAD` request to each resource successfully changed in step (3.B.) yield the same revision ETag that was returned in the mutation response, the client may be able to apply reverse operations to undo its changes. Whether practical reverse operations are available depends on the operation and size of affected data.

Alternative ERMrest bulk-change APIs are under consideration to allow truly atomic change by sending a complete multi-resource request and allowing the server to process it under transaction control. Users interested in such features should contact the developers by filing an issue in our GitHub project.

### Set-based Data Resources and Representations

ERMrest presents a composite resource model for data as sets of tuples. Using different resource naming mechanisms, this allows reference to data at different granularities and levels of abstraction:

1. All entities in one table, or a filtered subset of those entities.
1. A projection of attributes for all entities in one table or a filtered subset of those entities, possibly including additional attributes joined from other tables.
1. A projection of attributes for all entities in one table or a filtered subset of those entities, grouped by grouping keys, possibly including additional attributes joined from other tables and possibly including computed aggregates over members of each group.
1. One entity (known by its key value).
1. A projection of one entity.
1. A projection of computed aggregates over all entities in one table or over a filtered subset of those entities.

For simplicity, ERMrest always uses data formats capable of representing a set of tuples, even if the particular named data resource is a degenerate case with set cardinality of one (single tuple) or zero (emtpy set). The currently supported MIME types for tabular data are:

- `application/json`: a JSON array of objects where each object represents one tuple with named fields (the default representation).
- `text/csv`: a comma-separated value table where each row represents one tuple and a header row specifies the field names.
- `application/x-json-stream`: a stream of JSON objects, one per line, where each object represents one tuple with named fields.

Other data formats may be supported in future revisions.

#### Scalar and Array Typed Attributes

ERMrest generically exposes a range of scalar and array-of-scalar attribute types, with names familiar to PostgreSQL users:

- `boolean`: Can be either `True` or `False`.
- `date`: An ISO 8601 date such as `2015-12-31`.
- `timestamptz`: An ISO 8601 timestamp with timezone such as `2016-01-13T16:34:24-0800`.
- `float4` and `float8`: Floating-point numbers in 4-byte (32-bit) or 8-byte (64-bit) precision, respectively.
- `int2`, `int4`, `int8`: Two's complement integers in 2-byte, 4-byte, or 8-byte widths, respectively.
- `serial2`, `serial4`, `serial8`: Corresponding to `int2`, `int4`, and `int8` with an auto-incremented default behavior on insertion.
- `text`: Variable-length text containing Unicode characters, using UTF-8 encoding in all supported MIME types (currently CSV and JSON).
- `jsonb`: JSON text strings parsed and stored in PostgreSQL's binary JSON variant.

The [binary filter predicate](data/naming.md#binary-filter-predicate)
language of ERMrest URIs compare a stored scalar column value (the
left-hand value) to a constant value supplied in the URI filter syntax
(the right-hand value). In general, the core operators apply to all
scalar types except the regular-expression matches which only apply to
`text` column type.

##### Arrays of Scalars

ERMrest supports columns storing arrays of the preceding scalar
types. These arrays are encoded differently depending on the MIME type:

- As native JSON array content in JSON input/output formats, e.g. `{"array_column_name": ["value1", "value2"], "scalar_column_name": "value3"}`
- As PostgreSQL-formatted arrays in CSV input/output formats, e.g. `"{value1,value2,value3}",value3`

The [binary filter predicate](data/naming.md#binary-filter-predicate)
language of ERMrest URIs compare each scalar element in a stored array
column using *existential qualification*. The array elements are used
as left-hand values and individually compared with the constant
right-hand value from the URI filter syntax. The predicate is
considered to match if *any* contained array element individually
matches using the scalar comparison.

A column storing an array of scalars MAY be used as a unique key or foreign key, subject to PostgreSQL native interpretation of array equality. However, it is RECOMMENDED that data modelers consider normalizing their schema to avoid such constructs.

##### Experimental Types

ERMrest makes a best-effort attempt to support additional attribute
types when exposing legacy database schema. These types MAY support
value storage and exchange to varying degrees but support for filter
predicates and other niceties are lacking or we discourage their use
for other reasons:

- `uuid`: Universally Unique Identifiers, e.g. `a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11`.
- `numeric`: Arbitrary-precision decimal numerical data.
- `time` and `timetz`: Time values lacking date information.
- `timestamp`: Timestamps lacking timezone information.
- `json`: JSON text strings.
- various `text` and `character` types with length constraints: No
  length constraints or padding are considered or enforced by ERMrest
  and for the most part these map to variable-length `text` storage
  with additional constraints that MAY be enforced by PostgreSQL.

In a normal ERMrest configuration, these types are not supported when
defining new columns or tables, and only mapped from existing
databases for legacy support.

#### CSV Format

ERMrest supports the `text/csv` MIME type for tabular input or output,
as described in [RFC 4180](https://tools.ietf.org/html/rfc4180). If
deviation between the RFC and ERMrest are found, please report them as
a bug in the ERMrest issue tracker.

Refer to the RFC for full CSV format details, but here are a few
points worth noting:

- Each row (record) is terminated with a carriage-return, linefeed (CRLF) byte pair.
- Fields are separated by the comma (`,`) character. The final field MUST NOT have a trailing comma, as that would be interpreted as one more empty field before the record terminator.
- The first row is a header with column names in each field.
- All records MUST have the same number of fields.
- Fields MAY be surrounded by the double-quotation character (`"`) to allow embedding of field separators, record terminators, or whitespace.
  - Even a newline or CRLF pair may appear in the quoted field.
  - To embed a literal double-quotation character in a quoted field, escape it by preceding with a second copy of the same byte, e.g. `"This "" sentence has one double-quote character in it."`.
- All whitespace between field separators is significant.
  - A quoted record SHOULD NOT be preceded or followed by whitespace, e.g. `...," a b ",...` is preferred to `..., "a b" ,...`. The RFC does not allow the latter form. ERMrest MAY interpret both as equivalent but this behavior SHOULD NOT be relied upon by clients.

##### NULL values

As a further note, ERMrest interprets quoted and unquoted empty fields distinctly:

- `...,,...`: NULL value
- `...,"",...`: empty string

##### Example CSV Content

In this example, we include the literal `<CRLF>` to emphasize the record terminator that would not be visually appreciable otherwise:

    row #,column A,column B,column C,column D<CRLF>
    1,a,b,c,d<CRLF>
	2,A,B,C,D<CRLF>
	3, A, B, C, D<CRLF>
	4, A , B , C , D <CRLF>
	5," A "," B "," C "," D "<CRLF>
	6," ""A"" "," ""B"" "," ""C"" "," ""D"" "<CRLF>
	7,"A<CRLF>
	A","B<CRLF>
	B","C<CRLF>
	C","D<CRLF>
	D"<CRLF>
	8,,,,<CRLF>
	9,"","","",""<CRLF>

The preceding example has nine total rows with a column containing an
explicit row number `1` through `9` and four addition columns named
`column A` through `column D` with the following values encoded in the
CSV records:

1. Four literals `a` through `d`
2. Four literals `A` through `D`
3. Four literals ` A` through ` D`, i.e. alphabetic character preceded by space character.
4. Four literals ` A ` through ` D `, i.e. alphabetic character surrounded by space characters on both sides.
5. Same literals as row (4).
6. Four literals ` "A" ` through ` "D" `, i.e. alphabetic character surrounded by quotes and then surrounded by space characters on both sides.
7. Four literals `A<CRLF>A` through `D<CRLF>D`, i.e. one carriage-return linefeed pair surrounded by alphabetic characters on both sides.
8. Four NULL values.
9. Four literal empty strings.

