
# 
# Copyright 2013 University of Southern California
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

"""ERMREST data path support

The data path is the core ERM-aware mechanism for searching,
navigating, and manipulating data in an ERMREST catalog.

"""
import psycopg2
import urllib
import csv
import web

from util import sql_identifier, sql_literal
from model import Type
from ermrest.exception import *
from ermrest.catalog import _random_name

def make_row_thunk(conn, cur, content_type, drop_tables=[], ):
    def row_thunk():
        """Allow caller to lazily expand cursor after commit.

           If conn is not None, call conn.commit() after fetching
           results to avoid leaving it idle in transaction due to the
           cursor fetch commands.

        """
        
        if content_type == 'text/csv':
            hdr = True
            for row in cur:
                if hdr:
                    # need to defer accessing cur.description until after fetching 1st row
                    yield row_to_csv([ col[0] for col in cur.description ]) + '\n'
                    hdr = False
                yield row_to_csv(row) + '\n'

        elif content_type in [ 'application/json', 'application/x-json-stream' ]:
            for row in cur:
                yield row[0] + '\n'

        elif content_type is tuple:
            for row in cur:
                yield row

        elif content_type is dict:
            for row in cur:
                yield row_to_dict(cur, row)

        for table in drop_tables:
            cur.execute("DROP TABLE %s" % sql_identifier(table))

        cur.close()

        #if conn is not None:
        #    conn.commit()
        
    return row_thunk

def notify_data_change(cur, table):
    """Update data version information after possible change to table.

       Conservatively updates version for any dependent tables too.
    """
    tables = set()

    def expand_table(t1):
        if t1 in tables:
            # don't re-expand tables in event of a cyclic foreign key pattern (weird but possible in SQL)
            return
        tables.add(t1)
        for unique in t1.uniques.values():
            for ftable in unique.table_references:
                expand_table(ftable)

    expand_table(table)

    for table in tables:
        cur.execute('SELECT _ermrest.data_change_event(%s, %s)' % (sql_literal(table.schema.name), sql_literal(table.name)))


class EntityElem (object):
    """Wrapper for instance of entity table in path.

    """
    def __init__(self, epath, alias, table, pos, keyref=None, refop=None, keyref_alias=None, context_pos=None):
        self.epath = epath
        self.alias = alias
        self.table = table
        self.pos = pos
        if context_pos is None:
            context_pos = pos - 1
        self.context_pos = context_pos
        self.keyref = keyref
        self.refop = refop
        self.keyref_alias = keyref_alias
        self.filters = []

    def _link_parts(self):
        fkcols = [ c.name for c in self.keyref.foreign_key.columns ]
        pkcols = [ c.name for c in self.keyref.unique.columns ]

        if self.refop == '=@':
            # left to right reference
            ltable = self.keyref.foreign_key.table
            lcnames, rcnames = fkcols, pkcols
            refop = 'refs'
        else:
            # right to left reference
            ltable = self.keyref.unique.table
            lcnames, rcnames = pkcols, fkcols
            refop = 'refby'

        return ltable, lcnames, rcnames, refop

    def __str__(self):
        s = str(self.table)

        if self.alias:
            s += ' AS %s' % self.alias

        if self.keyref:
            ltable, lcnames, rcnames, refop = self._link_parts()
        
            if self.keyref_alias:
                ltname = self.keyref_alias
            else:
                ltname = '..'

            lcols = ltname + ':' + ','.join(lcnames)
            rcols = '.' + ':' + ','.join(rcnames)

            s += ' ON (%s %s %s)' % (lcols, refop, rcols)

        if self.filters:
            s += ' WHERE ' + ' AND '.join([ str(f) for f in self.filters ])

        return s

    def __repr__(self):
        return '<ermrest.ermpath.EntityElem %s>' % str(self)

    def add_filter(self, filt):
        """Add a filtersql_name condition to this path element.
        """
        filt.validate(self.epath)
        self.filters.append(filt)

    def sql_join_condition(self):
        """Generate SQL condition for joining this element to the epath.

        """
        if not self.keyref:
            raise NotImplementedError('self.keyref')

        ltable, lcnames, rcnames, refop = self._link_parts()

        if self.keyref_alias:
            ltnum = self.epath.aliases[self.keyref_alias]
        else:
            ltnum = self.context_pos
        
        return ' AND '.join([
                't%d.%s = t%d.%s' % (
                    ltnum, 
                    sql_identifier(lcnames[i]),
                    self.pos, 
                    sql_identifier(rcnames[i])
                    )
                for i in range(0, len(lcnames))
                ])

    def sql_wheres(self):
        """Generate SQL row conditions for filtering this element in the epath.
           
        """
        return [ f.sql_where(self.epath, self) for f in self.filters ]

    def sql_table_elem(self):
        """Generate SQL table element representing this entity as part of the epath JOIN.

        """
        if self.pos == 0:
            return '%s AS t0' % self.table.sql_name()

        else:
            return '%s AS t%d ON (%s)' % (
                self.table.sql_name(),
                self.pos,
                self.sql_join_condition()
                )
    
    def put(self, conn, cur, input_data, in_content_type='text/csv', content_type='text/csv', output_file=None, allow_existing=True, allow_missing=True, attr_update=None, use_defaults=None, attr_aliases=None):
        """Put or update entities depending on allow_existing, allow_missing modes.

           conn: sanepg2 connection to catalog

           input_data:
              x with x.read() --> data will be read
              iterable --> data will be iterated

           in_content_type:
              text names of MIME types control deserialization:
                'text/csv' --> CSV table
                'application/json' --> JSON array of objects
                'application/x-json-stream' --> stream of JSON objects

                for MIME types, iterable input will be concatenated to
                form input byte stream, or read() will be called to
                fetch byte stream until an empty read() result is
                received.
 
              None means input is Python data stream (iter only)
                dicts will be seen as column: value, ... rows
                tuples will be seen as value, ... rows
                other types are erroneous

                for Python data streams, iterable input must yield one
                row respresentation at a time.  read() is not
                supported for Python data streams.

                for tuples, values must be ordered according to column
                ordering in the catalog model.

           content_type and output_file: see documentation for
              identical feature in get() method of this class. The
              result being controlled is a representation of each
              inserted or modified row, including any default values
              which might have been absent from the input.

           allow_existing: when input rows match existing keys
              True --> update existing row with input (default)
              None --> skip input row
              False --> raise exception

           allow_missing: when input rows do not match existing keys
              True --> insert input rows (default)
              None --> skip input row
              False --> raise exception

           attr_update: customized entity processing
              mkcols, nmkcols --> use specified metakey and non-metakey columns
              None --> use entity metakey and non-metakey columns

           use_defaults: customize entity processing
              { col, ... } --> use defaults
              None --> use input values

           Input rows are correlated to stored entities by metakey
           equivalence.  The metakey for an entity is the union of all
           its unique keys.  The metakey for a custom update may be a
           subset of columns and may in fact be a non-unique key.

           Input row data is applied to existing entities by updating
           the non-metakey columns to match the input.  Input row data
           is used to insert new entities only when allow_missing is
           False and attr_update is None.

        """
        if len(self.filters) > 0:
            raise BadSyntax('Entity filters not allowed during entity PUT.')

        if not self.table.writable_kind():
            raise ConflictModel('Entity %s is not writable.' % self.table)
        
        input_table = _random_name("input_data_")
        input_json_table = _random_name("input_json_")

        drop_tables = []

        if attr_update is not None:
            # caller has configured an attribute update request
            # input table has key columns followed by non-key columns
            mkcols, nmkcols = attr_update
            if attr_aliases is not None:
                mkcol_aliases, nmkcol_aliases = attr_aliases
            else:
                mkcol_aliases = dict()
                nmkcol_aliases = dict()
        else:
            # we are doing a whole entity request
            # input table has columns in same order as entity table
            inputcols = self.table.columns_in_order()
            mkcols = set()
            for unique in self.table.uniques:
                for c in unique:
                    mkcols.add(c)
            nmkcols = [ c for c in inputcols if c not in mkcols ]
            mkcols = [ c for c in inputcols if c in mkcols ]
            mkcol_aliases = dict()
            nmkcol_aliases = dict()

        if len(mkcols) == 0:
            raise ConflictModel('PUT not supported on entities without key constraints.')
        
        skip_key_tests = False

        if use_defaults is not None:
            if use_defaults.intersection( set([ c.name for c in mkcols ]) ):
                # default values for one or more key columns have been requested
                # input rows cannot be tested for key uniqueness except by trying to insert!
                skip_key_tests = True

            # ignore non-key input columns where defaults are to be used
            nmkcols = [ c for c in nmkcols if c.name not in use_defaults ]

        # create temporary table
        cur.execute(
            "CREATE TEMPORARY TABLE %s (%s)" % (
                sql_identifier(input_table),
                ','.join([ c.ddl(mkcol_aliases.get(c)) for c in mkcols ] 
                         + [ c.ddl(nmkcol_aliases.get(c)) for c in nmkcols ] )
                )
            )
        drop_tables.append( input_table )
        if in_content_type in [ 'application/x-json-stream' ]:
            cur.execute( "CREATE TEMPORARY TABLE %s (j json)" % sql_identifier(input_json_table))
            drop_tables.append( input_json_table )
        
        # copy input data to temp table
        if in_content_type == 'text/csv':
            hdr = csv.reader([ input_data.readline() ]).next()

            inputcol_names = set(
                [ str(mkcol_aliases.get(c, c.name)) for c in mkcols ]
                + [ str(mkcol_aliases.get(c, c.name)) for c in nmkcols ]
                )
            csvcol_names = set()
            csvcol_names_ordered = []
            for cn in hdr:
                try:
                    inputcol_names.remove(cn)
                    csvcol_names.add(cn)
                    csvcol_names_ordered.append(cn)
                except KeyError:
                    if cn in csvcol_names:
                        raise BadData('CSV column %s appears more than once.' % cn)
                    else:
                        raise BadData('CSV column %s not recognized.' % cn)

            if len(inputcol_names) > 0:
                raise BadData('CSV input missing required columns: %s' 
                              % ', '.join([ '"%s"' % cn for cn in inputcol_names ]))

            try:
                cur.copy_expert(
                """
COPY %s (%s) 
FROM STDIN WITH (
    FORMAT csv, 
    HEADER false, 
    DELIMITER ',', 
    QUOTE '"'
)""" % (sql_identifier(input_table),
        ','.join([ sql_identifier(cn) for cn in csvcol_names_ordered ])
        ),
                input_data
                )
            except psycopg2.DataError, e:
                raise BadData('Bad CSV input. ' + e.pgerror)

        elif in_content_type == 'application/json':
            buf = input_data.read()
            try:
                cur.execute( 
                """
INSERT INTO %(input_table)s (%(cols)s)
SELECT %(cols)s 
FROM (
  SELECT (rs.r).*
  FROM (
    SELECT json_populate_recordset( NULL::%(input_table)s, %(input)s::json ) AS r
  ) rs
) s
""" % dict( 
                        input_table = sql_identifier(input_table),
                        cols = ','.join(
                            [ c.sql_name(mkcol_aliases.get(c)) for c in mkcols ]
                            + [ c.sql_name(nmkcol_aliases.get(c)) for c in nmkcols ]
                            ),
                        input = Type('text').sql_literal(buf)
                        )
                )
            except psycopg2.DataError, e:
                raise BadData('Bad JSON array input. ' + e.pgerror)

        elif in_content_type == 'application/x-json-stream':
            try:
                cur.copy_expert( "COPY %s (j) FROM STDIN" % sql_identifier(input_json_table), input_data )

                cur.execute(
                """
INSERT INTO %(input_table)s (%(cols)s)
SELECT %(cols)s
FROM (
  SELECT (rs.r).*
  FROM (
    SELECT json_populate_record( NULL::%(input_table)s, i.j ) AS r
    FROM %(input_json)s i
  ) rs
) s
""" % dict(
                        input_table = sql_identifier(input_table),
                        input_json = sql_identifier(input_json_table),
                        cols = ','.join(
                            [ c.sql_name(mkcol_aliases.get(c)) for c in mkcols ]
                            + [ c.sql_name(nmkcol_aliases.get(c)) for c in nmkcols ]
                            )
                        )
                )
            except psycopg2.DataError, e:
                raise BadData('Bad JSON stream input. ' + e.pgerror)

        else:
            raise UnsupportedMediaType('%s input not supported' % in_content_type)

        #  -- check for duplicate keys
        if not skip_key_tests:
            cur.execute("SELECT count(*) FROM %s" % sql_identifier(input_table))
            total_rows = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM (SELECT DISTINCT %s FROM %s) s" % (
                    ','.join([ c.sql_name(mkcol_aliases.get(c)) for c in mkcols]),
                    sql_identifier(input_table))
                        )
            total_mkeys = cur.fetchone()[0]
            if total_rows > total_mkeys:
                raise ConflictData('Multiple input rows share the same unique key information.')

        correlating_sql = [
            "SELECT %(inmkcols)s FROM %(input_table)s",
            "SELECT %(mkcols)s FROM %(table)s"
            ]
        correlating_sql = tuple([
            sql % dict(table = self.table.sql_name(), 
                       inmkcols = ','.join(
                        [ c.sql_name(mkcol_aliases.get(c)) for c in mkcols ]
                        ),
                       mkcols = ','.join([ c.sql_name() for c in mkcols ]),
                       input_table = sql_identifier(input_table))
            for sql in correlating_sql
            ])
        
        update_sql = """
UPDATE %(table)s AS t SET %(assigns)s
FROM %(input_table)s AS i
WHERE %(keymatches)s 
  AND (%(valnonmatches)s)
RETURNING %(tcols)s
""" % dict(
            table = self.table.sql_name(),
            input_table = sql_identifier(input_table),
            assigns = ','.join([ "%s = i.%s " % ( c.sql_name(), c.sql_name(nmkcol_aliases.get(c)) ) for c in nmkcols ]),
            keymatches = ' AND '.join([ "t.%s IS NOT DISTINCT FROM i.%s" % (c.sql_name(), c.sql_name(mkcol_aliases.get(c))) for c in mkcols ]),
            valnonmatches = ' OR '.join([ "t.%s IS DISTINCT FROM i.%s" % (c.sql_name(), c.sql_name(nmkcol_aliases.get(c))) for c in nmkcols ]),
            tcols = ','.join(
        [ 'i.%s AS %s' % (c.sql_name(mkcol_aliases.get(c)), c.sql_name(mkcol_aliases.get(c))) for c in mkcols ]
        + [ 't.%s AS %s' % (c.sql_name(), c.sql_name(nmkcol_aliases.get(c))) for c in nmkcols ]
        )
            )

	# NOTE: insert only happens for /entity/ API which does not support column aliases
	if skip_key_tests:
            insert_sql = """
INSERT INTO %(table)s (%(cols)s)
SELECT %(icols)s
FROM %(input_table)s
RETURNING *
""" % dict(
                table = self.table.sql_name(),
                input_table = sql_identifier(input_table),
                cols = ','.join([ c.sql_name() for c in (mkcols + nmkcols) if c.name not in use_defaults ]),
                icols = ','.join([ c.sql_name() for c in (mkcols + nmkcols) if c.name not in use_defaults ])
                )
        else:
            insert_sql = """
INSERT INTO %(table)s (%(cols)s)
SELECT %(icols)s
FROM (
  SELECT %(mkcols)s FROM %(input_table)s
  EXCEPT
  SELECT %(mkcols)s FROM %(table)s
) k
JOIN %(input_table)s AS i ON (%(keymatches)s)
RETURNING *
""" % dict(
                table = self.table.sql_name(),
                input_table = sql_identifier(input_table),
                cols = ','.join([ c.sql_name() for c in (mkcols + nmkcols) ]),
                icols = ','.join([ 'i.%s' % c.sql_name() for c in (mkcols + nmkcols) ]),
                mkcols = ','.join([ c.sql_name() for c in mkcols ]),
                keymatches = ' AND '.join([ "k.%s IS NOT DISTINCT FROM i.%s" % (c.sql_name(), c.sql_name()) for c in mkcols ])
                )
        
        updated_sql = "SELECT * FROM updated_rows"
        inserted_sql = "SELECT * FROM inserted_rows"
        upsert_sql = "WITH %s %s"
        
        # generate rows to caller
        if content_type == 'text/csv':
            # TODO implement and use row_to_csv() stored procedure?
            pass
        elif content_type == 'application/json':
            upsert_sql = "WITH %s SELECT COALESCE(array_to_json(array_agg(row_to_json(q)), True)::text, '[]') FROM (%s) q"
        elif content_type == 'application/x-json-stream':
            upsert_sql = "WITH %s SELECT row_to_json(q)::text FROM (%s) q"
        elif content_type in [ dict, tuple ]:
            pass
        else:
            raise NotImplementedError('content_type %s' % content_type)
        
        upsert_ctes = []
        upsert_queries = []
        
        if allow_existing and nmkcols:
            upsert_ctes.append("updated_rows AS (%s)" % update_sql)
            upsert_queries.append(updated_sql)

        if attr_update is None and allow_missing:
            upsert_ctes.append("inserted_rows AS (%s)" % insert_sql)
            upsert_queries.append(inserted_sql)
    
        upsert_sql = upsert_sql % (
            ',\n'.join(upsert_ctes),
            '\nUNION ALL\n'.join(upsert_queries)
            )

        if allow_existing is False and not skip_key_tests:
            cur.execute("%s INTERSECT ALL %s" % correlating_sql)
            for row in cur:
                raise ConflictData('Input row key (%s) collides with existing entity.' % str(row))

        if allow_missing is False:
            cur.execute("%s EXCEPT ALL %s" % correlating_sql)
            for row in cur:
                raise ConflictData('Input row key (%s) does not match existing entity.' % str(row))

        # we cannot use a held cursor here because upsert_sql modifies the DB
        try:
            notify_data_change(cur, self.table)
            #web.debug(upsert_sql)
            cur.execute(upsert_sql)
        except psycopg2.IntegrityError, e:
            raise ConflictModel('Input data violates model. ' + e.pgerror)
            
        return list(make_row_thunk(None, cur, content_type, drop_tables)())

class AnyPath (object):
    """Hierarchical ERM access to resources, a generic parent-class for concrete resources.

    """
    def sql_get(self, row_content_type='application/json'):
        """Generate SQL query to get the resources described by this path.

           The query will be of the form:

              SELECT 
                tK.* 
              FROM "x" AS t0 
                ... 
              JOIN "z" AS tK ON (...)
              WHERE ...
           
           encoding path references and filter conditions.

        """
        raise NotImplementedError('sql_get on abstract class ermpath.AnyPath')

    def _sql_get_agg_attributes(self, allow_extra=True):
        """Process attribute lists for aggregation APIs.
        """
        aggfunc_templates = dict(
            min='min(%(attr)s)', 
            max='max(%(attr)s)', 
            cnt='count(%(attr)s)', 
            cnt_d='count(DISTINCT %(attr)s)',
            array='array_to_json(array_agg(%(attr)s))'
            )

        aggfunc_star_templates = dict(
            cnt='count(*)',
            array='array_to_json(array_agg(%(attr)s))'
            )

        aggregates = []
        extras = []
        
        for attribute in self.attributes:
            col, base = attribute.resolve_column(self.epath._model, self.epath)
            sql_attr = sql_identifier(
                attribute.alias is not None and str(attribute.alias) or str(col.name)
                )

            if hasattr(attribute, 'aggfunc'):
                templates = col.is_star_column() and aggfunc_star_templates or aggfunc_templates

                if attribute.alias is None:
                    raise BadSyntax('Aggregated column %s must be given an alias.' % attribute)

                if str(attribute.aggfunc) not in templates:
                    raise BadSyntax('Unknown or unsupported aggregate function "%s" applied to column "%s".' % (attribute.aggfunc, col.name))

                aggregates.append((templates[str(attribute.aggfunc)] % dict(attr=sql_attr), sql_attr))
            elif not allow_extra:
                raise BadSyntax('Attribute %s lacks an aggregate function.' % attribute)
            else:
                extras.append(sql_attr)

        return aggregates, extras

    def get(self, conn, cur, content_type='text/csv', output_file=None, limit=None):
        """Fetch resources.

           conn: sanepg2 database connection to catalog

           content_type: 
              text names of MIME types control serialization:
                'text/csv' --> CSV table with header row
                'application/json' --> JSON array of row objects
                'application/x-json-stream' --> stream of JSON objects

              Python types select native Python result formats
                dict  --> dict of column:value per row
                tuple --> tuple of values per row

                for tuples, values will be ordered according to column
                ordering in the catalog model.

           output_file: 
              None --> thunk result, when invoked generates iterable results
              x --> x.write() the serialized output

           Note: only text content types are supported with
           output_file writing.
        """
        # TODO: refactor this common code between 

        sql = self.sql_get(row_content_type=content_type)
        #web.debug(sql)

        if limit is not None:
            sql += (' LIMIT %d' % limit)

        if output_file:
            # efficiently send results to file
            if content_type == 'text/csv':
                sql = "COPY (%s) TO STDOUT CSV DELIMITER ',' HEADER" % sql
            elif content_type == 'application/json':
                sql = "COPY (SELECT array_to_json(array_agg(row_to_json(q)), True)::text FROM (%s) q) TO STDOUT" % sql
            elif content_type == 'application/x-json-stream':
                sql = "COPY (SELECT row_to_json(q)::text FROM (%s) q) TO STDOUT" % sql
            else:
                raise NotImplementedError('content_type %s with output_file.write()' % content_type)

            cur.copy_expert(sql, output_file)

        else:
            # generate rows to caller
            if content_type == 'text/csv':
                # TODO implement and use row_to_csv() stored procedure?
                pass
            elif content_type == 'application/json':
                sql = "SELECT array_to_json(COALESCE(array_agg(row_to_json(q)), ARRAY[]::json[]), True)::text FROM (%s) q" % sql
            elif content_type == 'application/x-json-stream':
                sql = "SELECT row_to_json(q)::text FROM (%s) q" % sql
            elif content_type in [ dict, tuple ]:
                pass
            else:
                raise NotImplementedError('content_type %s' % content_type)

            cur = conn.execute(sql)
            
            return make_row_thunk(conn, cur, content_type)()
        
class EntityPath (AnyPath):
    """Hierarchical ERM data access to whole entities, i.e. table rows.

    """
    def __init__(self, model):
        AnyPath.__init__(self)
        self._model = model
        self._path = None
        self._context_index = None
        self.sort = None
        self.aliases = {}

    def __str__(self):
        return ' / '.join(
            [ str(e) for e in self._path ] 
            + self._context_index >= 0 and [ '$%s' % self._path[self._context_index].alias ] or []
            )

    def __getitem__(self, k):
        return self._path[ self.aliases[k] ]

    def set_base_entity(self, table, alias=None):
        """Root this entity path in the specified table.

           Optionally set alias for the root.
        """
        if not self._path is None:
            raise NotImplementedError('self._path')
        self._path = [ EntityElem(self, alias, table, 0) ]
        self._context_index = -1
        if alias is not None:
            self.aliases[alias] = 0

    def current_entity_table(self):
        """Get table aka entity type associated with the current path.

           The entity type of the path is the right-most table of the
           path.
        """
        return self._path[self._context_index].table

    def current_entity_position(self):
        """Get non-negative integer position of current entity context in path."""
        if self._context_index == -1:
            return len(self._path) - 1
        elif self._context_index >= 0:
            return self._context_index
        else:
            raise NotImplementedError('current_entity_position with index %s' % self._context_index)

    def set_context(self, context):
        """Change path entity context to existing context referenced by alias."""
        alias = context.resolve_context(self)
        self._context_index = self.aliases[alias]

    def get_data_version(self, cur):
        """Get data version txid considering all tables in entity path."""
        preds = [
            '("schema" = %s AND "table" = %s)' % (
                sql_literal(elem.table.schema.name), 
                sql_literal(elem.table.name)
                )
            for elem in self._path
            ]
        cur.execute("""
SELECT COALESCE(max(snap_txid), 0) AS snap_txid 
FROM _ermrest.data_version
WHERE %(pred)s
""" % dict(pred=' OR '.join(preds))
                    )
        version = next(cur)
        return version

    def add_filter(self, filt):
        """Add a filter condition to the current path.

           Filters restrict the matched rows of the right-most table.
        """
        return self._path[self._context_index].add_filter(filt)

    def add_sort(self, sort):
        """Add a sortlist specification for final output.

           Each column must be part of the entity type associated with current path.
        """
        table = self.current_entity_table()

        if not sort:
            self.sort = None
        else:
            parts = []
            for key in sort:
                if key.keyname not in table.columns:
                    raise ConflictModel('Sort key "%s" not found in table "%s".' % (key.keyname, table.name))
                parts.append( '%s%s NULLS LAST' % (
                        sql_identifier(key.keyname), 
                        { True: ' DESC'}.get(key.descending, '')
                        )
                              )

            self.sort = 'ORDER BY ' + ', '.join(parts)

    def add_link(self, keyref, refop, ralias=None, lalias=None):
        """Extend the path by linking in another table.

           keyref specifies the foreign key and primary keys used
           for linkage.

           refop specifies the direction of linkage, i.e. whether the
           left table references the right table or vice versa.  The
           direction can only be successfully reversed when left and
           right tables are of the same type and direction isn't
           statically restricted. But, refop must match the allowed
           direction even when left and right tables are inequal.

           the ralias optionally defines an alias for the newly added
           right-most table instance.

           the lalias selects a left-hand table instance other than
           the right-most table prior to extension.
        """
        if not self._path:
            raise NotImplementedError('self._path %s' % self._path)
        rpos = len(self._path)

        if refop == '@=':
            rtable = keyref.foreign_key.table
        else:
            # '=@'
            rtable = keyref.unique.table

        assert self._context_index >= -1
        if self._context_index >= 0:
            rcontext = self._context_index
        else:
            rcontext = rpos - 1
        
        self._path.append( EntityElem(self, ralias, rtable, rpos, keyref, refop, lalias, rcontext) )
        self._context_index = -1

        if ralias is not None:
            if ralias in self.aliases:
                raise BadData('Alias %s bound more than once.' % ralias)
            self.aliases[ralias] = rpos


    def sql_get(self, selects=None, sort=None, distinct_on=True, row_content_type='application/json'):
        """Generate SQL query to get the entities described by this epath.

           The query will be of the form:

              SELECT 
                DISTINCT ON (...)
                tK.* 
              FROM "x" AS t0 
                ... 
              JOIN "z" AS tK ON (...)
              WHERE ...
           
           encoding path references and filter conditions.

        """
        selects = selects or ("t%d.*" % (self.current_entity_position()))

        pkeys = self._path[self._context_index].table.uniques.keys()
        if pkeys:
            pkeys.sort(key=lambda k: len(k))
            shortest_pkey = self._path[self._context_index].table.uniques[pkeys[0]].columns
        else:
            shortest_pkey = self._path[self._context_index].table.columns_in_order()
        distinct_on_cols = [ 
            't%d.%s' % (self.current_entity_position(), sql_identifier(c.name))
             for c in shortest_pkey
            ]

        tables = [ elem.sql_table_elem() for elem in self._path ]

        wheres = []
        for elem in self._path:
            wheres.extend( elem.sql_wheres() )

        sql = """
SELECT 
  %(distinct_on)s
  %(selects)s
FROM %(tables)s
%(where)s
""" % dict(distinct_on = distinct_on and ('DISTINCT ON (%s)' % ', '.join(distinct_on_cols)) or '',
           selects     = selects,
           tables      = ' JOIN '.join(tables),
           where       = wheres and ('WHERE ' + ' AND '.join(['(%s)' % w for w in wheres])) or '',
           order       = self.sort
           )
	
	# This subquery is ugly and inefficient but necessary due to DISTINCT ON above
	if sort is None:
            sort = self.sort

    	if sort is not None:
            sql = "SELECT * FROM (%s) s %s" % (sql, sort)

        return sql

    def sql_delete(self):
        """Generate SQL statement to delete the entities described by this epath.
        """
        table = self._path[self._context_index].table
        # find the "meta-key" for this table
        #  -- the union of all columns of all keys
        mkcols = set()
        for key in table.uniques:
            for col in key:
                mkcols.add(col)
        mkcols = [ c.sql_name() for c in mkcols ]
        
        return """
DELETE FROM %(table)s AS t
USING (%(getqry)s) AS i
WHERE %(keymatches)s
""" % dict(
            table = table.sql_name(),
            getqry = self.sql_get(),
            keymatches = ' AND '.join([ "t.%s IS NOT DISTINCT FROM i.%s " % (c, c) for c in mkcols ])
            )
    
    def delete(self, conn, cur):
        """Delete entities.

           conn: sanepg2 database connection to catalog
        """
        table = self.current_entity_table()
        if not table.writable_kind():
            raise ConflictModel('Entity %s is not writable.' % table)
        
        cur.execute("SELECT count(*) AS count FROM (%s) s" % self.sql_get())
        if cur.fetchone()[0] == 0:
            raise NotFound('entities matching request path')
        notify_data_change(cur, table)
        cur.execute(self.sql_delete())
        
    def put(self, conn, cur, input_data, in_content_type='text/csv', content_type='text/csv', output_file=None, allow_existing=True, allow_missing=True, attr_update=None, use_defaults=None, attr_aliases=None):
        """Put or update entities depending on allow_existing, allow_missing modes.

           conn: sanepg2 connection to catalog

           input_data:
              x with x.read() --> data will be read
              iterable --> data will be iterated

           in_content_type:
              text names of MIME types control deserialization:
                'text/csv' --> CSV table
                'application/json' --> JSON array of objects
                'application/x-json-stream' --> stream of JSON objects

                for MIME types, iterable input will be concatenated to
                form input byte stream, or read() will be called to
                fetch byte stream until an empty read() result is
                received.
 
              None means input is Python data stream (iter only)
                dicts will be seen as column: value, ... rows
                tuples will be seen as value, ... rows
                other types are erroneous

                for Python data streams, iterable input must yield one
                row respresentation at a time.  read() is not
                supported for Python data streams.

                for tuples, values must be ordered according to column
                ordering in the catalog model.

           content_type and output_file: see documentation for
              identical feature in get() method of this class. The
              result being controlled is a representation of each
              inserted or modified row, including any default values
              which might have been absent from the input.

           allow_existing: when input rows match existing keys
              True --> update existing row with input (default)
              None --> skip input row
              False --> raise exception

           allow_missing: when input rows do not match existing keys
              True --> insert input rows (default)
              None --> skip input row
              False --> raise exception

        """
        
        if len(self._path) != 1:
            raise BadData("unsupported path length for put")
        
        return self._path[0].put(conn, cur, input_data, in_content_type, content_type, output_file, allow_existing, allow_missing, attr_update, use_defaults, attr_aliases)
        

class AttributePath (AnyPath):
    """Hierarchical ERM data access to entity attributes, i.e. table cells.

    """
    def __init__(self, epath, attributes):
        AnyPath.__init__(self)
        self.epath = epath
        self.attributes = attributes
        self.sort = None

    def add_sort(self, sort):
        """Add a sortlist specification for final output.

           Validation deferred until sql_get() runs... sort keys must match designated output columns.
        """
        self.sort = sort

    def sql_get(self, split_sort=False, distinct_on=True, row_content_type='application/json'):
        """Generate SQL query to get the resources described by this apath.

           The query will be of the form:

              SELECT 
                DISTINCT ON (...)
                tK.* 
              FROM "x" AS t0 
                ... 
              JOIN "z" AS tK ON (...)
              WHERE ...
           
           encoding path references and filter conditions.

        """
        # validate attributes for GET case
        selects = []

        outputs = set()

        if row_content_type == 'text/csv':
            cast = '::text'
        else:
            cast = ''

        for attribute in self.attributes:
            col, base = attribute.resolve_column(self.epath._model, self.epath)
            
            if base == self.epath:
                # column in final entity path element
                alias = "t%d" % self.epath.current_entity_position()
            elif base in self.epath.aliases:
                # column in interior path referenced by alias
                alias = "t%d" % self.epath[base].pos
            else:
                raise ConflictModel('Invalid attribute name "%s".' % attribute)

            if hasattr(col, 'sql_name_with_talias'):
                select = col.sql_name_with_talias(alias, output=True)
            else:
                select = "%s.%s" % (alias, col.sql_name())

            select = select + cast

            if attribute.alias is not None:
                if str(attribute.alias) in outputs:
                    raise BadSyntax('Output column name "%s" appears more than once.' % attribute.alias)
                outputs.add(str(attribute.alias))
                selects.append('%s AS %s' % (select, sql_identifier(attribute.alias)))
            else:
                if str(col.name) in outputs:
                    raise BadSyntax('Output column name "%s" appears more than once.' % col.name)
                outputs.add(str(col.name))
                selects.append('%s AS %s' % (select, col.sql_name()))

        if self.sort:
            parts = []
            for key in self.sort:
                if key.keyname not in outputs:
                    raise BadData('Sort key "%s" not among output columns.' % key.keyname)
                parts.append( '%s%s NULLS LAST' % (
                        sql_identifier(key.keyname), 
                        { True: ' DESC'}.get(key.descending, '')
                        )
                              )

            self.sort = 'ORDER BY ' + ', '.join(parts)

        selects = ', '.join(selects)

        if split_sort:
            # let the caller compose the query and the sort clause
            return (self.epath.sql_get(selects=selects, distinct_on=distinct_on), self.sort)
        else:
            return self.epath.sql_get(selects=selects, sort=self.sort, distinct_on=distinct_on)

    def sql_delete(self, del_columns, equery=None):
        """Generate SQL statement to delete the attributes described by this apath.

           del_columns: iterable set of Column instances to be deleted

        """
        if equery is None:
            equery = self.epath.sql_get()

        etable = self.epath.current_entity_table()

        if not etable.writable_kind():
            raise ConflictModel('Entity %s is not writable.' % etable)

        mkcols = set()
        for unique in etable.uniques:
            for c in unique:
                mkcols.add(c)

        for c in del_columns:
            if c in mkcols:
                raise ConflictModel('Deletion of attribute %s not supported because it is part of a unique key for entities.' % c.name)

        # actually correlate by full row, not just unique meta-key
        mkcols = [ c.sql_name() for c in etable.columns_in_order() ]
        nmkcols = [ c.sql_name() for c in del_columns ]
        
        return """
UPDATE %(table)s AS t SET %(updates)s
FROM (%(getqry)s) AS i
WHERE %(keymatches)s
""" % dict(
            table = etable.sql_name(),
            getqry = equery,
            keymatches = ' AND '.join([ "t.%s IS NOT DISTINCT FROM i.%s " % (c, c) for c in mkcols ]),
            updates = ', '.join([ "%s = NULL" % c for c in nmkcols ])
            )
    
    def delete(self, conn, cur):
        """Delete entity attributes.

        """
        equery = self.epath.sql_get()
        nmkcols = set()
        
        # delete columns are named explicitly
        for attribute in self.attributes:
            col, base = attribute.resolve_column(self.epath._model, self.epath)
            if base == self.epath:
                # column in final entity path element
                nmkcols.add(col)
            elif base in self.epath.aliases:
                # column in interior path referenced by alias
                raise ConflictModel('Only unqualified attribute names from entity %s can be modified by DELETE.' % etable.name)
            else:
                raise ConflictModel('Invalid attribute name "%s".' % attribute)
        
        dquery = self.sql_delete(nmkcols, equery)

        cur.execute("SELECT count(*) AS count FROM (%s) s" % equery)
        if cur.fetchone()[0] == 0:
            raise NotFound('entities matching request path')
        table = self.epath.current_entity_table()
        notify_data_change(cur, table)
        cur.execute(dquery)

class AttributeGroupPath (AnyPath):
    """Hierarchical ERM data access to entity attributes, i.e. table cells.

    """
    def __init__(self, epath, groupkeys, attributes):
        AnyPath.__init__(self)
        self.epath = epath
        self.groupkeys = groupkeys
        self.attributes = attributes
        self.sort = None

        if not groupkeys:
            raise BadSyntax('Attribute group requires at least one group key.')

    def add_sort(self, sort):
        """Add a sortlist specification for final output.

           Validation deferred until sql_get() runs... sort keys must match designated output columns.
        """
        self.sort = sort

    def sql_get(self, row_content_type='application/json'):
        """Generate SQL query to get the resources described by this apath.

           The query will be of the form:

              SELECT
                group keys...,
                attributes...
              FROM (
                ...
              ) s
              GROUP BY group keys...

           and may join on an additional DISTINCT ON query if the
           attribute list includes non-key non-aggregate values.
           
           encoding path references and filter conditions.

        """
        apath = AttributePath(self.epath, self.groupkeys + self.attributes)
        apath.add_sort(self.sort)
        
        groupkeys = []
        aggregates = []
        extras = []

        for key in self.groupkeys:
            col, base = key.resolve_column(self.epath._model, self.epath)
            if key.alias is not None:
                groupkeys.append( sql_identifier(str(key.alias)) )
            else:
                groupkeys.append( sql_identifier(str(col.name)) )

        aggregates, extras = self._sql_get_agg_attributes()
        asql, sort = apath.sql_get(split_sort=True, distinct_on=False)
        if not sort:
            sort = ''

        if row_content_type == 'text/csv':
            groupkeys = map(lambda k: '%s::text' % k, groupkeys)
            extras = map(lambda k: '%s::text' % k, extras)
            aggregates = map(lambda a: ('%s::text' % a[0], a[1]), aggregates)

        if extras:
            # an impure aggregate query includes extras which must be reduced 
            # by an arbitrary DISTINCT ON and joined to the core aggregate query
            sql = """
SELECT
  %(selects)s
FROM ( 
  SELECT %(groupaggs)s FROM ( %(asql)s ) s GROUP BY %(groupkeys)s
) g
JOIN ( 
  SELECT DISTINCT ON ( %(groupkeys)s )
    %(groupextras)s
  FROM ( %(asql)s ) s
) e ON ( %(joinons)s )
%(sort)s
"""
        else:
            # a pure aggregate query has only group keys and aggregates
            sql = """
SELECT %(groupaggs)s
FROM ( %(asql)s ) s
GROUP BY %(groupkeys)s
%(sort)s
"""
        return sql % dict(
            asql=asql,
            sort=sort,
            selects=', '.join(['g.%s' % k for k in groupkeys + [ a[1] for a in aggregates]]
                              + [ 'e.%s' % e for e in extras ]),
            groupkeys=', '.join(groupkeys),
            groupaggs=', '.join(groupkeys + ["%s AS %s" % a for a in aggregates]),
            groupextras=', '.join(groupkeys + extras),
            joinons=' AND '.join([ 
                    '(g.%s IS NOT DISTINCT FROM e.%s)' % (k, k)
                    for k in groupkeys
                    ])
            )

    def put(self, conn, cur, input_data, in_content_type='text/csv', content_type='text/csv', output_file=None):
        """Update entity attributes.

           conn: sanepg2 connection to catalog

           input_data:
              x with x.read() --> data will be read
              iterable --> data will be iterated

           in_content_type:
              text names of MIME types control deserialization:
                'text/csv' --> CSV table
                'application/json' --> JSON array of objects
                'application/x-json-stream' --> stream of JSON objects

                for MIME types, iterable input will be concatenated to
                form input byte stream, or read() will be called to
                fetch byte stream until an empty read() result is
                received.
 
              None means input is Python data stream (iter only)
                dicts will be seen as column: value, ... rows
                tuples will be seen as value, ... rows
                other types are erroneous

                for Python data streams, iterable input must yield one
                row respresentation at a time.  read() is not
                supported for Python data streams.

                for tuples, values must be ordered according to column
                ordering in the catalog model.

           content_type and output_file: see documentation for
              identical feature in get() method of this class. The
              result being controlled is a representation of each
              inserted or modified row, including any default values
              which might have been absent from the input.

           allow_existing: when input rows match existing keys
              True --> update existing row with input (default)
              None --> skip input row
              False --> raise exception

           allow_missing: when input rows do not match existing keys
              True --> insert input rows (default)
              None --> skip input row
              False --> raise exception

        """
        mkcols = set()
        mkcol_aliases = dict()
        for groupkey in self.groupkeys:
            col, base = groupkey.resolve_column(self.epath._model, self.epath)
            if col in mkcols:
                raise BadSyntax('Group key column %s cannot be bound more than once.' % col)
            if groupkey.alias:
                mkcol_aliases[col] = groupkey.alias
            if base == self.epath:
                # column in final entity path element
                mkcols.add(col)
            elif base in self.epath.aliases:
                # column in interior path referenced by alias
                mkcols.add(col)
            else:
                raise ConflictModel('Invalid groupkey name "%s".' % groupkey)

        nmkcols = set()
        nmkcol_aliases = dict()
        for attribute in self.attributes:
            if hasattr(attribute, 'aggfunc'):
                raise BadSyntax('Aggregated column %s not allowed in PUT.' % attribute)

            col, base = attribute.resolve_column(self.epath._model, self.epath)
            if col in nmkcols:
                raise BadSyntax('Update column %s cannot be bound more than once.' % col)
            if attribute.alias:
                nmkcol_aliases[col] = attribute.alias
            if base == self.epath:
                # column in final entity path element
                nmkcols.add(col)
            elif base in self.epath.aliases:
                # column in interior path referenced by alias
                raise ConflictModel('Only unqualified attribute names from entity %s can be modified by PUT.' % etable.name)
            else:
                raise ConflictModel('Invalid attribute name "%s".' % attribute)
        
        if not nmkcols:
            raise BadSyntax('Grouped attribute update requires at least one target attribute.')

        attr_update = (list(mkcols), list(nmkcols))
        attr_aliases = (mkcol_aliases, nmkcol_aliases)
        return self.epath.put(conn, cur, input_data, in_content_type, content_type, output_file, allow_existing=True, allow_missing=False, attr_update=attr_update, attr_aliases=attr_aliases)
        

class AggregatePath (AnyPath):
    """Hierarchical ERM data access to aggregate row.

    """
    def __init__(self, epath, attributes):
        AnyPath.__init__(self)
        self.epath = epath
        self.attributes = attributes

        if not attributes:
            raise BadSyntax('Aggregate requires at least one attribute.')

    def add_sort(self, sort):
        """Add a sortlist specification for final output.

           Validation deferred until sql_get() runs... sort keys must match designated output columns.
        """
        if sort:
            raise BadSyntax('Sort is meaningless for aggregates returning one row.')

    def sql_get(self, row_content_type='application/json'):
        """Generate SQL query to get the resources described by this apath.

        """
        apath = AttributePath(self.epath, self.attributes)
        aggregates, extras = self._sql_get_agg_attributes(allow_extra=False)
        asql, sort = apath.sql_get(split_sort=True, distinct_on=False)

        if row_content_type == 'text/csv':
            cast = '::text'
        else:
            cast = ''

        # a pure aggregate query has aggregates
        sql = """
SELECT %(aggs)s
FROM ( %(asql)s ) s
"""
        return sql % dict(
            asql=asql,
            aggs=', '.join([ '%s%s AS %s' % (a[0], cast, a[1]) for a in aggregates]),
            )

class QueryPath (object):
    """Hierarchical ERM data access to query results, i.e. computed rows.

    """
    def __init__(self, epath, expressions):
        self.epath = epath
        self.expressions = expressions

def row_to_dict(cur, row):
    return dict([
            (cur.description[i][0], row[i])
            for i in range(0, len(row))
            ])

def val_to_csv(v):
    def condquote(v):
        if v.find(',') > 0 or v.find('"') > 0:
            return '"%s"' % (v.replace('"', '""'))
        else:
            return v

    if v is None:
        return ''

    if type(v) in [ int, float, long ]:
        return '%s' % v

    if type(v) is list:
        return condquote('{%s}' % ",".join([ val_to_csv(e) for e in v ]))

    else:
        return condquote(str(v))

def row_to_csv(row):
    return ','.join([ val_to_csv(v) for v in row ])

       
