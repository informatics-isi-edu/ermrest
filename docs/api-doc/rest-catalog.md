# Catalog Operations

In this documentation and examples, the _service_ as described in the previous section on [model resource naming](model/naming.md) is assumed to be `https://www.example.com/ermrest`.

## Service Ad Retrieval

Outside of any catalog context, the __service__ itself offers a brief advertisement of its capability.

The GET method is used to retrieve the service advertisement. This
request also serves as a basic health-check of the ERMrest service:

    GET /ermrest/ HTTP/1.1
    Host: www.example.com

On success, this request yields the service advertisement:

    HTTP/1.1 200 OK
    Content-Type: application/json
    
    {
      "version": "0.2.0",
      "features": {
        ...
      }
    }

Typical error response codes include:
- 400 Bad Request (on legacy versions lacking this feature)
- 503 Service Unavailable (if basic service health-check is failing)

The `"version"` field is the ermrest Python package version as
installed.  The `"features"` field is where ERMrest may advertise
software features added in subsequent revisions. This allows
fine-grained feature detection by clients concerned with exploiting
new features, when available, but falling back to simpler access modes
if accessing older catalogs.

Known feature flags at time of writing of this document:

- `trs`: Service supports the `trs(RID)` projection functions to retrieve row-level access rights.
- `tcrs`: Service supports the `tcrs(RID)` projection functions to retrieve row-level, per-column access rights.
- `history_control`: Service supports `tag:isrd.isi.edu:2020,history-capture` table annotation to disable history capture.
- `implicit_fkey_index`: Service will produce indexes for compound foreign keys to allow index-based joins on these reference patterns.
- `catalog_post_input`: The POST `/ermrest/catalog` method accepts JSON input to customize the catalog ID or initial owner ACL.
- `catalog_alias`: The `/ermrest/alias` resource space and related catalog aliasing features are available.
- `indexing_preferences`: Service supports `tag:isrd.isi.edu:2018,indexing-preferences` annotations to influence index construction during table or model provisioning requests.
- `quantified_value_lists`: Service supports `all(...)` and `any(...)` URL syntax for lists of values as query predicate right-hand side values.

Generally, absence of a feature flag means the service is running
older software which predates the release of the feature. A flag will
be present with boolean value `true` to advertise presence of a
feature. Specific flags may be documented with other advertisement
values.

### Indexing Preferences Feature Flag

The `indexing_preferences` feature is reported as an object rather
than a simple boolean.  These individual boolean flags advertise which
index configuration hints are supported when using the :

- `btree`: Service interprets the indexing-preferences `btree` field holding a boolean flag to enable or disable built-in btree index construction where this is not required for service function. (A key constraint implies a type of btree index which cannot be disabled.)
- `btree_column_list`: Service interprets the indexing-preferences `btree` field holding a list of strings as an ordered list of named columns to include in a custom btree index. When possible, this overrides a default built-in btree index which the service would otherwise build for the annotated column.
- `trgm`: Service interpets the indexing-preferences `trgm` field holding a boolean flag to enable or disable built-in GIN tri-gram ops index construction for the annotated column, in support of the `::regexp::` and `::ciregexp::` predicates.
- `gin_array`: Service interpets the indexing-preferences `gin_array` field holding a boolean flag to enable built-in GIN array ops index construction for the annotated column, in support of `=` (equality) query predicates using quantified value lists `any(...)` or `or(...)`.


## Catalog Creation

The POST method is used to create an empty catalog:

    POST /ermrest/catalog HTTP/1.1
    Host: www.example.com

This method supports an optional JSON input document:

    POST /ermrest/catalog HTTP/1.1
    Host: www.example.com
    Content-Type: application/json

    {
      "id": desired catalog id,
      "owner": administrative ACL
    }

These fields are optional and, if present, override the default behavior obtained in a POST without input:

- `"id"`: The desired _cid_ to bind (default is a service-generated serial number)
- `"owner"`: Initial owner-level access control list for the new catalog (default is the requesting client's identity)

On success, this request yields the new catalog identifier, e.g. `42` in this example:

    HTTP/1.1 201 Created
    Location: /ermrest/catalog/42
    Content-Type: application/json
    
    {
      "id": "42"
    }

The configured `"owner"` will also appear in the `"acls"` sub-resource of the resulting catalog resource.

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

In the rare event that there is a system error during catalog creation, the ERMrest registry of catalogs may retain a record of a claimed catalog identifier without a corresponding catalog database. This record includes the `"owner"` and only clients authorized by that access control list may retry catalog creation with the same desired catalog id.

## Catalog Retrieval

The GET method is used to get a short description of a catalog by its canonical identifier or an alias:

    GET /ermrest/catalog/42 HTTP/1.1
    Host: www.example.com
    
On success, this request yields a catalog description:

    HTTP/1.1 200 OK
    Content-Type: application/json
    
    {
      "id": "42",
      "alias_target": target catalog identifier,
      "rights": {
        "owner": boolean,
        "create": boolean
      },
      "acls": {
        "owner": access control list,
        ...
      },
      "annotations": {
        "tag:isrd.isi.edu,2018:example": {"value": "my example annotation"}
      },
      "snaptime": "2PX-WS30-E58W",
      "features": {
        ...
      }
    }

The fields of this representation are:
- `"id"`: The identifier for the catalog being addressed (may be an alias or storage catalog identifier).
- `"alias_target"`: The canonical identifier for the storage catalog (only present when `"id"` is showing an alias instead).
- `"snaptime"`: The identifier for the snapshot being addressed.
- `"rights"`: A summary of rights for the requesting client.
- `"acls"`: Configured access control lists for this catalog.
- `"annotations"`: Configured annotations for this catalog.
- `"features"`: The service features advertisement as described in the [Service Ad Retrieval request](#service-ad-retrieval).

This representation summarizes the catalog which is affectively addressed by the catalog URL. Other catalog sub-resources described in this API documentation are likewise available relative to this catalog URL prefix. Access to sub-resources for catalog, schema, and content management and access are consistent whether the catalog URL prefix is using a canonical storage catalog _cid_ or a catalog _alias_.

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

## Catalog Deletion

The DELETE method is used to delete a catalog:

    DELETE /ermrest/catalog/42 HTTP/1.1
    Host: www.example.com

There are two cases for catalog deletion via this API:

1. When DELETE `/ermrest/catalog/` _alias_ names a catalog by alias: equivalent to DELETE `/ermrest/alias/` _alias_ while the underlying storage catalog is unaffected.
2. When DELETE `/ermrest/catalog/` _cid_ names a storage catalog identifier, the catalog and its content are destroyed, unbinding (but not destroying) any existing aliases which have _cid_ as their `"alias_target"`.

On success, this request yields a description:

    HTTP/1.1 204 No Content

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

## Catalog Alias Creation

The POST method is used to create an alias resource:

    POST /ermrest/alias HTTP/1.1
    Host: www.example.com

This method supports an optional JSON input document:

    POST /ermrest/alias HTTP/1.1
    Host: www.example.com
    Content-Type: application/json

    {
      "id": desired alias id,
      "owner": administrative access control list,
      "alias_target": existing storage catalog id
    }

These fields are optional and, if present, override the default behavior obtained in a POST without input:

- `"id"`: The desired _alias_ to bind (default is a service-generated serial number)
- `"owner"`: Initial access control list for the alias (default is the requesting client's identity)
- `"alias_target"`: Storage catalog to bind with the new alias (default unbound)

An unbound alias can reserve the alias for future use by clients permitted by the adminstrative access control list.

On success, this request yields the new catalog alias, e.g. `my_alias` in this example:

    HTTP/1.1 201 Created
    Location: /ermrest/catalog/42
    Content-Type: application/json
    
    {
      "id": "my_alias"
    }

The configured `"owner"` and `"alias_target"` will also appear in the resulting alias resource.

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

## Catalog Alias Retrieval

The GET method is used to get a short description of an alias:

    GET /ermrest/alias/my_alias HTTP/1.1
    Host: www.example.com
    
On success, this request yields a description:

    HTTP/1.1 200 OK
    Content-Type: application/json
    
    {
      "id": "my_alias",
      "owner": administrative access control list,
      "alias_target": "42"
    }

The fields of this representation are:
- `"id"`: The alias identifier.
- `"owner"`: The access control list granting permission to manage this alias.
- `"alias_target"`: The canonical identifier for the storage catalog (may be `null` for unbound aliases.

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

## Catalog Alias Update

The PUT method is used to modify the configuration of an alias:

    PUT /ermrest/alias/my_alias HTTP/1.1
    Host: www.example.com
    Content-Type: application/json
    
    {
      "id": "my_alias",
      "owner": new administrative access control list,
      "alias_target": new target catalog identifier
    }

Either field is optional and defaults to leaving the respective configuration unchanged:

- `"owner"`: Set a new administrative access control list for the alias.
- `"alias_target"`: Bind or re-bind the alias to the specified storage catalog.

For ease of use, the `"id"` field is also accepted as input, so that an existing alias representation could be edited and resubmitted. However, the included `"id"` field MUST match the _alias_ identifier in the URL.

On success, this request yields a description of the updated alias:

    HTTP/1.1 200 OK
    Content-Type: application/json
    
    {
      "id": "my_alias",
      "owner": administrative access control list,
      "alias_target": "42"
    }

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

## Catalog Alias Deletion

The DELETE method is used to delete a catalog alias:

    DELETE /ermrest/alias/my_alias HTTP/1.1
    Host: www.example.com
    
On success, this request yields a description:

    HTTP/1.1 204 No Content

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized
