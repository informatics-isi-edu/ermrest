
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

"""ERMREST REST API mapping layer

This module integrates ERMREST as a web.py application:

   A. Loads an ermrest-config.json from the application working
      directory, i.e. the daemon home directory in a mod_wsgi
      deployment.  This data configures a global_env dictionary
      exported from this module.

   B. Configures a webauthn2.Manager instance for security services

   C. Configures a syslog logger

   D. Implements a Dispatcher class to parse ERMREST URLs and dispatch
      to a parser-constructed abstract syntax tree for each web
      request.

   E. Defines a web.py web_urls dispatch table that can be used to
      generate a WSGI app. This maps the core ERMREST Dispatcher as
      well as webauthn2 APIs under an /authn/ prefix.

The general approach to integrating ERMREST with web.py is to use the
web.py provided web.ctx thread-local storage for request state. This
includes preconfigured state:

  web.ctx.ermrest_request_guid: a random correlation key issued per request
  web.ctx.ermrest_start_time: a timestamp when web dispatch began
  web.ctx.webauthn2_context: authentication context for the web request
  web.ctx.webauthn2_manager: the manager used to get authentication context
  web.ctx.ermrest_request_trace(tracedata): a function to log trace data

The mapping also recognized "out" variables that can communicate
information back out of the dispatched request handler:

  web.ctx.ermrest_request_content_range: content range of response (default -/-)
  web.ctx.ermrest_request_content_type: content type of response (default unknown)

These are used in final request logging.

"""
import logging
from logging.handlers import SysLogHandler
import web
import random
import base64
import datetime
import pytz
import struct
import urllib
import sys
import traceback
import itertools
import psycopg2
import webauthn2

from .url import url_parse_func, ast
from .exception import *

from .registry import get_registry
from .catalog import get_catalog_factory
from .util import negotiated_content_type, urlquote

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
webauthn2_handler_factory = webauthn2.RestHandlerFactory(manager=webauthn2_manager)
UserSession = webauthn2_handler_factory.UserSession
UserPassword = webauthn2_handler_factory.UserPassword
UserManage = webauthn2_handler_factory.UserManage
AttrManage = webauthn2_handler_factory.AttrManage
AttrAssign = webauthn2_handler_factory.AttrAssign
AttrNest = webauthn2_handler_factory.AttrNest
Preauth = webauthn2_handler_factory.Preauth

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
log_template = "%(elapsed_s)d.%(elapsed_ms)3.3ds %(client_ip)s user=%(client_identity)s req=%(reqid)s"
log_trace_template = log_template + " -- %(tracedata)s"
log_final_template = log_template + " (%(status)s) %(method)s %(proto)s://%(host)s/%(uri)s %(range)s %(type)s"


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
    parts['tracedata'] = tracedata
    logger.info( (log_trace_template % parts).encode('utf-8') )


def request_init():
    """Initialize web.ctx with request-specific timers and state used by our REST API layer."""
    web.ctx.ermrest_request_guid = base64.b64encode( struct.pack('Q', random.getrandbits(64)) )
    web.ctx.ermrest_start_time = datetime.datetime.now(pytz.timezone('UTC'))
    web.ctx.ermrest_request_content_range = '-/-'
    web.ctx.ermrest_content_type = 'unknown'
    web.ctx.webauthn2_manager = webauthn2_manager
    web.ctx.webauthn2_context = webauthn2.Context() # set empty context for sanity
    web.ctx.ermrest_request_trace = request_trace
    web.ctx.ermrest_registry = registry
    web.ctx.ermrest_catalog_factory = catalog_factory
    web.ctx.ermrest_config = global_env

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


class Dispatcher (object):
    """Helper class to handle parser-based URL dispatch

       Normal web.py dispatch is via regular expressions on a decoded
       URL, but we use a hybrid method:

       1. handle top-level catalog APIs via web_urls dispatched
          through web.py, with a final catch-all handler...

       2. for sub-resources of a catalog, run an LALR(1) parser
          generated by python-ply to parse the undecoded sub-resource
          part of the URL, allowing more precise interpretation of
          encoded and unencoded URL characters for meta-syntax.

    """
    def prepareDispatch(self):
        """computes web dispatch from REQUEST_URI

           with the HTTP method of the request, e.g. GET, PUT...
        """
        request_init()
        uri = web.ctx.env['REQUEST_URI']
        
        try:
            return uri, url_parse_func(uri)
        except (LexicalError, ParseError), te:
            raise rest.BadRequest(str(te))
        except:
            et, ev, tb = sys.exc_info()
            web.debug('got exception "%s" during URI parse' % str(ev),
                      traceback.format_exception(et, ev, tb))
            raise

    def METHOD(self, methodname):
        ast = None
        try:
            try:
                uri, ast = self.prepareDispatch()

                if not hasattr(ast, methodname):
                    raise rest.NoMethod()

                astmethod = getattr(ast, methodname)
                result = astmethod(uri)
                if hasattr(result, 'next'):
                    # force any transaction deferred in iterator
                    try:
                        first = result.next()
                    except StopIteration:
                        return result
                    return itertools.chain([first], result)
                else:
                    return result
            except (rest.WebException, web.HTTPError), e:
                # exceptions signal normal REST response scenarios
                request_trace( str(e) )
                raise e
            except psycopg2.Error, e:
                request_trace( str(e) )
                et, ev, tb = sys.exc_info()
                web.debug('got exception "%s" during METHOD() dispatcher' % str(ev),
                          traceback.format_exception(et, ev, tb))
                # TODO: simplify postgres error text?
                raise rest.Conflict( str(e) )
            except Exception, e:
                et, ev, tb = sys.exc_info()
                request_trace( str(ev) )
                web.debug('got exception "%s"' % str(ev), traceback.format_exception(et, ev, tb))
                raise

        finally:
            # log after we force iterator, to flush any deferred transaction log messages
            request_final()
            if ast is not None:
                ast.final()

    def HEAD(self):
        return self.METHOD('HEAD')

    def GET(self):
        return self.METHOD('GET')
        
    def PUT(self):
        return self.METHOD('PUT')

    def DELETE(self):
        return self.METHOD('DELETE')

    def POST(self):
        return self.METHOD('POST')


def web_urls():
    """Builds and returns the web_urls for web.py.
    """
    urls = (
        # user authentication via webauthn2
        '/authn/session(/[^/]+)', UserSession,
        '/authn/session/?()', UserSession,
        '/authn/password(/[^/]+)', UserPassword,
        '/authn/password/?()', UserPassword,
    
        # user account management via webauthn2
        '/authn/user(/[^/]+)', UserManage,
        '/authn/user/?()', UserManage,
        '/authn/attribute(/[^/]+)', AttrManage,
        '/authn/attribute/?()', AttrManage,
        '/authn/user/([^/]+)/attribute(/[^/]+)', AttrAssign,
        '/authn/user/([^/]+)/attribute/?()', AttrAssign,
        '/authn/attribute/([^/]+)/implies(/[^/]+)', AttrNest,
        '/authn/attribute/([^/]+)/implies/?()', AttrNest,
        '/authn/preauth(/[^/]+)', Preauth,
        '/authn/preauth/?()', Preauth,

        # the catalog factory
        '/catalog/?', ast.Catalogs,
        
        # core parser-based REST dispatcher
        '(?s).*', Dispatcher
    )
    return tuple(urls)
