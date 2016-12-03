# 
# Copyright 2012-2016 University of Southern California
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
"""
General utilities for ERMREST.
"""

# Right now these are all DB related utilities. We should keep it that way.

__all__ = ['table_exists', 'schema_exists', 'sql_identifier', 'sql_literal', 'negotiated_content_type', 'urlquote', 'urlunquote']

import web
import urllib
import uuid
import base64
from webauthn2.util import urlquote, negotiated_content_type

def urlunquote(url):
    if type(url) not in [ str, unicode ]:
        url = str(url)
    text = urllib.unquote_plus(url)
    if type(text) == str:
        text = unicode(text, 'utf8')
    elif type(text) == unicode:
        pass
    else:
        raise TypeError('unexpected decode type %s in urlunquote()' % type(text))
    return text


def schema_exists(cur, schemaname):
    """Return True or False depending on whether schema exists in our 
       database.
       
       schemaname : the schema name
    """

    cur.execute("""
SELECT * FROM information_schema.schemata
WHERE schema_name = %(schema)s
"""
                       % dict(schema=sql_literal(schemaname))
                       )
    exists = cur.rowcount > 0
    return exists


def table_exists(cur, schemaname, tablename):
    """Return True or False depending on whether (schema.)tablename exists in 
       our database.
       
       
       schemaname : the schema name
       tablename : the table name
    """
    cur.execute("""
SELECT * FROM information_schema.tables
WHERE table_schema = %(schema)s
AND table_name = %(table)s
"""
                     % dict(schema=sql_literal(schemaname),
                            table=sql_literal(tablename))
                     )
    exists = cur.rowcount > 0
    return exists

def column_exists(cur, schemaname, tablename, columnname):
    cur.execute("""
SELECT * FROM information_schema.columns
WHERE table_schema = %(schema)s
  AND table_name = %(table)s
  AND column_name = %(column)s
""" % dict(
    schema=sql_literal(schemaname),
    table=sql_literal(tablename),
    column=sql_literal(columnname)
)
    )
    exists = cur.rowcount > 0
    return exists

def constraint_exists(cur, constraintname):
    cur.execute("SELECT * FROM pg_catalog.pg_constraint WHERE conname = %s" % sql_literal(constraintname))
    return cur.rowcount > 0

def view_exists(cur, schemaname, tablename):
    """Return True or False depending on whether (schema.)tablename view exists in our database."""

    cur.execute("""
SELECT True 
FROM pg_namespace nc, pg_class c
WHERE c.relnamespace = nc.oid 
  AND nc.nspname::text = %(schema)s
  AND c.relname::text = %(table)s
  AND c.relkind IN ('v'::"char", 'm'::"char") 
  AND NOT pg_is_other_temp_schema(nc.oid) 
  AND (pg_has_role(c.relowner, 'USAGE'::text) 
     OR has_table_privilege(c.oid, 'SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER'::text) 
     OR has_any_column_privilege(c.oid, 'SELECT, INSERT, UPDATE, REFERENCES'::text))
"""
                % dict(schema=sql_literal(schemaname),
                       table=sql_literal(tablename))
    )
    exists = cur.rowcount > 0
    return exists


def _string_wrap(s, escape=u'\\', protect=[]):
    try:
        s = s.replace(escape, escape + escape)
        for c in set(protect):
            s = s.replace(c, escape + c)
        return s
    except Exception, e:
        web.debug('_string_wrap', s, escape, protect, e)
        raise

def sql_identifier(s):
    # double " to protect from SQL
    return u'"%s"' % _string_wrap(s, u'"')

def sql_literal(v):
    if type(v) is list:
        return 'ARRAY[%s]' % (','.join(map(sql_literal, v)))
    elif v is not None:
        # double ' to protect from SQL
        s = '%s' % v
        return "'%s'" % _string_wrap(s, u"'")
    else:
        return 'NULL'

def random_name(prefix=''):
    """Generates and returns a random name in URL-safe base64 minus '=' padding.

       An optional prefix is prepended to the random bits.  The random
       bits are encoded using base64 so the suffix characters will be
       drawn from 'a'-'z', 'A'-'Z', '0'-'9', '-', and '_'.

    """
    # TODO: trim out uuid version 4 static bits?  Is 122 random bits overkill?
    return prefix + base64.urlsafe_b64encode(uuid.uuid4().bytes).replace('=','')

