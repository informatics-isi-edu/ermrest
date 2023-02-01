
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
        start_time=web.ctx.ermrest_start_time,
        req=web.ctx.ermrest_requiest_guid,
        client=web.ctx.ip,
        webauthn2_context=web.ctx.webauthn2_context,
    ))

def request_init():
    """Initialize web.ctx with request-specific timers and state used by our REST API layer."""
    web.ctx.ermrest_request_guid = random_name()
    web.ctx.ermrest_start_time = datetime.datetime.now(timezone.utc)
    web.ctx.ermrest_request_content_range = None
    web.ctx.ermrest_content_type = None
    web.ctx.webauthn2_manager = webauthn2_manager
    web.ctx.webauthn2_context = webauthn2.Context() # set empty context for sanity
    web.ctx.ermrest_history_snaptime = None # for coherent historical snapshot queries
    web.ctx.ermrest_history_snaprange = None # for longitudinal history manipulation
    web.ctx.ermrest_history_amendver = None # for ETag versioning of historical results
    web.ctx.ermrest_request_trace = request_trace
    web.ctx.ermrest_registry = registry
    web.ctx.ermrest_catalog_factory = catalog_factory
    web.ctx.ermrest_catalog_model = None
    web.ctx.ermrest_config = global_env
    web.ctx.ermrest_catalog_pc = None
    web.ctx.ermrest_change_notify = amqp_notifier.notify if amqp_notifier else lambda : None
    web.ctx.ermrest_model_rights_cache = dict()

    # get client authentication context
    web.ctx.webauthn2_context = context_from_environment(web.ctx.env, fallback=True)
    web.ctx.ermrest_client_roles = set([
        r['id'] if type(r) is dict else r
        for r in web.ctx.webauthn2_context.attributes
    ]).union({'*'})

def request_final():
    """Log final request handler state to finalize a request's audit trail."""
    if web.ctx.ermrest_catalog_pc is not None:
        if web.ctx.ermrest_catalog_pc.conn is not None:
            web.ctx.ermrest_request_trace(
                'ERMrest DB conn LEAK averted in request_final()!?'
            )
            web.ctx.ermrest_catalog_pc.final()

    extra = {}
    if web.ctx.ermrest_history_snaptime:
        extra['snaptime'] = str(web.ctx.ermrest_history_snaptime)
    if web.ctx.ermrest_history_snaprange:
        extra['snaprange'] = [ str(ts) if ts else None for ts in web.ctx.ermrest_history_snaprange ]

    logger.info(format_final_json(
        environ=web.ctx.env,
        webauthn2_context=web.ctx.webauthn2_context,
        req=web.ctx.ermrest_request_guid,
        start_time=web.ctx.ermrest_start_time,
        client=web.ctx.ip,
        status=web.ctx.status,
        content_range=web.ctx.ermrest_request_content_range,
        content_type=web.ctx.ermrest_content_type,
        track=(web.ctx.webauthn2_context.tracking if web.ctx.webauthn2_context else None),
        **extra,
    ))

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
                        if hasattr(result, '__next__'):
                            # force any transaction deferred in iterator
                            for res in result:
                                yield res
                        else:
                            yield result
                    except psycopg2.ProgrammingError as e:
                        if e.pgcode == '42501':
                            # insufficient_privilege ... HACK: add " and is" to combine into Forbidden() template
                            raise rest.Forbidden(e.pgerror.replace('ERROR:  ','').replace('\n','') + ' and is')
                        elif e.pgcode == '42601':
                            # SQL syntax error means we have buggy code!
                            web.debug(e.pgcode, e.pgerror)
                            raise rest.RuntimeError('Query generation error, contact ERMrest administrator')
                        else:
                            # re-raise and let outer handlers below do something more generic
                            raise
                except (rest.WebException, web.HTTPError) as e:
                    # exceptions signal normal REST response scenarios
                    raise e
                except (ConflictModel, ConflictData) as e:
                    raise rest.Conflict(e.message)
                except Forbidden as e:
                    raise rest.Forbidden(e.message)
                except NotFound as e:
                    raise rest.NotFound(e.message)
                except BadData as e:
                    raise rest.BadRequest(e.message)
                except UnsupportedMediaType as e:
                    raise rest.UnsupportedMediaType(e.message)
                except psycopg2.Error as e:
                    request_trace(u"Postgres error: %s (%s)" % ((e.pgerror if e.pgerror is not None else 'None'), e.pgcode))
                    if e.pgcode is not None:
                        if e.pgcode[0:2] == '08':
                            raise rest.ServiceUnavailable('Database connection error.')
                        elif e.pgcode[0:2] == '53':
                            raise rest.ServiceUnavailable('Resources unavailable.')
                        elif e.pgcode[0:2] == '40':
                            raise rest.ServiceUnavailable('Transaction aborted.')
                        elif e.pgcode[0:2] == '54':
                            raise rest.BadRequest(str(e))
                        elif e.pgcode[0:2] == 'XX':
                            raise rest.ServiceUnavailable('Internal error.')
                        elif e.pgcode == '57014':
                            raise rest.BadRequest('Query run time limit exceeded.')
                        elif e.pgcode[0:2] == '23':
                            raise rest.Conflict(str(e))

                    # TODO: simplify postgres error text?
                    web.debug(e, e.pgcode, e.pgerror)
                    et, ev, tb = sys.exc_info()
                    web.debug('got psycopg2 exception "%s"' % str(ev))
                    raise rest.Conflict( str(e) )
                except (psycopg2.pool.PoolError, psycopg2.OperationalError) as e:
                    raise rest.ServiceUnavailable(e.message)
                except Exception as e:
                    et, ev, tb = sys.exc_info()
                    web.debug('got unrecognized %s exception "%s"' % (type(ev), str(ev)), traceback.format_exception(et, ev, tb))
                    raise
            finally:
                request_final()
        return wrapper
    return helper
