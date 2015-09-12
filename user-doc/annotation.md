# Model Annotation

This document defines a set of annotations we suggest may be useful in
combination with ERMrest. We define a set of _annotation keys_, any
associated JSON _annotation values_, and their semantics. Communities
may use these conventions to modify their interpretation of ERMrest
catalog content.

These annotations do not affect the behavior of the ERMrest service
itself but merely inform clients about intended use beyond that
captured in the entity-relationship model. Further, as described in
the [REST API docs](../api-doc/index.md), the annotation system is
openly extensible so communities MAY use other annotation keys not
described here; in those cases, the community SHOULD publish similar
documentation on their use and interpretation.

## Notation and Usage

Each annotation key is defined in a section of this document and shown
as a literal string.  We prepend a date in each key name and promise
not to modify the semantics of an existing annotation key, once
published to GitHub. We may publish typographical or other small
textual clarifications, but if we need to change the proposed
semantics we will define a new key with a different date and/or key
text. We will follow the date stamp conventions from
[RFC 4151](http://www.faqs.org/rfcs/rfc4151.html) which allow for
abbreviated ISO dates such as `2015`, `2015-01`, and `2015-01-01`.

### Example to Set Annotation

This example sets the
[2015 Default](#2015-default) annotation:

    PUT /ermrest/catalog/1/schema/MainContent/annotation/tag%3Amisd.isi.edu%2C2015%3Aermrest%2Fdefault HTTP/1.1
    Host: www.example.com
    Content-Type: application/json

    null

TBD changes to propose for ERMrest:

1. Allow non-escaped characters in the annotation key since it is the final field of the URL and does not have a parsing ambiguity?
2. Allow an empty (0 byte) request body to represent the same thing as JSON `null`?

## Annotations

Some annotations are supported on multiple types of model element, so
here is a quick matrix to locate them.

| Annotation | Schema | Table | Column | Key | Foreign Key Ref | Summary |
|------------|--------|-------|--------|-----|-----------------|---------|
| [2015 Binary Relationship](#2015-binary-relationship) | - | X | - | - | X | Entity relationships |
| [2015 Default](#2015-default) | X | X | - | - | - | Default scope |
| [2015 Hidden](#2015-hidden) | X | X | X | - | X | Hide model element |
| [2015 URL](#2015-url) | - | - | X | - | - | Column data as URLs |
| [2015 Vocabulary](#2015-vocabulary) | - | X | - | - | - | Table as a vocabulary list |

For brevity, the annotation keys are listed above by their section
name within this documentation. The actual key URI follows the form
`tag:misd.isi.edu,` _date_ `:` _key_ where the _key_ part is
lower-cased with hyphens replacing whitespace. For example, the first
`2015 Default` annotation key URI is actually
`tag:misd.isi.edu,2015:default`.

### 2015 Binary Relationship

`tag:misd.isi.edu,2015:binary-relationship`

This key is allowed on any number of tables or foreign key references
(FKRs). When applied to FKRs, the annotation refines the
interpretation of the FKR relationship. When applied to tables, the
annotation indicates that the table primarily encodes associations
between other entities and further characterizes that relationship.

Supported JSON payload patterns:

- `null` or `{}`: Default heuristics apply.
- `{`... `"referring":` `[` _fkr_ `]` ...`}`: The list of columns _fkr_ forms a foreign key reference to the quasi-referring entity in this association table.
- `{`... `"referred":` `[` _fkr_ `]` ...`}`: The list of columns _fkr_ forms a foreign key reference to the quasi-referred in this association table.
- `{`... `"container":` _container_ ...`}`: The _container_ entity is considered to contain its counterparts in the relationship.
- `{`... `"referring_name":` _name_ ...`}`: The relationship has a preferred _name_ from the perspective of the referring entity.
- `{`... `"referred_name":` _name_ ...`}`: The relationship has a preferred _name_ from the perspective of the referred entity.
- `{`... `"name":` _name_ ... `}`: The relationship has a preferred _name_ from an outsider perspective.

#### Directionality

A foreign key reference annotated as a binary relationship is
inherently directed and and assigns roles of _referring_ to the table
containing the foreign key reference and _referred_ to the table
containing the key which is being referenced. For consistency, when
annotating an association table, the `referring` and `referred`
annotation fields SHOULD designate foreign keys through which these
same relationship roles will be assigned to the associated entity
tables. When such designation is present, the assocation is considered
_directed_.

#### Containment

A containment relationship implies a nested, hierarchical
interpretation of related entities. The container "contains" the
contained entities, i.e. a parent document contains child documents in
a typical nested tree structure. The containment property of a binary
relationship indicates such roles.

#### Heuristics

To find the name of a binary relationship, the first matching rule wins:

1. The `name` field with a string value declares the relationship name.
2. For association table relationships, the table name declares the relationship name.
3. For single-column FKR relationships, the FKR column name declares the relationship name.

To find the referring name of a binary relationship, the first matching rule wins:

1. The `referring_name` field with a string value declares the referring name.
2. The `referring_name` field with `false` value declares an anonymous or hidden referring relationship.
3. For directed associations, the name of the referred table is the referring name.
4. Otherwise, the relationship name is used as the referring name.

To find the referred name of a binary relationship, the first matching rule wins:

1. The `referred_name` field with a string value declares the referred name.
2. The `referred_name` field with `false` value declares an anonymous or hidden referred relationship.
3. For directed associations, the name of the referring table is the referred name.
4. For FKR relationships, the name of the referring table is the referred name.
5. ???

To find containment, the first matching rule wins:

1. The `container` field with value `"referred"` establishes the referred entity as the container.
2. The `container` field with value `"referring"` establishes the referring entity as the container.
3. The `container` field with value `"either"` suggests treating either entity as the container when it is central to a presentation, so the other related entities are exposed as nested content. In this mode, a cyclic presentation may develop if navigation from container to contained is allowed.
4. Otherwise, the relationship is not containment but some other form of relationship to be determined by other means.

### 2015 Default

`tag:misd.isi.edu,2015:default`

This key is allowed on at most one of each of the following model
element types:

- Schema
- Table

This annotation indicates that the annotated schema or table should be
selected by default in a model-driven user interface where
presentation is scoped by schema or table, respectively. This default
selection only applies when the user has not had an opportunity or has
not taken the opportunity to choose a scope explicitly and the
user interface requires a scope selection in order to function.

### 2015 Hidden

`tag:misd.isi.edu,2015:hidden`

This key is allowed on any number of the following model elements:

- Schema
- Table
- Column
- Foreign Key Reference

This annotation indicates that the annotated model element should be
hidden from typical model-driven user interfaces, with the
presentation behaving as if the model element were not present.

### 2015 URL

`tag:misd.isi.edu,2015:url`

This key is allowed on any number of columns in the model with a
textual value type. This annotation indicates that the annotated
column contains values that should be interpreted as retrievable
URLs.

Supported JSON payload patterns:

- `null` or `{}`: Nothing else is known about the URLs.
- `{`... `"pattern":` _pattern_ ...`}`: The actual URL is obtained by expanding the _pattern_ by substituting the column value for the substitution marker `{value}` in _pattern_. For example, a pattern `http://www.ncbi.nlm.nih.gov/pubmed/{value}` would replace the `{value}` marker with PubMed identifiers stored in the column.
- `{`... `"base-url":` _URL0_ ...`}`: Each relative URL found in this column SHOULD be interpreted as relative to the _URL0_ base URL indicated.
- `{`... `"entity": true` ...`}`: Each URL locates a representation of the table row.
- `{`... `"thumbnail": true` ...`}`: Each URL locates an image suitable as a brief summary in a user interface.
- `{`... `"content-type":` _MIME type_ ... `}`: Each URL locates a representation which SHOULD have the given _MIME type_. This sets a static MIME type for the whole table.
- `{`... `"content-type-column":` _MIME column_ ... `}`: Each URL locates a representation which SHOULD have the MIME type stored in the corresponding _MIME column_ of the same table. This allows for variable MIME types on a row-by-row basis in the table.

These optional descriptive fields are mostly additive in their semantics.

1. Any `pattern` assertion is interpreted first, resulting in a URL that is then interpreted according the remaining rules, i.e. the result of the pattern MAY be a relative URL further modified by the `base-url` assertion.
2. In the absence `base-url`, the proper interpretation of relative URLs SHOULD be determined by other means.
3. In the absence of `entity`, the relationship of the located representation to the table row SHOULD be determined by other means.
4. A `thumbnail` assertion implies that the MIME type of the located representations SHOULD be an image type, but does not specify which image type specifically.
5. A `content-type` assertion indicates a static MIME type for the whole column, while the `content-type-column` assertion indicates a source of row-by-row MIME types. The presence of both indicates that the row-by-row source SHOULD always contain the same static value.
6. A retrieved representation that does not satisfy the `thumbnail`, `content-type`, or `content-type-column` expectations designated by the annotation SHOULD be handled as an erroneous condition.

### 2015 Vocabulary

`tag:misd.isi.edu,2015:vocabulary`

This key is allowed on any number of tables in the model, where the
table contains at least one key comprised of a single textual
column. A vocabulary table is one where each row represents a term or
concept in a controlled vocabulary.

Supported JSON payload patterns:

- `null` or `{}`: Default heuristics apply.
- `{`... `"term":` _column_ ...`}`: The named _column_ stores the preferred textual representation of the term. The referenced column MUST comprise a single-column key for the table.
- `{`... `"id":` _column_ ...`}`: The named _column_ stores the preferred compact identifier for the term, which MAY be textual or numeric. The referenced column MUST comprise a single-column key for the table.
- `{`... `"internal":` [_column_, ...] ...`}`: The one or more named _columns_ store internal identifiers for the term, used for efficient normalized storage in the database but not meaningful to typical users. The referenced columns MUST each comprise a single-column key for the table.
- `{`... `"description":` _column_ ...`}`: The named _column_ stores a longer textual representation of the term or concept. The referenced column SHOULD comprise a single-column key for the table.

#### Heuristics

1. In the absence of an `internal` assertion, assume all keys are potentially meaningful to users.
2. In the absence of a `term` assertion
  - Try to find a single-column key named `term`
  - Try to find a single-column key named `name`
  - Try to find a unambiguous single-column textual key
  - If no term column is found table SHOULD NOT be interpreted as a vocabulary.
3. In the absence of an `id` assertion
  - Try to find a column named `id`
  - Try to find an unambiguous single-column numeric key
  - If no `id` column is found, use the term column as the preferred compact identifier.
4. In the absence of a `description` assertion
  - Try to find a column named `description`
  - If no description column is found, proceed as if there is no description or use some other detailed or composite view of the table rows as a long-form presentation.

In the preceding, an "unambiguous" key means that there is only one
key matching the specified type and column count.

The preferred compact identifier is more often used in dense table
representations, technical search, portable data interchange, or
expert user scenarios, while the preferred textual representation is
often used in prose, long-form presentations, tool tips, or other
scenarios where a user may need more natural language understanding of
the concept.

