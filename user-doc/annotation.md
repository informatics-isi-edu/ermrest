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

| Annotation | Schema | Table | Column | Key | FKR | Summary |
|------------|--------|-------|--------|-----|-----|---------|
| [2015 Binary Relationship](#2015-binary-relationship) | - | - | - | - | - | Retracted. |
| [2015 Default](#2015-default) | X | X | - | - | - | Default scope |
| [2015 Display](#2015-display) | X | X | X | - | - | Display options |
| [2015 Facets](#2015-facets) | - | X | - | - | - | Retracted. |
| [2015 Hidden](#2015-hidden) | X | X | X | - | X | Retracted. |
| [2015 URL](#2015-url) | - | X | X | - | - | Column or table data as URLs |
| [2015 Vocabulary](#2015-vocabulary) | - | X | - | - | - | Table as a vocabulary list |
| [2016 Abstracts Table](#2016-abstracts-table) | - | X | - | _ | _ | Table abstracts another table |
| [2016 Foreign Key](#2016-foreign-key) | - | - | - | - | X | Foreign key augmentation |
| [2016 Generated](#2016-generated) | - | - | X | - | - | Generated column element |
| [2016 Ignore](#2016-ignore) | X | X | - | - | - | Ignore model element |
| [2016 Immutable](#2016-immutable) | - | - | X | - | - | Immutable column element |
| [2016 Record Link](#2016-record-link) | X | X | - | - | - | Intra-Chaise record-level app links |
| [2016 Sequence](#2016-sequence) | - | - | X | - | - | Column as a Gene Sequence |
| [2016 Table Display](#2016-table-display) | X | X | - | - | - | Table-specific display options |
| [2016 Visible Columns](#2016-visible-columns) | - | X | - | - | - | Column visibility and presentation order |
| [2016 visible Foreign Keys](#2016-visible-foreign-keys) | - | X | - | - | - | Foreign key visibility and presentation order |

For brevity, the annotation keys are listed above by their section
name within this documentation. The actual key URI follows the form
`tag:misd.isi.edu,` _date_ `:` _key_ where the _key_ part is
lower-cased with hyphens replacing whitespace. For example, the first
`2015 Default` annotation key URI is actually
`tag:misd.isi.edu,2015:default`.

### ~~2015 Binary Relationship~~

`tag:misd.isi.edu,2015:binary-relationship`

This annotation proposal has been retracted. At time of retraction, no none uses of the annotation exist in the wild.

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

### 2015 Display

`tag:misd.isi.edu,2015:display`

This key is allowed on any number of schemas, tables, and
columns. This annotation indicates display options for the indicated
element and its nested model elements.

Supported JSON payload patterns:

- `{`... `"name":` _name_ ...`}`: The _name_ to use in place of the model element's original name.
- `{`... `"name_style":` `{` `"underline_space"`: _uspace_ `,` `"title_case":` _tcase_ `}` ...`}`: Element name conversion instructions.

Supported JSON _uspace_ patterns:

- `true`: Convert underline characters (`_`) into space characters in model element names.
- `false`: Leave underline characters unmodified (this is also the default if the setting is completely absent).

Supported JSON _tcase_ patterns:

- `true`: Convert element names to "title case" meaning the first character of each word is capitalized and the rest are lower cased regardless of model element name casing. Word separators include white-space, hyphen, and underline characters.
- `false`: Leave character casing unmodified (this is also the default if the setting is completely absent).

#### 2015 Display Settings Hierarchy

- The `"name"` setting applies *only* to the model element which is annotated.
- The `"name_style"` setting applies to the annotated model element and is also the default for any nested element.

This annotation provides an override guidance for Chaise applications using a hierarchical scoping mode:

1. Column-level name
2. Column-level name_style. 
3. Table-level name_style. 
4. Schema-level name_style. 

Note: 
- An explicit setting of `null` will turn *off* inheritence and restore default behavior for that modele element and any of its nested elements.
- The name_style has to be derived separately for each field e.g. one can set `underline_space=true` at the schema-level and doesn't have to set this again.   


### ~~2015 Facets~~

`tag:misd.isi.edu,2015:facets`

This proposal is retracted. At time of retraction, no known uses of this annotation exist in the wild.

#### Examples

There is a direct correspondence between _facetspec_ elements and an
ERMrest API URL fragment encoding the same path information. Consider
the following _facetspec_ examples that could be present in a facets
annotation on the entity type `S`:`E1` in a catalog:

| facet spec. | ERMrest URL fragment |
|-------------|----------------------|
| `{}` | `/entity/S:E1` |
| `{"path": []}` | `/entity/S:E1` |
| `{"fcolumns": ["foo", "bar"]}` | `/attribute/S:E1/foo,bar` |
| `{"table": "E2"}` |`/entity/S:E1/S:E2` |
| `{"schema": "S", "table": "E2"}` |`/entity/S:E1/S:E2` |
| `{"path": [{"schema": "S", "table": "E2"}]}` |`/entity/S:E1/S:E2` |
| `{"path": [{"schema": "S", "table": "E2"}], "fcolumns": ["foo", "bar"]}` |`/attribute/S:E1/S:E2/foo,bar` |
| `{"lcolumns": ["id"]}` | `/entity/S:E1/(id)` |
| `{"path": [{"lcolumns": ["id"]}]}` | `/entity/S:E1/(id)` |
| `{"path": [{"lcolumns": ["id"]}, {"lcolumns": ["id"]}]}` | `/entity/S:E1/(id)/(id)` |
| `{"path": [{"schema": "S", "table": "E2", "lcolumns": ["e1_id"]}, {"lcolumns": ["id"]}]}` | `/entity/S:E1/(S:E2:e1_id)/(id)` |

#### Heuristics

1. Validate each _facetspec_.
  - Validate the _linkspec_ chain to determine source table for facets.
  - Resolve the _fname_ facets as columns in the source table.
  - If *too many* invalid _facetspec_ elements were encountered, consider the whole set invalid?
2. Ignore invalid _facetspec_ elements.
  - Any _sname_:_tname_ that is not present in the model is invalid.
  - Any _lname_ that is not present in the link table is invalid.
  - Any _lname_ sequence that does not form a link's endpoint is invalid.
  - Any ambiguous linkage is invalid (more than one way to reach the named table or using the same named link columns).
3. Present the ordered list of valid _facetspec_ elements as the primary faceting.
  - Heuristics MAY suppress or denormalize a valid _facetspec_.
  - An empty set of valid elements SHOULD be interpreted as if no annotation was present.
4. Offer other reachable facets (found via model-driven interpretation) through "see more" or similar advanced interfaces. The annotation is meant to group or prioritize facets but SHOULD NOT block facet interpretation.

### ~~2015 Hidden~~

`tag:misd.isi.edu,2015:hidden`

This annotation has been _deprecated_ in favor of [2016 Ignore](#2016-ignore).

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

This key is allowed on any number of columns and tables in the
model. This annotation describes how the table or column can be
presented as a URL.

#### Combining multiple annotations

The JSON payload under this annotation MAY contain:

1. A non-empty object which is interpreted as one [presentation instruction](#url-presentation-instructions).
2. A `null` value or empty object `{}` *only* at the column level, which is interpreted as equivalent to `{"url": "{cname}", "presentation": "link"}` where `cname` is the actual name of the column annotated as such.
3. An array, whose elements are each interpreted by the preceding two rules.

Any other payload not matching these rules SHOULD be discarded as invalid.  The overall interpretation of the annotation contents is to gather a sequence of URL presentation instructions to apply to each table row. The overall presentation of the table row SHOULD contain the sequence of meaningful presentations, pruned to remove invalid or NULL-expanding presentations.

If this annotation is applied at the table level, any presentation instructions derived from the table-level annotation appear first in the final sequence. For each column of the table, in natural column order, any presentation instruction derived from this annotation at the column level are appended to the final sequence.

#### URL presentation instructions

Supported JSON payload patterns:

- `{`... `"url":` _pattern_ ...`}`: The actual URL is obtained by expanding the _pattern_ (see [Pattern Expansion](#pattern-expansion)).
- `{`... `"url": [` _pattern_`,`...`]`...`}`: A set of URLs is obtained by expanding the list of _pattern_.
- `{`... `"caption":` _pattern_ ...`}`: The optional caption to go along with the URL where applicable. The actual caption is obtained by expanding the _pattern_ (see below).
- `{`... `"caption": [` _pattern_`,`...`]`...`}`: A set of captions is obtained by expanding the list of _pattern_. The list of captions MUST be the same length as the list of URLs.
- `{`... `"content-type":` _pattern_ ... `}`: The expected MIME type for the resource named by the URL is obtained by expanding the _pattern_.
- `{`... `"content-type":` _pattern_ ... `}`: A set of MIME types is obtained by expanding the list of _pattern_. The list of content types MUST be the same length as the list of URLs.
- `{`... `"presentation":` [`"download"` | `"embed"` | `"link"` | `"thumbnail"`] ...`}`: Indicates the preferred presentation style for the URL or URLs. The presentation value should be one of the options listed.
- `{`... `"entity": true` ...`}`: Each URL locates a representation of the table row.
- `{`... `"height":` _pattern_ ...`}`: The desired height of the presentation, if applicable, is obtained by expanding the _pattern_.
- `{`... `"width":` _pattern_ ...`}`: The desired width of the presentation, if applicable, is obtained by expanding the _pattern_.

These optional descriptive fields are mostly additive in their semantics.

1. The `url` assertion is interpreted first, resulting in a URL (or set of URLs) that is then interpreted according the remaining rules.
2. The `caption` may be used to enhance the presentation of the URL (or set of URLs) where applicable.
3. In the absence of `entity`, the relationship of the located representation to the table row SHOULD be determined by other means.
4. A `thumbnail` assertion within the `presentation` option implies that the MIME type of the located representations SHOULD be an image type, but does not specify which image type specifically.
5. The `content-type` may be used to determine the MIME type of a URL (or set of URLs).
6. A specified `height` and `width` define a desired geometry, otherwise default or dynamic sizing is assumed.
7. A retrieved representation that does not satisfy the `thumbnail`, `content-type`, or `content-type-column` expectations designated by the annotation SHOULD be handled as an erroneous condition.
8. When a single annotation instruction includes an array of `url` patterns, the URL presentation is a composite of those URLs. If the array is empty or the effective array is empty due to null value exceptions in patterns, the enclosing presentation instruction is disabled.

#### Null value exceptions

If any field value in a _pattern_ is NULL in the source data record, the entire _pattern_ evaluates to NULL for this row.

1. For annotation objects containing a scalar `url` _pattern_
  - If the `url` _pattern_ evaluates to NULL, the annotation object does not produce a URL presentation
  - If the `caption` _pattern_ is present and evaluates to NULL, the annotation object does not produce a URL presentation
2. For annotation objects containing an array of `url` _pattern_
  - If the `url` _pattern_ in position _i_ evaluates to NULL, the position _i_ does not produce a URL presentation
  - If the `caption` _pattern_ in position _i_ is present and evaluates to NULL, the position _i_ does not produce a URL presentation
  - If no position produces a URL presentation, the enclosing object does not produce a URL presentation

### 2015 Vocabulary

`tag:misd.isi.edu,2015:vocabulary`

This key is allowed on any number of tables in the model, where the
table contains at least one key comprised of a single textual
column. A vocabulary table is one where each row represents a term or
concept in a controlled vocabulary.

Supported JSON payload patterns:

- `null` or `{}`: Default heuristics apply.
- `{`... `"uri":` _uri_ ...`}`: The _uri_ indicates the global identifier of the controlled vocabulary. The _uri_ MAY be a resolvable URL.
- `{`... `"term":` _column_ ...`}`: The named _column_ stores the preferred textual representation of the term. The referenced column MUST comprise a single-column key for the table.
- `{`... `"id":` _column_ ...`}`: The named _column_ stores the preferred compact identifier for the term, which MAY be textual or numeric. The referenced column MUST comprise a single-column key for the table.
- `{`... `"internal":` [_column_, ...] ...`}`: The one or more named _columns_ store internal identifiers for the term, used for efficient normalized storage in the database but not meaningful to typical users. The referenced columns MUST each comprise a single-column key for the table.
- `{`... `"description":` _column_ ...`}`: The named _column_ stores a longer textual representation of the term or concept. The referenced column SHOULD comprise a single-column key for the table.

#### Heuristics

1. In the absence of an `internal` assertion, assume all keys are potentially meaningful to users.
2. In the absence of a `term` assertion
  - Try to find a single-column key named `term`
  - Try to find a single-column key named `name`
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

### 2016 Sequence

`tag:isrd.isi.edu,2016:sequence`

This key is allowed on any number of columns in the model. It is used to
indicate that the annotated column contains a text value that should be
interpreted as a gene sequence.

Supported JSON payload patterns:

- `null` or `{}`: Default heuristics apply.
- `{`... `"subseq-length":` _number_ ...`}`: The _number_ indicates the intended
  length for a subsequence of the overall gene sequence. When displaying a gene
  sequence, it is common to visually demarcate a long sequence of nucleotides
  into smaller subsequences.
- `{`... `"separator":` _character_ ...`}`: The _character_ to use as the
  separator between subsequence strings.

### 2016 Ignore

`tag:isrd.isi.edu,2016:ignore`

This key is allowed on any number of the following model elements:

- Schema
- Table

This key was previously specified for these model elements but such use is deprecated:

- Column (use [2016 Visible Columns](#2016-visible-columns) instead)
- Foreign Key (use [2016 Visible Foreign Keys](#2016-visible-foreign-keys) instead)

This annotation indicates that the annotated model element should be ignored in typical model-driven user interfaces, with the presentation behaving as if the model element were not present. The JSON payload contextualizes the user interface mode or modes which should ignore the model element.

Supported JSON payload patterns:
- `null` or `true`: Ignore in any presentation context. `null` is equivalent to `tag:misd.isi.edu,2015:hidden` for backward-compatibility.
- `[]` or `false`: Do **not** ignore in any presentation context.
- `[` _context_ `,` ... `]`: Ignore **only** in specific listed contexts drawn from the following list, otherwise including the model element as per default heuristics:
  - `entry`: Avoid prompting of the user for input to whole schemas or whole tables while obtaining user input.
    - `edit`: A sub-context of `entry` that only applies to editing existing resources.
	- `create`: A sub-context of `entry` that only applies to creating new resources.
  - `filter`: Avoid offering filtering options on whole schemas or whole tables.
  - `compact`: Avoid presenting data related to whole schemas or whole tables when presenting data in compact, tabular formats.
  - `detailed`: Avoid presenting data related to whole schemas or whole tables when presenting data in detailed, entity-level formats.

This annotation provides an override guidance for Chaise applications
using a hierarchical scoping mode:

1. Hard-coded default behavior in Chaise codebase.
2. Server-level configuration in `chaise-config.js` on web server overrides hard-coded default.
3. Schema-level annotation overrides server-level or codebase behaviors.
4. Table-level annotation overrides schema-level, server-level, or codebase behaviors.
5. Annotations on the column or foreign key reference levels override table-level, schema-level, server-level, or codebase behaviors.


### 2016 Record Link

`tag:isrd.isi.edu,2016:recordlink`

This key is allowed on any number of schemas or tables in the
model. It is used to indicate which record-level application in the
Chaise suite should be linked from rows in a search or other row-set
presentation.

Supported JSON payload patterns:

- `{ "mode":` _mode_ `, "resource":` _relpath_ `}`: Link to _relpath_ app resource, forming a URL using linking _mode_.
  - The `mode` _mode_ SHOULD be the following fixed constant (unless additional modes are defined in a future revision):
    - `"tag:isrd.isi.edu,2016:recordlink/fragmentfilter"`: form an application link as, e.g., `/chaise/` _relpath_ `?` _catalog_ `/` _schema_ `:` _table_ `/` _filter_ where _filter_ is a simple ERMrest predicate such as `columnname:eq:value`.
  - The `resource` _relpath_ SHOULD be a relative path to one of the supported Chaise record-level applications:
    - `"record/"`
    - `"viewer/"`

This annotation provides an override guidance for Chaise applications
using a hierarchical scoping mode:

1. Hard-coded default behavior in Chaise codebase.
2. Server-level configuration in `chaise-config.js` on web server overrides hard-coded default.
3. Schema-level annotation overrides server-level or codebase behaviors.
4. Table-level annotation overrides schema-level, server-level, or codebase behaviors.

### 2016 Immutable

`tag:isrd.isi.edu,2016:immutable`

This key indicates that the values for a given column may not be mutated
(changed) once set. This key is allowed on any number of columns. There is no
content for this key.

### 2016 Generated

`tag:isrd.isi.edu,2016:generated`

This key indicates that the values for a given column will be generated by
the system. This key is allowed on any number of columns. There is no content
for this key.

### Pattern Expansion

When deriving a field value from a _pattern_, the _pattern_ MAY contain markers for substring replacements of the form `{column name}` where `column name` MUST reference a column in the table. Any particular column name MAY be referenced and expanded zero or more times in the same _pattern_.

For example, a _table_ may have a [`tag:misd.isi.edu,2015:url`](#2015-url) annotation containing the following payload:

```
{
    "pattern": "https://www.example.org/collections/{collection}/media/{object}",
    "presentation": "embed"
}
```

A web user agent that consumes this annotation and the related table data would likely embed the following `<iframe>` tag for each entity:

```
<iframe src="https://www.example.org/collections/123/media/XYZ"></iframe>
```

### 2016 Visible Columns

`tag:isrd.isi.edu,2016:visible-columns`

This key indicates that the presentation order and visibility for
columns in a table, overriding the defined table structure.

Supported JSON payload pattern:

- `{` ... _context_ `:` _columnlist_ `,` ... `}`: A separate _columnlist_ can be specified for any number of _context_ names.
- `{` ... _context1_ `:` _context2_ `,` ... `}`: Configure _context1_ to use the same _columnlist_ configured for _context2_.

For presentation contexts which are not listed in the annotation, or when the annotation is entirely absent, all available columns SHOULD be presented in their defined order unless the application has guidance from other sources.

Supported _context_ names:

- `"entry"`: Any data-entry presentation context, i.e. when prompting the user for input column values.
  - `"edit"`: A sub-context of `entry` that only applies to editing existing resources.
  - `"create"`: A sub-context of `entry` that only applies to creating new resources.
- `"record"`: Any detailed record-level presentation context.
- `"filter"`: Any data-filtering control context, i.e. when prompting the user for column constraints or facets.
- `"compact"`: Any compact, tabular presentation of data from multiple entities.
- `"*"`: A default to apply for any context not matched by a more specific context name.

Supported _columnlist_ patterns:

- `[` _colname_ `,` ... `]`: Present columns from the table with name matching _colname_, in the order specified in the list. Ignore listed _colname_ values that do not correspond to column in the table. Do not present table columns that are not specified in the list.

### 2016 Foreign Key

`tag:isrd.isi.edu,2016:foreign-key`

This key allows augmentation of a foreign key reference constraint
with additional presentation information.

Supported JSON payload patterns:

- `{` ... `"id":` _id_ ... `}`: A unique _id_ can be assigned to one foreign key reference constraint for easier cross-referencing. (See related [2016 Visible Foreign Keys](#2016-visible-foreign-keys) annotation.) The _id_ MUST be unique among all uses of this annotation in the same catalog.
- `{` ... `"from_name":` _fname_ ... `}`: The _fname_ string is a preferred name for the set of entities containing foreign key references described by this constraint.
- `{` ... `"to_name":` _tname_ ... `}`: The _tname_ string is a preferred name for the set of entities containing keys described by this constraint.

Heuristics (use first applicable rule):

1. A set of "related entities" make foreign key reference to a presentation context:
  - The _fname_ is a preferred name for the related entity set.
  - The name of the table containing the related entities may be an appropriate name for the set, particularly if the table has no other relationship to the context.
  - The name of the table can be composed with other contextual information, e.g. "Tablename having columnname = value".
2. To name a set of "related entities" linked to a presentation context by an association table:
  - The _tname_ of the foreign key from association table to related entities is a preferred name for the related entity set.
  - The name of the table containing the related entities may be an appropriate name for the set, particularly if the table has no other relationship to the context.

### 2016 Table Display

`tag:isrd.isi.edu,2016:table-display`

This key allows specification of table presentation options at the table or schema level of the model.

Supported JSON payload patterns:

- `{`... `"row_name":` _pattern_ ...`}`: The _row_name_ indicates the presentation name to use to represent a row from a table. The row name is specified in the form of a _pattern_ as defined by the [Pattern Expansion](#pattern-expansion) section. This option only applies when annotating a Table.
- `{`... `"row_order":` `[` _sortkey_ ... `]` `}`: The list of one or more _sortkey_ defines the preferred or default order to present rows from a table. The ordered list of sort keys starts with a primary sort and optionally continues with secondary, tertiary, etc. sort keys.
- `{`... `"row_order":` null `}`: No preferred order is known.

Supported JSON _sortkey_ patterns:

- `{ "column":` _columnname_ `, "descending": true }`: Sort according to the values in the _columnname_ column in descending order. This is equivalent to the ERMrest sort specifier `@sort(` _columnname_ `::desc::` `)`.
- `{ "column":` _columnname_ `, "descending": false }`: Sort according to the values in the _columnname_ column in ascending order. This is equivalent to the ERMrest sort specifier `@sort(` _columnname_ `)`.
- `{ "column":` _columnname_ `}`: If omitted, the `"descending"` field defaults to `false` as per above.
- `"` _columnname_ `"`: A bare _columnname_ is a short-hand for `{ "column":` _columnname_ `}`.

#### 2016 Table Display Settings Hierarchy

The `"row_name"` and `"row_order"` settings apply only to tables, but MAY be annotated at the schema level to set a schema-wide default, if appropriate in a particular model. Any table-level specification of these settings will override the behavior for that table. These settings on other model elements are meaningless and ignored.

For hierarchically inheritable settings, an explicit setting of `null` will turn *off* inheritence and restore default behavior for that modele element and any of its nested elements.

### 2016 Visible Foreign Keys

`tag:isrd.isi.edu,2016:visible-foreign-keys`

This key indicates that the presentation order and visibility for
foreign keys referencing a table, useful when presenting "related entities".

Supported JSON payload pattern:

- `{` ... _context_ `:` _fkeylist_ `,` ... `}`: A separate _fkeylist_ can be specified for any number of _context_ names.

For presentation contexts which are not listed in the annotation, or when the annotation is entirely absent, all available foreign keys SHOULD be presented unless the application has guidance from other sources.

Supported _context_ names:

- `entry`: Any data-entry presentation context, i.e. when prompting the user for input column values.
  - `edit`: A sub-context of `entry` that only applies to editing existing resources.
  - `create`: A sub-context of `entry` that only applies to creating new resources.
- `filter`: Any data-filtering control context, i.e. when prompting the user for column constraints or facets.
- `compact`: Any compact, tabular presentation of data from multiple entities.

Supported _keylist_ patterns:

- `[` _id_ `,` ... `]`: Present foreign keys with matching _id_, in the order specified in the list. Ignore listed _id_ values that do not correspond to foreign keys in the catalog. Do not present foreign keys that are not specified in the list.

The _id_ value for a foreign key is established using the `"id"` field of the related [2016 Foreign Key](#2016-foreign-key) annotation.

### 2016 Abstracts Table

`tag:isrd.isi.edu,2016:abstracts-table`

This key indicates that the annotated table _abstracts_ another
table. This means that they both represent the same _entity set_ but
the abstraction has modified the representation of each entity in some
way.

Supported JSON payload patterns:

- `{` ... `"schema" :` _sname_, `"table" :` _tname_ ... `}`: The table identified by _sname_:_tname_ is the base storage table being abstracted by the table bearing this annotation.
- `{` ... `"contexts" : [` _context_ `,` ... `]` ... `}`: The abstraction is preferred in the listed application context(s).

A table which abstracts another table _SHOULD_ have a non-null (primary) key which is also a foreign key to the table it abstracts. Otherwise, a consuming application would not know how to navigate from one abstracted representation of an entity to another representation from the base storage tables.

Supported _context_ names:

- `filter`: Any data-filtering control context, i.e. when prompting the user for column constraints or facets.
- `compact`: Any compact, tabular presentation of data from multiple entities.
- `detailed`: Any read-only, entity-level presentation.

It is assumed that any application context that is performing mutation (record creation, deletion, or editing) MUST use a base entity storage table that is not an abstraction over another table. However, the use of the `detailed` context MAY offer an abstraction that augments the presentation of an existing record. An application offering mutation options while displaying an existing entity record might then present the data from the `detailed` abstraction but only offer editing or data-entry controls on the fields available from the base storage table.
