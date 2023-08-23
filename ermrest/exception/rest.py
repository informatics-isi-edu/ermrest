
# 
# Copyright 2012-2023 University of Southern California
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

import flask
from webauthn2.util import deriva_ctx, RestException

class ErmrestException (RestException):

    def __init__(self, message=None, headers={}):
        if message is None:
            message = self.description
        else:
            message = '%s Detail: %s' % (self.description, message)
        super(ErmrestException, self).__init__(message, headers=headers)

class NoMethod (ErmrestException):
    code = 405
    description = 'Request method not allowed on this resource.'

class Conflict (ErmrestException):
    code = 409
    description = 'Request conflicts with state of server.'

class Forbidden (ErmrestException):
    code = 403
    description = 'Access forbidden.'
    title = 'Access Forbidden'

    def __init__(self, message=None, headers={}):
        # act as if we raised Unauthorized(...) if client is anonymous
        if deriva_ctx.webauthn2_context.client is None:
            self.code = Unauthorized.code
            self.description = Unauthorized.description
            self.title = Unauthorized.title
        super(Forbidden, self).__init__(message, headers=headers)

class Unauthorized (ErmrestException):
    code = 401
    description = 'Access requires authentication.'
    title = 'Authentication Required'

class NotFound (ErmrestException):
    code = 404
    description = 'Resource not found.'

class BadRequest (ErmrestException):
    code = 400
    description = 'Request malformed.'

class NotModified(ErmrestException):
    code = 304
    title = 'Not Modified'
    description = ''

class PreconditionFailed (ErmrestException):
    code = 412
    title = 'Precondition Failed'
    description = 'Resource state does not match requested preconditions.'

class UnsupportedMediaType (ErmrestException):
    code = 415
    description = u'The request input type is not supported.'

class RuntimeError (ErmrestException):
    code = 500
    description = 'The request execution encountered a runtime error.'

class ServiceUnavailable (ErmrestException):
    code = 503
    title = 'Service Unavailable'
    description = 'The service is temporarily unavailable.'
