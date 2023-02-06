
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

"""Core ERMrest API configuration and context.

   These are split out from ermrest_api dispatching module to avoid
   circular dependencies.

"""

import threading
import logging
from logging.handlers import SysLogHandler
import web
import datetime
from datetime import timezone
import struct
import json
import sys
import traceback
import psycopg2
import webauthn2
from webauthn2.util import context_from_environment
from webauthn2.rest import format_trace_json, format_final_json
from collections import OrderedDict

from .exception import *

from .registry import get_registry
from .catalog import get_catalog_factory
from .util import negotiated_content_type, urlquote, random_name

__all__ = [
    'web_urls',
    'webauthn2_manager',
    'global_env'
    ]

## flask app we will configure for our service
app = flask.Flask('ermrest')

def raw_path_app(app_orig, raw_uri_env_key='REQUEST_URI'):
    """Allow routes to distinguish raw reserved chars from escaped ones.
    :param app_orig: The WSGI app to wrap with middleware.
    :param raw_path_env_key: The key to lookup the raw request URI in the WSGI environment.
    """
    def app(environ, start_response):
        parts = urllib.parse.urlparse(environ[raw_uri_env_key])
        path_info = parts.path
        script_name = environ['SCRIPT_NAME']
        if path_info.startswith(script_name):
            path_info = path_info[len(script_name):]
        if parts.params:
            path_info = '%s;%s' % (path_info, parts.params)
        environ['PATH_INFO'] = path_info
        return app_orig(environ, start_response)
    return app

app.wsgi_app = raw_path_app(app.wsgi_app)

## setup web service configuration data
global_env = webauthn2.merge_config(
    jsonFileName='ermrest_config.json', 
    built_ins={
        "request_timeout_s": 15.0,
        # TODO: are these used?
        # "default_limit": 100,
        # "db": "ermrest", 
        # "dbn": "postgres", 
        # "dbmaxconnections": 8
        }
    )

# setup webauthn2 handler
webauthn2_manager = webauthn2.Manager()

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

# setup AMQP notices path
try:
    import pika

    class AmqpChangeNotifier (object):
        def __init__(self, config):
            self._config = config
            self._lock = threading.Lock()
            if self._config.get('host') is None:
                self._config['host'] = 'localhost'
            connection = self._config.get('connection')
            if isinstance(connection, str):
                self._connection_config = pika.URLParameters(connection)
            elif isinstance(connection, dict):
                self._connection_config = pika.ConnectionParameters(**connection)
            else:
                self._connection_config = pika.ConnectionParameters(host=self._config['host'])
            self._exchange_name = config['exchange']
            self._routing_key = config['routing_key']
            self._connection = None
            self._channel = None
            self._pika_init()
            
        def _pika_init(self):
            connection = pika.BlockingConnection(self._connection_config)
            channel = connection.channel()
            channel.exchange_declare(exchange=self._exchange_name, exchange_type="fanout")
            self._connection = connection
            self._channel = channel

        def _pika_publish(self):
            self._channel.basic_publish(
                exchange=self._exchange_name,
                routing_key=self._routing_key,
                body='change'
            )
        
        def notify(self):
            try:
                self._lock.acquire()
                try:
                    if self._connection is None:
                        self._pika_init()
                    self._pika_publish()
                except pika.exceptions.AMQPError as e:
                    # retry once more on errors?
                    try:
                        self._connection.close()
                    except:
                        pass
                    try:
                        self._pika_init()
                        self._pika_publish()
                    except:
                        pass
            finally:
                try:
                    self._lock.release()
                except:
                    pass

    conf = global_env.get('change_notification', {}).get('AMQP')
    amqp_notifier = AmqpChangeNotifier(conf) if conf else None
except:
    et, ev, tb = sys.exc_info()
    logger.info( ('Change notification via AMQP disabled due to initialization error: %s\n%s' % (
        str(ev),
        traceback.format_exception(et, ev, tb)
    )).encode('utf-8') )
    amqp_notifier = None

def request_trace(tracedata):
    """Log one tracedata event as part of a request's audit trail.

       tracedata: a string representation of trace event data
    """
    logger.info(format_trace_json(
        tracedata,
        start_time=deriva_ctx.ermrest_start_time,
        req=deriva_ctx.ermrest_request_guid,
        client=flask.request.remote_addr,
        webauthn2_context=deriva_ctx.webauthn2_context,
    ))

@app.before_request
def request_init():
    """Initialize deriva_ctx with request-specific timers and state used by our REST API layer."""
    deriva_ctx.deriva_response = flask.Response()
    deriva_ctx.ermrest_dispatched_handler = None
    deriva_ctx.ermrest_request_guid = random_name()
    deriva_ctx.ermrest_start_time = datetime.datetime.now(timezone.utc)
    deriva_ctx.ermrest_request_content_range = None
    deriva_ctx.ermrest_content_type = None
    deriva_ctx.ermrest_status = None
    deriva_ctx.webauthn2_manager = webauthn2_manager
    deriva_ctx.webauthn2_context = webauthn2.Context() # set empty context for sanity
    deriva_ctx.ermrest_history_snaptime = None # for coherent historical snapshot queries
    deriva_ctx.ermrest_history_snaprange = None # for longitudinal history manipulation
    deriva_ctx.ermrest_history_amendver = None # for ETag versioning of historical results
    deriva_ctx.ermrest_request_trace = request_trace
    deriva_ctx.ermrest_registry = registry
    deriva_ctx.ermrest_catalog_factory = catalog_factory
    deriva_ctx.ermrest_catalog_model = None
    deriva_ctx.ermrest_config = global_env
    deriva_ctx.ermrest_catalog_pc = None
    deriva_ctx.ermrest_change_notify = amqp_notifier.notify if amqp_notifier else lambda : None
    deriva_ctx.ermrest_model_rights_cache = dict()

    # get client authentication context
    deriva_ctx.webauthn2_context = context_from_environment(flask.request.environ, fallback=True)
    deriva_ctx.ermrest_client_roles = set([
        r['id'] if type(r) is dict else r
        for r in deriva_ctx.webauthn2_context.attributes
    ]).union({'*'})

def _teardown():
    if deriva_ctx.ermrest_dispatched_handler is not None:
        if hasattr(deriva_ctx.ermrest_dispatched_handler, 'final'):
            deriva_ctx.ermrest_dispatched_handler.final()
    if deriva_ctx.ermrest_catalog_pc is not None:
        if deriva_ctx.ermrest_catalog_pc.conn is not None:
            deriva_ctx.ermrest_request_trace('ERMrest DB conn LEAK averted in request_final()!?')
            deriva_ctx.ermrest_catalog_pc.final()

@app.after_request
def request_final(response):
    """Log final request handler state to finalize a request's audit trail."""

    if not hasattr(response.response, 'seek'):
        # force lingering response generator, unless it is a seekable file/buffer
        response.make_sequence()

    if flask.request.method in {'PUT', 'POST', 'DELETE'} \
       and response.status_code in {200, 201, 204}:
        deriva_ctx.ermrest_change_notify()

    _teardown()

    extra = {}
    if deriva_ctx.ermrest_history_snaptime:
        extra['snaptime'] = str(deriva_ctx.ermrest_history_snaptime)
    if deriva_ctx.ermrest_history_snaprange:
        extra['snaprange'] = [ str(ts) if ts else None for ts in deriva_ctx.ermrest_history_snaprange ]

    if isinstance(response, flask.Response):
        deriva_ctx.ermrest_status = response.status
    elif isinstance(response, RestException):
        deriva_ctx.ermrest_status = response.code

    deriva_ctx.ermrest_content_type = response.headers.get('content-type', 'none')
    if 'content-range' in response.headers:
        content_range = response.headers['content-range']
        if content_range.startswith('bytes '):
            content_range = content_range[6:]
        deriva_ctx.ermrest_request_content_range = content_range
    elif 'content-length' in response.headers:
        deriva_ctx.ermrest_request_content_range = '*/%s' % response.headers['content-length']
    else:
        deriva_ctx.ermrest_request_content_range = '*/0'

    logger.info(format_final_json(
        environ=flask.request.environ,
        webauthn2_context=deriva_ctx.webauthn2_context,
        req=deriva_ctx.ermrest_request_guid,
        start_time=deriva_ctx.ermrest_start_time,
        client=flask.request.remote_addr,
        status=deriva_ctx.ermrest_status,
        content_range=deriva_ctx.ermrest_request_content_range,
        content_type=deriva_ctx.ermrest_content_type,
        track=(deriva_ctx.webauthn2_context.tracking if deriva_ctx.webauthn2_context else None),
        **extra,
    ))

    return response

@app.errorhandler(Exception)
def error_handler(ev):
    _teardown()
    if isinstance(ev, werkzeug.exceptions.HTTPException) \
       and not isinstance(ev, rest.RestException):
        deriva_debug(str(ev), flask.request.path, flask.request.environ['REQUEST_URI'])

    if isinstance(ev, psycopg2.Error):
        request_trace(u"Postgres error: %s (%s)" % (ev.pgerror, ev.pgcode))

        if ev.pgcode is not None:
            if ev.pgcode == '42501':
                # insufficient_privilege ... HACK: add " and is" to combine into Forbidden() template
                ev = rest.Forbidden(ev.pgerror.replace('ERROR:  ','').replace('\n','') + ' and is')
            elif ev.pgcode == '42601':
                # SQL syntax error means we have buggy code, so let it convert into 500 error!
                pass
            elif ev.pgcode == '57014':
                ev = rest.BadRequest('Query run time limit exceeded.')
            elif ev.pgcode[0:2] == '08':
                ev = rest.ServiceUnavailable('Database connection error.')
            elif ev.pgcode[0:2] == '23':
                ev = rest.Conflict(str(ev))
            elif ev.pgcode[0:2] == '40':
                ev = rest.ServiceUnavailable('Transaction aborted.')
            elif ev.pgcode[0:2] == '53':
                ev = rest.ServiceUnavailable('Resources unavailable.')
            elif ev.pgcode[0:2] == '54':
                ev = rest.BadRequest(str(ev))
            elif ev.pgcode[0:2] == 'XX':
                ev = rest.ServiceUnavailable('Internal error.')
            else:
                deriva_debug('unrecognized psycopg2 exception', str(ev), ev.pgcode, ev.pgerror)
                et, ev2, tb = sys.exc_info()
                deriva_debug(traceback.format_exception(et, ev2, tb))
                ev = rest.Conflict( str(ev) )

        if isinstance(ev, psycopg2.OperationalError):
            ev = rest.ServiceUnavailable(str(ev))

    elif isinstance(ev, (LexicalError, ParseError)):
        ev = rest.BadRequest(str(ev))
    elif isinstance(ev, (ConflictModel, ConflictData)):
        ev = rest.Conflict(ev.message)
    elif isinstance(ev, Forbidden):
        ev = rest.Forbidden(ev.message)
    elif isinstance(ev, NotFound):
        ev = rest.NotFound(ev.message)
    elif isinstance(ev, BadData):
        ev = rest.BadRequest(ev.message)
    elif isinstance(ev, UnsupportedMediaType):
        ev = rest.UnsupportedMediaType(ev.message)
    elif isinstance(ev, werkzeug.exceptions.MethodNotAllowed):
        ev = rest.NoMethod()

    if not isinstance(ev, (rest.RestException, werkzeug.exceptions.HTTPException)):
        request_trace('Unhandled exception: %s (%s)' % (type(ev), str(ev)))
        et, ev2, tb = sys.exc_info()
        deriva_debug('got unhandled exception', type(ev), str(ev))
        deriva_debug(''.join(traceback.format_exception(et, ev2, tb)))
        ev = rest.RuntimeError(str(ev))

    return ev

