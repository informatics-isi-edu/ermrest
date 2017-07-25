
# Chado Vocabulary Patterns

This page is to explore some possible use-case patterns for using
Chado schema for controlled vocabularies.

## Assumptions and conventions

1. We want to load ontologies easily, so being consistent with Chado is probably helpful.
2. We want to separate ontology/vocabulary preparation from normal data management operations
   - Vocabularies and terms are defined *before* use in data tables
   - Restricted domain tables are used to present subsets of ontologies for use in data columns
   - Data serialization should not depend on order vocabularies are loaded
3. We will use the dbxref concept specifically with _DB_ `:` _ACCESSION_ `:` _VERSION_ textual formatted indentifiers as keys and foreign keys in vocabulary storage columns, e.g. `OBO_REL:is_a:`.

## Chado-derived core tables

Assume a basic ontology storage area similar to
[Chado CV Module](http://gmod.org/wiki/Chado_CV_Module).  Here, we
only focus on the few tables that would affect normal data
management.

### db
The `db` table enumerates database authorities.
```
CREATE TABLE db (
  name text PRIMARY KEY,
  description text,
  urlprefix text,
  url text
  );

```

### cv
The `cv` table enumerates controlled vocabularies.
```
CREATE TABLE cv (
  name text PRIMARY KEY,
  definition text
);

```

### dbxref
The `dbxref` table enumerates global, unique, stable public identifiers. This table probably won't be used in day-to-day
queries because the db, accession, and version are included in denormalized form elsewhere; it's included in the model
because this is the only place the dbxref `description` field exists.
```
CREATE TABLE dbxref (
  name text PRIMARY KEY,
  db text NOT NULL REFERENCES db(name) DEFERRABLE,
  accession text NOT NULL,
  version text NOT NULL DEFAULT '',
  description text,
  UNIQUE(db, accession, version)
);
```
### cvterm

The `cvterm` table enumerates all available terms. In addition to denormalizing the `dbxref` and `cv` fields, we've
added a `dbxref_unversioned` field (the dbxref without version information, which is likely to be searched for) and
array fields for synonyms and alternate dbxrefs (derived from the chado `cvtermsynonym` and `cvterm_dbxref` tables).

```
create table cvterm (
  dbxref text PRIMARY KEY REFERENCES dbxref(name) DEFERRABLE,
  dbxref_unversioned text NOT NULL,
  cv text NOT NULL REFERENCES cv(name) DEFERRABLE,
  name text NOT NULL,
  definition text,
  is_obsolete boolean NOT NULL,
  is_relationshiptype boolean NOT NULL,
  synonyms text[],
  alternate_dbxrefs text[],
  UNIQUE(cv, name, is_obsolete),
  CHECK(dbxref LIKE dbxref_unversioned || ':%')
);
```

### cvtermpath

The `cvtermpath` table stores transitive closures of term-to-term relationship graphs.
The `cvtermpath_id` field is present only because ermrest requires a single-valued unique key.

```
CREATE TABLE cvtermpath (
  cvtermpath_id bigserial PRIMARY KEY,
  type_dbxref text NOT NULL REFERENCES cvterm(dbxref) DEFERRABLE,
  subject_dbxref text NOT NULL REFERENCES cvterm(dbxref) DEFERRABLE,
  object_dbxref text NOT NULL REFERENCES cvterm(dbxref) DEFERRABLE,
  pathdistance integer NOT NULL,
  UNIQUE(type_dbxref, subject_dbxref, object_dbxref)
);  
```

We constrain the path table:

1. Don't allow NULL `type_dbxref` which is a closure over multiple relationships
2. Don't store multiple rows for same subject, relationship, object. Store *minimum* path distance.

## Domain tables

We can have any number of domain tables to enumerate a subset of
controlled vocabulary terms. Each domain table is a filtered subset of
`cvterm` with the same structure. A domain table could be implemented as
materialized views defined with `create materialized view mydomain1 as select * from cvterm where ...`,
as tables curated by hand, etc.

```
CREATE TABLE mydomain1 (
  cvtermpath_id bigserial PRIMARY KEY,
  type_dbxref text NOT NULL REFERENCES cvterm(dbxref) DEFERRABLE,
  subject_dbxref text NOT NULL REFERENCES cvterm(dbxref) DEFERRABLE,
  object_dbxref text NOT NULL REFERENCES cvterm(dbxref) DEFERRABLE,
  pathdistance integer NOT NULL,
  UNIQUE(type_dbxref, subject_dbxref, object_dbxref)
);
```
We want a foreign key reference constraint to emphasize that the domain table is a proper subset of the core cvterm table.

## Domain path tables
For each domain table, we will have a corresponding table defined as a subset of
`cvtermpath` with all records that include any term in the domain table. For example,
a domain path table could be defined with
```
create materialized view mydomain1_path as
  select * from cvtermpath p
  join mydomain1 d on d.dbxref = p.subject_dbxref or d.dbxref = p.object_dbxref;
```

## Data tables using controlled terms

We can use controlled vocabularies for any number of data columns by
configuring a foreign key constraint to a domain table.

```
CREATE TABLE mydata (
   ...
   myconcept text REFERENCES mydomain1 (dbxref),
   ...
);
```

## Heuristics and idioms

### Basic data access

Naive access to data tables can completely ignore the connections to a
vocabulary and just consume the stored data column as explicit dbxref
strings.

### Data integrity and basic value enumeration

Any consumer can introspect the data table and understand the foreign
key constraint to see which dbxref values are allows in a data
column. The database will enforce the foreign key integrity to prevent
values from being added to a data column outside the configured domain
term set.

### Prettier term display

Because the domain table uses the same schema as the core cvterm table,
it includes definitions and other metadata. Some presentation customization
can be done based on this information alone. However, there might be more
vocabulary-aware UX features desired in some cases?

Options:

1. Use normal Chaise/annotation features to adjust domain table "row name".
2. Detect fkey chain to core cvterm table to enable special vocabulary functions?
3. Annotate domain tables to enable special vocabulary functions?

### Semantic search via transitive closures

Any consumer can recognize the foreign key chain, through domain
table, to the `cvterm` table and the presence of the `cvtermpath`
table encoding inter-term relationships.

A phase 1 joined query similar to this ERMrest URL can be used to
search for a set of terms:

```
/catalog/N/attribute/P:=cvtermpath/T:=(type_id)/dbxref=REL/pathdistance::lt::10/$P/O:=(object_id)/dbexref=BOUND/S:=(subject_id)/mydomain1/dbxref
```

This query would return a set of distinct dbxref values that are less
than `10` hops below an upper-bound dbxref `BOUND` in the graph of
`REL` relationship (mixed-in with `OBO_REL:is_a` (subclass)
relationship but only if the output terms also appear in the term
domain `mydomain1` which is a subset of all possible terms in the
system.

A phase 2 search can express actual data column constraints to match
on a disjunctive list of terms found by the phase 1 search.  Even if
we implement this on the server, we'd probably do the same two-phase
search, to in-line the bounded term set as a disjunction of constants
(that's our experience with how to get high performance out of
Postgres for complex analytic queries).

Options:

1. Do both search phases on client side with no new ERMrest API
   features.  Might hit some URL length limits eventually.
2. Add a filter syntax to ERMrest API to allow the query triplet of
   (term domain, relationship, and boundary to be encoded as a direct
   predicate on a data column.  E.g. `column::relationship::boundary`
   
Discussion:

To add a query syntactic sugar to ERMrest, we'd need to hard-code a
mapping of directed relationship terms, e.g. `OBO_REL:is_a`, to new
ERMrest predicate operators, e.g. `::subclass_of::` and
`::has_subclass::` so we can express both upper and lower-bounded
constraints against a data column. The right-hand side of the
predicate would specify the boundary value as a dbxref string
(URL-encoded to escape the colon chars). With this sugar, the
`pathdistance` would not be able to be constrained since there is no
reasonable binary predicate syntax to combine relationship type,
boundary, and path-length.

To provide a GUI UX for semantic search, you probably need more than
to choose a relationship and type in dbxref boundary values. You
probably need the equivalent of the phase 1 search to show the user
how the term space expands from a particular combination of boundary
and relationship type while still being limited to the column's term
domain.  In order to present such a UX, you already have to have
client-side detection and awareness of when semantic search is
applicable as well as how to retrieve and preview these term
sub-graphs.

Assuming all the client-side work for a semantic search UX, it is not
clear what value the ERMrest syntactic sugar would add except
robustness against large term sets being encoded in URLs. The
client-side complexity does not change much as long as you need to
guide users through a query-construction UX...


## Open questions

### Should we differentiate between different types of synonyms?

Currently, all synonyms included in the `cvtermsynonym` table are included in the `synonyms` field of `cvterm`.
Synonyms can be of different types, however, and we may want to treat synonyms differently based on their type.
To facilitate discussion, I've included the `cvtermsynonym` table (denormalized for our-style foreign keys),
which includes all synonyms and their types:
```
create table cvtermsynonym (
  cvtermsynonym_id bigserial PRIMARY KEY,
  dbxref text NOT NULL REFERENCES cvterm(dbxref) DEFERRABLE,
  synonym text NOT NULL,
  synonym_type text,
  UNIQUE (dbxref, synonym)
);
```
### Which alternate dbxrefs should be included in the cvterm table?

Chado has a table called `cvterm_dbxref` which includes both external
dbxrefs and dbxrefs that are used for provenance
information. Currently, we include both in the `alternate_dbxrefs`
field of the `cvterm` database. To facilitate discussion, I've
included the `cvterm_dbxref` table (denormalized for our-style foreign
keys):

```
CREATE TABLE cvterm_dbxref (
  cvterm_dbxref_id bigserial PRIMARY KEY,
  cvterm text NOT NULL REFERENCES cvterm(dbxref) DEFERRABLE,
  alternate_dbxref text NOT NULL REFERENCES dbxref(name) DEFERRABLE,
  is_for_definition boolean,
  UNIQUE(primary_dbxref, alternate_dbxref)
);
```

### What dbxrefs should appear in the domain table?

Our current model specifies that domain tables should have the same format as `cvterm` tables, with the `dbxref` field a foreign
key to the `cvterm` table. For example, one entry from Uberon looks like this:

```
dbxref              | UBERON:0000006:
dbxref_unversioned  | UBERON:0000006
cv                  | uberon
name                | islet of Langerhans
definition          | the clusters of hormone-producing cells that are scattered throughout the pancreas
is_obsolete         | f
is_relationshiptype | f
synonyms            | {"pancreatic islet","pancreatic insula","islets of Langerhans","island of pancreas","island of Langerhans"}
alternate_dbxrefs   | {XAO:0000159:,VHOG:0000646:,UMLS:C0022131:,MIAA:0000076:,MESH:D007515:,MAT:0000076:,
                       URL:http://linkedlifedata.com/resource/umls/id/C0022131:,
		       URL:http://en.wikipedia.org/wiki/Islets_of_Langerhans:,GAID:324:,FMA:16016:,EV:0100130:,EMAPA:32927:,
		       EFO:0000856:,CALOHA:TS-0741:,BTO:0000991:,AAO:0010406:,NULL:C12608:,MP:0005215:,MESH:A03.734.414:,MA:0000127:}
```

A GUDMAP user is more likely to want to look for EMAPA:32927 than any
of the dbxrefs in this entry (`alternate_dbxrefs` includes the
versioned version EMAPA:32927:). It might make more sense for the
`dbxref_unversioned` column of the domain table to include the
unversioned dbxref that users are most likely to recognize, like this:
```
dbxref              | UBERON:0000006:
dbxref_unversioned  | EMAPA:32927
cv                  | uberon
name                | islet of Langerhans
definition          | the clusters of hormone-producing cells that are scattered throughout the pancreas
is_obsolete         | f
is_relationshiptype | f
synonyms            | {"pancreatic islet","pancreatic insula","islets of Langerhans","island of pancreas","island of Langerhans"}
alternate_dbxrefs   | {XAO:0000159:,VHOG:0000646:,UMLS:C0022131:,MIAA:0000076:,MESH:D007515:,MAT:0000076:,
                       URL:http://linkedlifedata.com/resource/umls/id/C0022131:,
		       URL:http://en.wikipedia.org/wiki/Islets_of_Langerhans:,GAID:324:,FMA:16016:,EV:0100130:,EMAPA:32927:,
		       EFO:0000856:,CALOHA:TS-0741:,BTO:0000991:,AAO:0010406:,NULL:C12608:,MP:0005215:,MESH:A03.734.414:,MA:0000127:}
```
If we do this, we might want to change the name `dbxref_unversioned` to something like `dbxref_common`.

### Second thoughts about arrays in cvterm

In Postgres, there are two equivalent ways to express "'foo' is an element of the array bar" in a query:
```
'foo' = ANY(bar)
```
or
```
'{foo}' <@ bar
```
The second form will take advantage of gin indexes; the first form will not. Pattern matching is also difficult on array elements.
We might want to consider dropping the array columns from `cvterm` and using `cvtermsynonym` and `cvterm_dbxref` instead.

## Implementation

See the [data commons chado directory](https://github.com/informatics-isi-edu/data-commons/tree/master/chado) for
scripts to create a data_commons schema and pull data from chado into those tables. See the
[data commons chado/obo directory](https://github.com/informatics-isi-edu/data-commons/tree/master/chado/obo)
for information about reading obo files into standard chado tables.
