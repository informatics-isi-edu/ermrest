# ermrest-freetext-indices

The script `ermrest-freetext-indices` is a utility script for
advanced, legacy use cases.  Please see [caveats](#caveats) below
before attempting to use this script.

## Synopsis

Invoke as the `ermrest` daemon user on the ERMrest web server:

`ermrest-freetext-indices` _catalog_ _schema_ ...

Creates indices on tables under one or more given schema names for
a given catalog ID.

## Description

`ermrest-freetext-indices` processes a local database containing one
ERMrest catalog in order to create additional column indices in the
database.  It prepares `btree` and `gin_trgm_ops` column indexes
useful for accelerating general Chaise functionality.

### Caveats

Most simple ERMrest deployments do not need to use this script.

1. This script is unnecessary on catalogs managed by the ERMrest HTTP
   interface. Tables created through the REST API are indexed
   automatically in the same way managed by this script. This script
   is only useful when a DBA has locally customized the schema via SQL
   DDL statements and wishes to add missing indexes for improved
   performance when accessing those locally customized tables.
2. The term `freetext` in the script name is a bit of a misnomer. Long
   ago, Chaise used the ERMrest `::ts::` text-search operator for the
   search box, and this script was used to construct appropriate
   `tsvector` indices in the database. However, modern Chaise uses the
   ERMrest `::regexp::` operator for substring matching and this
   script only manages tri-gram indices appropriate for accelerating
   those searches.

## Options

`ermrest-freetext-indices` requires the following command-line arguments: 

- _catalog_: Identifier for the catalog, e.g. `1`
- _schema_: Name of a schema in the catalog, e.g. `isa`

The _schema_ parameter may be repeated to process more than one named schema
in a single invocation of the script.

If invoked without arguments, the script outputs a brief help message.

## Exit Status

Possible exit status codes:

- `0`: Successful invocation
- `1`: Command-line argument usage error
- `2`: ERMrest registry configuration error
- `3`: Given catalog not found in registry
- `4`: Given schema not found in catalog
- `5`: Other runtime errors

## Examples

To index the `isa` schema on catalog `1`:

- `ermrest-freetext-indices 1 isa`

To index the `isa` and `vocabulary` schema on catalog `2`:

- `ermrest-freetext-indices 2 isa vocabulary`

To index the `schema with spaces` schema on catalog `1`:

- `ermrest-freetext-indices 1 "schema with spaces"`
