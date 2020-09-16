# Catalog Operations

In this documentation and examples, the _service_ as described in the previous section on [model resource naming](model/naming.md) is assumed to be `https://www.example.com/ermrest`.

## Catalog Creation

The POST method is used to create an empty catalog:

    POST /ermrest/catalog HTTP/1.1
    Host: www.example.com
    
On success, this request yields the new catalog identifier, e.g. `42` in this example:

    HTTP/1.1 201 Created
    Location: /ermrest/catalog/42
    Content-Type: application/json
    
    {
      "id": "42",
      "snaptime": "2PX-WS30-E58W"
    }

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

## Catalog Retrieval

The GET method is used to get a short description of a catalog:

    GET /ermrest/catalog/42 HTTP/1.1
    Host: www.example.com
    
On success, this request yields a description:

    HTTP/1.1 200 OK
    Content-Type: application/json
    
    {
      "id": "42",
      "annotations": {
        "tag:isrd.isi.edu,2018:example": {"value": "my example annotation"}
      },
      "snaptime": "2PX-WS30-E58W",
      "features": {
         ...
      }
    }

The `"features"` field is where ERMrest may advertise software
features added in subsequent revisions. This allows fine-grained
feature detection by clients concerned with exploiting new features,
when available, but falling back to simpler access modes if accessing
older catalogs.

Known feature flags at time of writing of this document:

- `history_control`: Service supports `tag:isrd.isi.edu:2020,history-capture` table annotation to disable history capture.

Generally, absence of a feature flag means the service is running
older software which predates the release of the feature. A flag will
be present with boolean value `true` to advertise presence of a
feature. Specific flags may be documented with other advertisement
values in the future, i.e. to indicate runtime status of a feature
which can be disabled selectively by the administrator.

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

## Catalog Deletion

The DELETE method is used to delete a catalog and all its content:

    DELETE /ermrest/catalog/42 HTTP/1.1
    Host: www.example.com
    
On success, this request yields a description:

    HTTP/1.1 204 No Content

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

