# Deprecated Model Annotations

This document collects a set of deprecated annotations. These are in
use in some legacy applications but for new work, please see
[recommended annotations](annotation.md) instead.

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

## Annotations

Some annotations are supported on multiple types of model element, so
here is a quick matrix to locate them.

| Annotation | Schema | Table | Column | Key | FKR | Summary |
|------------|--------|-------|--------|-----|-----|---------|
| [2015 Binary Relationship](#2015-binary-relationship) | - | - | - | - | - | Retracted. |
| [2015 Default](#2015-default) | X | - | - | - | - | Deprecated for use on schema objects. |
| [2015 Facets](#2015-facets) | - | X | - | - | - | Retracted. |
| [2015 Hidden](#2015-hidden) | X | X | X | - | X | Retracted. |
| [2015 URL](#2015-url) | - | X | X | - | - | Column or table data as URLs |
| [2016 Sequence](#2016-sequence) | - | - | X | - | - | Column as a Gene Sequence |

For brevity, the annotation keys are listed above by their section
name within this documentation. The actual key URI follows the form
`tag:misd.isi.edu,` _date_ `:` _key_ where the _key_ part is
lower-cased with hyphens replacing whitespace. For example, the first
`2015 Default` annotation key URI is actually
`tag:misd.isi.edu,2015:default`.

### ~~2015 Binary Relationship~~

`tag:misd.isi.edu,2015:binary-relationship`

This annotation proposal has been retracted. At time of retraction, no uses of the annotation exist in the wild.

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

