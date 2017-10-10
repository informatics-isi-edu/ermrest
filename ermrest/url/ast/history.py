
# 
# Copyright 2017 University of Southern California
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#    http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import json
import web

from ...model import current_request_snaptime
from ... import exception
from ...util import sql_literal
from .api import Api

def _post_commit(handler, resource, content_type='text/plain', transform=lambda v: v):
    handler.emit_headers()
    if resource is None and content_type == 'text/plain':
        return ''
    if resource is '' and web.ctx.status == '200 OK':
        web.ctx.status = '204 No Content'
        return ''
    web.header('Content-Type', content_type)
    response = transform(resource)
    web.header('Content-Length', len(response))
    return response

def _MODIFY(handler, thunk, _post_commit):
    def body(conn, cur):
        h_from, h_until = web.ctx.ermrest_history_snaprange
        amendver = web.ctx.ermrest_history_amendver
        # this is the ETag at start of request processing
        handler.set_http_etag('%s-%s' % (h_until, amendver))
        handler.http_check_preconditions(method='PUT')
        result = thunk(conn, cur)
        # this is the ETag resulting from request processing
        amendver = current_request_snaptime(cur)
        handler.set_http_etag('%s-%s' % (h_until, amendver))
        return result
    return handler.perform(body, lambda resource: _post_commit(handler, resource))

def _MODIFY_with_json_input(handler, thunk, _post_commit):
    try:
        doc = json.load(web.ctx.env['wsgi.input'])
    except:
        raise exception.rest.BadRequest('Could not deserialize JSON input.')
    return _MODIFY(handler, lambda conn, cur: thunk(conn, cur, doc), _post_commit)

class CatalogHistory (Api):
    """Represents whole-catalog history resource.

       URL: /ermrest/catalog/N/history/from,until

    """
    def __init__(self, history_catalog):
        Api.__init__(self, history_catalog)

    def DELETE_body(self, conn, cur):
        self.enforce_right('owner')
        h_from, h_until = web.ctx.ermrest_history_range
        if h_from is not None:
            raise exception.BadData('History truncation requires an empty lower time bound.')
        if h_until is None:
            raise exception.BadData('History truncation requires an upper time bound.')
        # TODO: perform history truncation
        raise exception.ConflictModel('History truncation not yet implemented.')

    def DELETE(self, uri):
        return _MODIFY(self, self.DELETE_body, _post_commit)

def _validate_model_rid(cur, rid, restypes={'schema', 'table', 'column', 'key', 'pseudo_key', 'fkey', 'pseudo_fkey'}):
    for restype in restypes:
        cur.execute("""
SELECT True FROM _ermrest_history.known_%(restype)ss WHERE "RID" = %(target_rid)s LIMIT 1;
""" % {
    'restype': restype,
    'target_rid': sql_literal(rid),
})
        res = cur.fetchone()
        if res is not None:
            return restype
    raise exception.NotFound('Historical model resource with RID=%s' % rid)
    
class DataHistory (Api):
    """Represents data history resources.

       URL1: /ermrest/catalog/N/history/from,until/attribute/CRID
       URL2: /ermrest/catalog/N/history/from,until/attribute/CRID/FRID=FVAL

    """
    def __init__(self, history_catalog, target_rid, filter_rid=None, filter_val=None):
        Api.__init__(self, history_catalog)
        self.target_rid = target_rid
        self.filter_rid = None
        self.filter_val = None

    def filtered(self, filter_rid, filter_val):
        """Add a value filter to a data history resource."""
        self.filter_rid = filter_rid
        self.filter_val = filter_val
        return self

    def validate_target(self, cur):
        self.target_type = _validate_model_rid(cur, self.target_rid, {'table', 'column'})

    def DELETE_body(self, conn, cur):
        self.enforce_right('owner')
        h_from, h_until = web.ctx.ermrest_history_range
        if h_from is None:
            raise exception.BadData('Redaction requires a lower time bound.')
        if h_until is None:
            raise exception.BadData('Redaction requires an upper time bound.')
        self.validate_target(cur)
        # TODO: perform data redaction
        raise exception.ConflictModel('Historical data redaction not yet implemented.')

    def DELETE(self, uri):
        return _MODIFY(self, self.DELETE_body, _post_commit)

class ConfigHistory (Api):
    """Represents over-writable configuration resources.

       URL 1: /ermrest/catalog/N/history/from,until/API
       URL 2: /ermrest/catalog/N/history/from,until/RID/API

       This ugly code handles a matrix of target types and payload types.
    
       RID, when present, is the model resource RID of the config subject.
       API is the subresource type 'acl', 'acl_binding', or 'annotation'.

    """
    subresource_apis = {
        'acl':         (),
        'acl_binding': (),
        'annotation':  (),
    }
    
    def __init__(self, history_catalog, subresource_api, target_rid=None):
        Api.__init__(self, history_catalog)
        assert subresource_api in subresource_apis
        self.subresource_api = subresource_api
        self.target_rid = target_rid
        self.target_type = None

    def validate_target(self, cur):
        if self.target_rid is None:
            self.target_type = 'catalog'
        else:
            # probe each resource type to figure out what the RID refers to...
            self.target_type = _validate_mode_rid(cur, self.target_rid)

    def PUT_body(self, cur, content):
        self.enforce_right('owner')
        if h_from is None:
            raise exception.BadData('Historical %s amendment requires a lower time bound.' % self.subresource_api)
        if h_until is None:
            raise exception.BadData('Historical %s amendment requires an upper time bound.' % self.subresource_api)
        self.validate_target(cur)
        # TODO: amend historical config
        raise exception.ConflictModel('Historical %s amendment not yet implemented.' % self.subresource_api)

    def PUT(self, uri):
        return _MODIFY_with_json_input(self, self.PUT_body, _post_commit)
