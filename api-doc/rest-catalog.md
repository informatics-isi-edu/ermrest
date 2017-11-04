# ERMrest Catalog Operations

In this documentation and examples, the _service_ as described in the previous section on [model resource naming](model/naming.md) is assumed to be `https://www.example.com/ermrest`.

## Catalog Creation

The POST method is used to create an empty catalog:

    POST /ermrest/catalog HTTP/1.1
    Host: www.example.com
    
On success, this request yields the new catalog identifier, e.g. `42` in this example:

    HTTP/1.1 201 Created
    Location: /ermrest/catalog/42
    Content-Type: application/json
    
    {"id": 42}

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
    
    {"id": "42", ...}

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

