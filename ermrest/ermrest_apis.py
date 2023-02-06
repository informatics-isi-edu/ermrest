
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

"""ERMREST REST API mapping layer

This sets up the flask app routes we support.

A few handlers can be directly routed by using flask route patterns
that parse the URL path and give us necessary parameters.

The majority are handled via our grammar-based URL parser, using a
proxy function that parses the full URL to instantiate a handler,
invokes the handler, and returns the response.


"""
import logging
from logging.handlers import SysLogHandler
import random
import base64
import datetime
import struct
import sys
import traceback
import psycopg2
import flask
import webauthn2
from webauthn2.util import deriva_ctx, deriva_debug

from .apicore import app
from .url import url_parse_func, ast

# simple routes which do not use our grammar-based URL parser
#

@app.route('/catalog', methods=['POST'])
@app.route('/catalog/', methods=['POST'])
def catalogs_dispatch():
    handler = ast.Catalogs()
    deriva_ctx.ermrest_dispatched_handler = handler
    return getattr(handler, flask.request.method.upper())()

@app.route('/alias', methods=['POST'])
@app.route('/alias/', methods=['POST'])
def aliases_dispatch():
    handler = ast.CatalogAliases()
    deriva_ctx.ermrest_dispatched_handler = handler
    return getattr(handler, flask.request.method.upper())()

@app.route('/alias/<string:catalog_id>', methods=['GET', 'PUT', 'DELETE'])
@app.route('/alias/<string:catalog_id>/', methods=['GET', 'PUT', 'DELETE'])
def alias_dispatch(catalog_id):
    handler = ast.CatalogAlias()
    deriva_ctx.ermrest_dispatched_handler = handler
    return getattr(handler, flask.request.method.upper())(catalog_id)

# complex routes which use our owwn URL parsing
#

@app.route('/', methods=['GET'])
@app.route('/catalog/<path:rest>', methods=['GET', 'PUT', 'DELETE', 'POST'])
def ermrest_parsed_request(*args, **kwargs):
    # our existing codebase from web.py app used the WSGI REQUEST_URI /ermrest/...
    uri = flask.request.environ['REQUEST_URI']
    ast = url_parse_func(uri)
    deriva_ctx.ermrest_dispatched_handler = ast
    return getattr(ast, flask.request.method.upper())(uri)

