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
1. Catalog: a particular dataset (in one service)
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
1. [Sort Modifer](data/naming.md#sort-modifier)
1. [Limit Query Parameter](data/naming.md#limit-query-parameter)

The filter, sort, and limit syntax together can support [paged data access](data/naming.md#data-paging):
  1. [Simple Paging by Entity Key](data/naming.md#simple-paging-by-entity-key)
  1. [Paging with Application Sort Order](data/naming.md#paging-with-application-sort-order)

### RESTful Operations Overview

The ERMrest interface supports typical HTTP operations to manage these different levels of resource:

1. [Catalog-level operations](rest-catalog.md)
  1. [Catalog Creation](rest-catalog.md#catalog-creation)
  1. [Catalog Retrieval](rest-catalog.md#catalog-retrieval)
  1. [Catalog Deletion](rest-catalog.md#catalog-deletion)
	 1. [ACL Retrieval](rest-catalog.md#access-control-list-retrieval)
	 1. [ACL Entry Creation](rest-catalog.md#access-control-entry-creation)
	 1. [ACL Entry Retrieval](rest-catalog.md#access-control-entry-retrieval)
	 1. [ACL Entry Deletion](rest-catalog.md#access-control-entry-deletion)
1. [Model-level operations](model/rest.md)
  1. [Schemata Retrieval](model/rest.md#schemata-retrieval)
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
