
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

The parser proxy is decorated with many routes so that we can tell
flask which HTTP methods will be available on each route. These URL
patterns are approximations of the real URL syntax with enough detail
to distinguish different API nodes with different capabilities. But,
they do not try to capture all the real semantic structure of the URL
paths which is better handled by the real ermrest grammar.

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
# these route patterns are used to specify available methods
# so flask can provide OPTIONS or No Method responses
#
# but, we use our own parser to dispatch to real AST handlers
#

@app.route('/', methods=['GET'])
@app.route('/catalog/<cid>', methods=['GET', 'DELETE', 'POST'])
@app.route('/catalog/<cid>/', methods=['GET', 'DELETE', 'POST'])
@app.route('/catalog/<cid>/acl', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/acl/', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/acl/<name>', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/annotation', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/annotation/', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/annotation/<name>', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/history/<when>', methods=['GET', 'DELETE'])
@app.route('/catalog/<cid>/history/<when>/', methods=['GET', 'DELETE'])
@app.route('/catalog/<cid>/history/<when>/attribute/<path:rest>', methods=['GET', 'DELETE'])
@app.route('/catalog/<cid>/history/<when>/acl', methods=['GET', 'PUT'])
@app.route('/catalog/<cid>/history/<when>/acl/', methods=['GET', 'PUT'])
@app.route('/catalog/<cid>/history/<when>/acl/<rest>', methods=['GET', 'PUT'])
@app.route('/catalog/<cid>/history/<when>/acl_binding', methods=['GET', 'PUT'])
@app.route('/catalog/<cid>/history/<when>/acl_binding/', methods=['GET', 'PUT'])
@app.route('/catalog/<cid>/history/<when>/acl_binding/<rest>', methods=['GET', 'PUT'])
@app.route('/catalog/<cid>/history/<when>/annotation', methods=['GET', 'PUT'])
@app.route('/catalog/<cid>/history/<when>/annotation/', methods=['GET', 'PUT'])
@app.route('/catalog/<cid>/history/<when>/annotation/<rest>', methods=['GET', 'PUT'])
@app.route('/catalog/<cid>/entity', methods=['GET', 'PUT', 'POST', 'DELETE'])
@app.route('/catalog/<cid>/entity/', methods=['GET', 'PUT', 'POST', 'DELETE'])
@app.route('/catalog/<cid>/entity/<path:rest>', methods=['GET', 'PUT', 'POST', 'DELETE'])
@app.route('/catalog/<cid>/attribute', methods=['GET', 'DELETE'])
@app.route('/catalog/<cid>/attribute/', methods=['GET', 'DELETE'])
@app.route('/catalog/<cid>/attribute/<path:rest>', methods=['GET', 'DELETE'])
@app.route('/catalog/<cid>/attributegroup', methods=['GET', 'PUT'])
@app.route('/catalog/<cid>/attributegroup/', methods=['GET', 'PUT'])
@app.route('/catalog/<cid>/attributegroup/<path:rest>', methods=['GET', 'PUT'])
@app.route('/catalog/<cid>/aggregate', methods=['GET'])
@app.route('/catalog/<cid>/aggregate/', methods=['GET'])
@app.route('/catalog/<cid>/aggregate/<path:rest>', methods=['GET'])
@app.route('/catalog/<cid>/entity_rid/<rest>', methods=['GET'])
@app.route('/catalog/<cid>/textfacet/<rest>', methods=['GET'])
@app.route('/catalog/<cid>/schema', methods=['GET', 'POST'])
@app.route('/catalog/<cid>/schema/', methods=['GET', 'POST'])
@app.route('/catalog/<cid>/schema/<sname>', methods=['GET', 'PUT', 'POST', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/', methods=['GET', 'PUT', 'POST', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/acl', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/acl/', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/acl/<name>', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/annotation', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/annotation/', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/annotation/<name>', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/comment', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table', methods=['GET', 'POST'])
@app.route('/catalog/<cid>/schema/<sname>/table/', methods=['GET', 'POST'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/acl', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/acl/', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/acl/<name>', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/acl_binding', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/acl_binding/', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/acl_binding/<name>', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/annotation', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/annotation/', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/annotation/<name>', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/comment', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/column', methods=['GET', 'POST'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/column/', methods=['GET', 'POST'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/column/<cname>', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/column/<cname>/', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/column/<cname>/acl', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/column/<cname>/acl/', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/column/<cname>/acl/<name>', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/column/<cname>/acl_binding', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/column/<cname>/acl_binding/', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/column/<cname>/acl_binding/<name>', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/column/<cname>/annotation', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/column/<cname>/annotation/', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/column/<cname>/annotation/<name>', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/column/<cname>/comment', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/key', methods=['GET', 'POST'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/key/', methods=['GET', 'POST'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/key/<cnames>', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/key/<cnames>/', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/key/<cnames>/annotation', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/key/<cnames>/annotation/', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/key/<cnames>/annotation/<name>', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/key/<cnames>/comment', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/foreignkey', methods=['GET', 'POST'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/foreignkey/', methods=['GET', 'POST'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/foreignkey/<cnames>', methods=['GET'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/foreignkey/<cnames>/', methods=['GET'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/foreignkey/<cnames>/reference', methods=['GET'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/foreignkey/<cnames>/reference/', methods=['GET'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/foreignkey/<cnames>/reference/<tname2>', methods=['GET'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/foreignkey/<cnames>/reference/<tname2>/', methods=['GET'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/foreignkey/<cnames>/reference/<tname2>/<cnames2>', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/foreignkey/<cnames>/reference/<tname2>/<cnames2>/', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/foreignkey/<cnames>/reference/<tname2>/<cnames2>/acl', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/foreignkey/<cnames>/reference/<tname2>/<cnames2>/acl/', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/foreignkey/<cnames>/reference/<tname2>/<cnames2>/acl/<name>', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/foreignkey/<cnames>/reference/<tname2>/<cnames2>/acl_binding', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/foreignkey/<cnames>/reference/<tname2>/<cnames2>/acl_binding/', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/foreignkey/<cnames>/reference/<tname2>/<cnames2>/acl_binding/<name>', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/foreignkey/<cnames>/reference/<tname2>/<cnames2>/annotation', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/foreignkey/<cnames>/reference/<tname2>/<cnames2>/annotation/', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/foreignkey/<cnames>/reference/<tname2>/<cnames2>/annotation/<name>', methods=['GET', 'PUT', 'DELETE'])
@app.route('/catalog/<cid>/schema/<sname>/table/<tname>/foreignkey/<cnames>/reference/<tname2>/<cnames2>/comment', methods=['GET', 'PUT', 'DELETE'])
def ermrest_parsed_request(*args, **kwargs):
    # our existing codebase from web.py app used the WSGI REQUEST_URI /ermrest/...
    uri = flask.request.environ['REQUEST_URI']
    ast = url_parse_func(uri)
    deriva_ctx.ermrest_dispatched_handler = ast
    return getattr(ast, flask.request.method.upper())(uri)

