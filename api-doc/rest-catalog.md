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
    
    {"id": "1", ...}

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

## Catalog Deletion

The DELETE method is used to delete a catalog and all its content:

    DELETE /ermrest/catalog/42 HTTP/1.1
    Host: www.example.com
    
On success, this request yields a description:

    HTTP/1.1 200 OK
    Content-Type: text/plain

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

BUG: change this to 204 No Content?


## Access Control List Retrieval

The GET method is used to get a summary of a specific access control (ACL)
list (`content_read_user` in this example):

    GET /ermrest/catalog/42/meta/content_read_user HTTP/1.1
	Host: www.example.com

On success, this request yields the ACL content as a key-value list:

	HTTP/1.1 200 OK
	Content-Type: application/json

	[{"k": "content_read_user", "v": "user1"}, {"k": "content_read_user", "v": "group2"}, ...]

This legacy representation is likely to change in future revisions.

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

## Access Control Entry Creation

The PUT method is used to add a role name, i.e. a user or group, to an ACL:

    PUT /ermrest/catalog/42/meta/content_read_user/user2 HTTP/1.1
	Host: www.example.com

On success, this request yields an empty response:

	HTTP/1.1 204 No Content

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

## Access Control Entry Retrieval

The GET method is used to get a specific member of a specific access
control (ACL) list (`user2` of `content_read_user` in this example):

    GET /ermrest/catalog/42/meta/content_read_user/user2 HTTP/1.1
	Host: www.example.com

On success, this request yields the ACL entry as a key-value list:

	HTTP/1.1 200 OK
	Content-Type: application/json

	[{"k": "content_read_user", "v": "user2"}]

This legacy representation is likely to change in future revisions.

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

## Access Control Entry Deletion

The DELETE method is used to add a role name, i.e. a user or group, to an ACL:

    DELETE /ermrest/catalog/42/meta/content_read_user/user2 HTTP/1.1
	Host: www.example.com

On success, this request yields an empty response:

	HTTP/1.1 204 No Content

Typical error response codes include:
- 404 Not Found
- 403 Forbidden
- 401 Unauthorized

