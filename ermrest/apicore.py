
# 
# Copyright 2012-2013 University of Southern California
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

"""Core ERMrest API configuration and context.

   These are split out from ermrest_api dispatching module to avoid
   circular dependencies.

"""

import logging
from logging.handlers import SysLogHandler
import web
import datetime
import pytz
import struct
import urllib
import sys
import traceback
import itertools
import psycopg2
import webauthn2

from .exception import *

from .registry import get_registry
from .catalog import get_catalog_factory
from .util import negotiated_content_type, urlquote, random_name

__all__ = [
    'web_urls',
    'webauthn2_manager',
    'global_env'
    ]

## setup web service configuration data
global_env = webauthn2.merge_config(
    jsonFileName='ermrest_config.json', 
    built_ins={
        # TODO: are these used?
        # "default_limit": 100,
        # "db": "ermrest", 
        # "dbn": "postgres", 
        # "dbmaxconnections": 8
        }
    )

webauthn2_config = global_env.get('webauthn2', dict(web_cookie_name='ermrest'))
webauthn2_config.update(dict(web_cookie_path='/'))

# setup webauthn2 handler
webauthn2_manager = webauthn2.Manager(overrides=webauthn2_config)

# setup registry
registry_config = global_env.get('registry')
if registry_config:
    registry = get_registry(registry_config)
else:
    registry = None

# setup catalog factory
catalog_factory_config = global_env.get('catalog_factory')
if catalog_factory_config:
    catalog_factory = get_catalog_factory(catalog_factory_config)
else:
    catalog_factory = None

# setup logger and web request log helpers
logger = logging.getLogger('ermrest')
sysloghandler = SysLogHandler(address='/dev/log', facility=SysLogHandler.LOG_LOCAL1)
syslogformatter = logging.Formatter('%(name)s[%(process)d.%(thread)d]: %(message)s')
sysloghandler.setFormatter(syslogformatter)
logger.addHandler(sysloghandler)
logger.setLevel(logging.INFO)

# some log message templates
log_template = u"%(elapsed_s)d.%(elapsed_ms)3.3ds %(client_ip)s user=%(client_identity)s req=%(reqid)s"
log_trace_template = log_template + u" -- %(tracedata)s"
log_final_template = log_template + u" (%(status)s) %(method)s %(proto)s://%(host)s/%(uri)s %(range)s %(type)s"


def log_parts():
    """Generate a dictionary of interpolation keys used by our logging template."""
    now = datetime.datetime.now(pytz.timezone('UTC'))
    elapsed = (now - web.ctx.ermrest_start_time)
    parts = dict(
        elapsed_s = elapsed.seconds, 
        elapsed_ms = elapsed.microseconds/1000,
        client_ip = web.ctx.ip,
        client_identity = web.ctx.webauthn2_context and urllib.quote(web.ctx.webauthn2_context.client or '') or '',
        reqid = web.ctx.ermrest_request_guid
        )
    return parts


def request_trace(tracedata):
    """Log one tracedata event as part of a request's audit trail.

       tracedata: a string representation of trace event data
    """
    parts = log_parts()
    if isinstance(tracedata, Exception):
        parts['tracedata'] = u'%s' % tracedata
    else:
        parts['tracedata'] = tracedata
        
    logger.info( (log_trace_template % parts).encode('utf-8') )


def request_init():
    """Initialize web.ctx with request-specific timers and state used by our REST API layer."""
    web.ctx.ermrest_request_guid = random_name()
    web.ctx.ermrest_start_time = datetime.datetime.now(pytz.timezone('UTC'))
    web.ctx.ermrest_request_content_range = '-/-'
    web.ctx.ermrest_content_type = 'unknown'
    web.ctx.webauthn2_manager = webauthn2_manager
    web.ctx.webauthn2_context = webauthn2.Context() # set empty context for sanity
    web.ctx.ermrest_request_trace = request_trace
    web.ctx.ermrest_registry = registry
    web.ctx.ermrest_catalog_factory = catalog_factory
    web.ctx.ermrest_config = global_env
    web.ctx.ermrest_catalog_pc = None

    try:
        # get client authentication context
        web.ctx.webauthn2_context = webauthn2_manager.get_request_context()
    except (ValueError, IndexError):
        content_type = negotiated_content_type(
            ['text/html', '*'],
            '*'
            )
        if content_type == 'text/html':
            # bounce browsers through a login form and back
            refer = web.ctx.env['REQUEST_URI']
            # leave off /ermrest/ prefix due to web.SeeOther behavior
            raise web.SeeOther('/authn/session?referrer=%s' % urlquote(refer))
        else:
            raise rest.Unauthorized('service access')
    except (webauthn2.exc.AuthnFailed):
        raise rest.Forbidden('Authentication failed')


def request_final():
    """Log final request handler state to finalize a request's audit trail."""
    parts = log_parts()
    parts.update(dict(
            status = web.ctx.status,
            method = web.ctx.method,
            proto = web.ctx.protocol,
            host = web.ctx.host,
            uri = web.ctx.env['REQUEST_URI'],
            range = web.ctx.ermrest_request_content_range,
            type = web.ctx.ermrest_content_type
            ))
    logger.info( (log_final_template % parts).encode('utf-8') )

def web_method():
    """Wrap ERMrest request handler methods with common logic.

       This should be used to wrap any handler methods that get
       dispatched directly via web.py.
    
       NOTE: Because we already wrap our generic METHOD handler in the
       ermrest_apis.Dispatcher class, we should NOT explicitly wrap
       handler methods in the various parser-drive handler
       classes. Doing so would cause a double-wrapping.

    """
    def helper(original_method):
        def wrapper(*args):
            request_init()
            try:
                try:
                    try:
                        result = original_method(*args)
                        if hasattr(result, 'next'):
                            # force any transaction deferred in iterator
                            try:
                                first = result.next()
                            except StopIteration:
                                return result
                            return itertools.chain([first], result)
                        else:
                            return result
                    except:
                        et, e, tb = sys.exc_info()
                        request_trace(e)
                        raise
                except (rest.WebException, web.HTTPError), e:
                    # exceptions signal normal REST response scenarios
                    raise e
                except (ConflictModel, ConflictData), e:
                    raise rest.Conflict(e.message)
                except NotFound, e:
                    raise rest.NotFound(e.message)
                except BadData, e:
                    raise rest.BadRequest(e.message)
                except UnsupportedMediaType, e:
                    raise rest.UnsupportedMediaType
                except psycopg2.pool.PoolError, e:
                    raise rest.ServiceUnavailable(e.message)
                except psycopg2.Error, e:
                    # TODO: simplify postgres error text?
                    raise rest.Conflict( str(e) )
                except Exception, e:
                    et, ev, tb = sys.exc_info()
                    web.debug('got exception "%s"' % str(ev), traceback.format_exception(et, ev, tb))
                    raise
            finally:
                request_final()
        return wrapper
    return helper
