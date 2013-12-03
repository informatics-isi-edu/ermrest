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
"""
General utilities for ERMREST.
"""

# Right now these are all DB related utilities. We should keep it that way.

__all__ = ['table_exists', 'schema_exists', 'sql_identifier', 'sql_literal']

    
def schema_exists(dbc, schemaname):
    """Return True or False depending on whether schema exists in our 
       database.
       
       dbc : a database connection
       schemaname : the schema name
    """

    cur = dbc.cursor()
    cur.execute("""
SELECT * FROM information_schema.schemata
WHERE schema_name = %(schema)s
"""
                       % dict(schema=sql_literal(schemaname))
                       )
    exists = cur.rowcount > 0
    cur.close()
    return exists


def table_exists(dbc, schemaname, tablename):
    """Return True or False depending on whether (schema.)tablename exists in 
       our database.
       
       dbc : a database connection
       schemaname : the schema name
       tablename : the table name
    """
    
    cur = dbc.cursor()
    cur.execute("""
SELECT * FROM information_schema.tables
WHERE table_schema = %(schema)s
AND table_name = %(table)s
"""
                     % dict(schema=sql_literal(schemaname),
                            table=sql_literal(tablename))
                     )
    exists = cur.rowcount > 0
    cur.close()
    return exists


def _string_wrap(s, escape='\\', protect=[]):
    s = s.replace(escape, escape + escape)
    for c in set(protect):
        s = s.replace(c, escape + c)
    return s


def sql_identifier(s):
    # double " to protect from SQL
    # double % to protect from web.db
    return '"%s"' % _string_wrap(_string_wrap(s, '%'), '"') 


def sql_literal(v):
    if v != None:
        # double ' to protect from SQL
        # double % to protect from web.db
        s = '%s' % v
        return "'%s'" % _string_wrap(_string_wrap(s, '%'), "'")
    else:
        return 'NULL'