
# 
# Copyright 2012-2019 University of Southern California
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

"""ERMREST exception types to signal REST HTTP errors

"""

import web

class WebException (web.HTTPError):
    def __init__(self, status, data=u'', headers={}, desc=u'%s'):
        if data is not None and desc is not None:
            data = ('%s\n%s\n' % (status, desc)) % data
            headers['Content-Type'] = 'text/plain'
        else:
            data = None
        try:
            web.ctx.ermrest_request_trace(data)
        except:
            pass
        web.HTTPError.__init__(self, status, headers=headers, data=data if data is not None else '')

class NotModified(WebException):
    def __init__(self, data=u'', headers={}):
        status = '304 Not Modified'
        desc = None
        WebException.__init__(self, status, headers=headers, data=data, desc=desc)

class BadRequest (WebException):
    def __init__(self, data=u'', headers={}):
        status = '400 Bad Request'
        desc = u'The request is malformed. %s'
        WebException.__init__(self, status, headers=headers, data=data, desc=desc)

class Unauthorized (WebException):
    def __init__(self, data=u'', headers={}):
        status = '401 Unauthorized'
        desc = u'The requested %s requires authorization.'
        WebException.__init__(self, status, headers=headers, data=data, desc=desc)

class Forbidden (WebException):
    def __init__(self, data=u'', headers={}):
        status = '403 Forbidden'
        desc = u'The requested %s is forbidden.'
        if web.ctx.webauthn2_context.client is None:
            status = '401 Unauthorized'
        WebException.__init__(self, status, headers=headers, data=data, desc=desc)

class NotFound (WebException):
    def __init__(self, data=u'', headers={}):
        status = '404 Not Found'
        desc = u'The requested %s could not be found.'
        WebException.__init__(self, status, headers=headers, data=data, desc=desc)

class NoMethod (WebException):
    def __init__(self, data=u'', headers={}):
        status = '405 Method Not Allowed'
        desc = (u'The requested method %s is not allowed: %%s.' % web.ctx.method)
        WebException.__init__(self, status, headers=headers, data=data, desc=desc)

class Conflict (WebException):
    def __init__(self, data=u'', headers={}):
        status = '409 Conflict'
        desc = u'The request conflicts with the state of the server. %s'
        WebException.__init__(self, status, headers=headers, data=data, desc=desc)

class PreconditionFailed (WebException):
    def __init__(self, data=u'', headers={}):
        status = '412 Precondition Failed'
        desc = 'Resource state does not match requested preconditions. %s'
        WebException.__init__(self, status, headers=headers, data=data, desc=desc)

class UnsupportedMediaType (WebException):
    def __init__(self, data=u'', headers={}):
        status = '415 Unsupported Media Type'
        desc = u'The request input type is not supported. %s'
        WebException.__init__(self, status, headers=headers, data=data, desc=desc)

class RuntimeError (WebException):
    def __init__(self, data=u'', headers={}):
        status = '500 Internal Server Error'
        desc = u'The request execution encountered a runtime error: %s.'
        WebException.__init__(self, status, headers=headers, data=data, desc=desc)

class ServiceUnavailable (WebException):
    def __init__(self, data=u'', headers={}):
        status = '503 Service Unavailable'
        desc = u'The service is temporarily unavailable: %s.'
        WebException.__init__(self, status, headers=headers, data=data, desc=desc)
