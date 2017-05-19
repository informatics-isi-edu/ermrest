# ERMrest

[ERMrest](http://github.com/informatics-isi-edu/ermrest) (rhymes with
"earn rest") is a general relational data storage service for web-based, data-oriented collaboration. It allows general entity-relationship modeling of data resources manipulated by RESTful access methods.

## Status

[![Build Status](https://travis-ci.org/informatics-isi-edu/ermrest.svg?branch=master)](https://travis-ci.org/informatics-isi-edu/ermrest)

ERMrest is research software, but its core features have proven stable enough to use in several production science projects.

**Known Issues**: See our list of [known issues](https://github.com/informatics-isi-edu/ermrest/issues?q=is%3Aopen+is%3Aissue+label%3Abug) at GitHub.

## Using ERMrest

As a protocol, the [ERMrest REST API](api-doc/index.md) can be easily accessed by browser-based applications or any basic HTTP client library. Its main features:
- Exposes a PostgreSQL RDBMS containing science data.
- Model neutrality
  - Allows use of natural, domain-specific relational data schema rather than forcing a fixed and generic schema.
  - Supports schema and data introspection by clients to allow generic presentation of tabular data rather than only hard-coded and domain-specific clients.
- An expressive set of data access methods
  - Set-based single and bulk whole-entity (table row) create/read/update/delete (CRUD);
  - Set-based single and bulk partial-entity (table cell) read/update (RU);
  - Aggregate and grouped aggregate queries;
  - Convenient ERM _navigation_ to map common relational _inner join_ idioms into URL path structures.
- Multi-tenancy to easily allow multiple _catalogs_, each with its own schema and data content.
  - Group/role-based permissions for catalog-level access
    - Catalog visibility
	- Schema management
	- Data retrieval
	- Data modification
  - Fine-grained [access control lists](user-doc/acls.md) to manage access policies

### Prerequisites

ERMrest is developed and tested primarily on the CentOS 7 enterprise Linux distribution with Python 2.7. It has a conventional web service stack:
- Apache HTTPD
- mod_wsgi
- web.py lightweight web framework
- psycopg2 database driver
- PostgreSQL 9.5 or later (9.6 recommended)
- webauthn security adaptation layer (another product of our group)

### Installation

See [ERMrest Installation (CentOS 7)](user-doc/install-centos7.md).

### Operational Model

1. The HTTPS connection is terminated by Apache HTTPD.
1. The `mod_webauthn` Apache HTTPD module determined authenticated client context for requests
1. The ERMrest service code executes as the `ermrest` daemon user
1. The service configuration is loaded from `~ermrest/ermrest_config.json`:
  - Core access control policy for catalog creation.
  - Data type presentation.
1. All dynamic data is stored in the RDBMS.
  - The catalog's data model
  - The catalog's fine-grained access control lists
  - The catalog's data content
1. Client authentication context is retrieved from Apache request environment
  - Client identity
  - Client roles/group membership.
1. Catalog-level authorization of service requests is determined by the service code:
  - ACLs retrieved from RDBMS
  - ACLs are intersected with authenticated client context.
1. The RDBMS is accessed using daemon service credentials
  - Fine-grained *static* authorization is handled in service prior to executing SQL
  - Fine-grained *dynamic* authorization is handled in service by compiling policy checks into SQL

## Help and Contact

Please direct questions and comments to the [project issue tracker](https://github.com/informatics-isi-edu/ermrest/issues) at GitHub.

## License

ERMrest is made available as open source under the Apache License,
Version 2.0. Please see the [LICENSE file](LICENSE) for more
information.

## About Us

ERMrest is developed in the
[Informatics group](http://www.isi.edu/research_groups/informatics/home)
at the [USC Information Sciences Institute](http://www.isi.edu). The
primary design team is:

- Karl Czajkowski
- Carl Kesselman
- Rob Schuler
- Serban Voinea
