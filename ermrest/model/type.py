
# 
# Copyright 2013-2019 University of Southern California
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

import re
import json

from ..util import sql_identifier, sql_literal
from .. import exception

# only to allow module to be used outside normal service context
_default_config = {
    "column_types": {
        "boolean": { "aliases": [ "bool" ] },
        "date": None,
        "ermrest_rid": None,
        "ermrest_rcb": None,
        "ermrest_rmb": None,
        "ermrest_rct": None,
        "ermrest_rmt": None,
        "ermrest_uri": None,
        "ermrest_curie": None,
        "float4": { "aliases": [ "real" ] },
        "float8": { "aliases": [ "double precision" ] },
        "int2": { "aliases": [ "smallint" ] },
        "int4": { "aliases": [ "integer", "int" ] },
        "int8": { "aliases": [ "bigint" ] },
        "interval": None,
        "jsonb": None,
        "serial2": { "aliases": [ "smallserial" ] },
        "serial4": { "aliases": [ "serial" ] },
        "serial8": { "aliases": [ "bigserial" ] },
        "text": { "aliases": [ "character varying"] },
        "timestamptz": { "aliases": [ "timestamp with time zone" ] },
        "uuid": None
        },
    
    "column_types_readonly": {
        "oid": None,
        "json": None,
        "tsvector": None,
        "text": {
            "aliases": [ "char", "bpchar", "varchar" ],
            "regexps": [ "(text|character)( +varying)?( *[(][0-9]+[)])?$" ]
            },
        "timestamp": { "aliases": [ "timestamp without time zone" ] },
        "tstzrange": None,
        }
    }

_pg_serial_default_pattern = r"nextval[(]'[^']+'::regclass[)]$"

class TypesEngine (object):
    """Stateful engine to help interpret catalog types and policy.

    """
    # TODO: track more type metadata that is currently discarded...?
    def __init__(self, config=None):
        self.config = config
        self.by_rid = dict()
        self.disallowed_by_rid = dict()
        self.by_name = dict()

    def add_base_type(self, rid, type_name, comment):
        try:
            type_name = canonicalize_column_type(type_name, None, self.config, readonly=True)
            if type_name not in self.by_name:
                self.by_name[type_name] = Type(typename=type_name)
            self.by_rid[rid] = self.by_name[type_name]
        except exception.ConflictData:
            self.disallowed_by_rid[rid] = Type(typename=type_name)

    def add_array_type(self, rid, type_name, element_type_rid, comment):
        if element_type_rid not in self.by_rid:
            self.disallowed_by_rid[rid] = ArrayType(base_type=self.disallowed_by_rid[element_type_rid])
        else:
            self.by_rid[rid] = ArrayType(base_type=self.by_rid[element_type_rid])

    def add_domain_type(self, rid, type_name, element_type_rid, default, notnull, comment):
        if element_type_rid not in self.by_rid:
            self.disallowed_by_rid[rid] = DomainType(typename=type_name, base_type=self.disallowed_by_rid[element_type_rid])
        else:
            self.by_rid[rid] = DomainType(typename=type_name, base_type=self.by_rid[element_type_rid])

    def lookup(self, rid, default=None, readonly=False):
        if rid in self.by_rid:
            typ = self.by_rid[rid]
            if typ.is_array or typ.is_domain:
                return typ
            # now check again using column-level default
            type_name = canonicalize_column_type(typ.name, default, self.config, readonly)
            if type_name in self.by_name:
                return self.by_name[type_name]
            else:
                # with current canonicalization rule, this only happens for serial?
                return mock_type({'typename': type_name})
        else:
            raise ValueError('Disallowed type "%s" requested.' % self.disallowed_by_rid[rid])

def mock_type(doc, defaultval=None, config=None, readonly=False):
    if defaultval is None:
        defaultval = doc.get('default')

    if doc.get('is_array', False):
        doc['base_type'] = mock_type(doc['base_type'], config=config, readonly=readonly)
        return ArrayType(**doc)

    doc['typename'] = canonicalize_column_type(doc['typename'], defaultval, config, readonly)
    
    if doc.get('is_domain', False):
        doc['base_type'] = mock_type(doc['base_type'], config=config, readonly=readonly)
        return DomainType(**doc)
    else:
        return Type(**doc)

def canonicalize_column_type(typestr, defaultval, config=None, readonly=False):
    """Return preferred notation for typestr or raise ValueError.

       'typestr' is matched to its preferred form

       'config' contains the 'sql_column_types' policy object

       'readonly' enables read-only policies when True, i.e. to map
       types in an existing database we would reject from a remote
       user creating a new table or column.
       
    """
    if config is None:
        config = _default_config

    def match_type(typestr, defaultval, policy):
        def rewrite_type(typestr):
            if defaultval is not None \
                    and re.match(_pg_serial_default_pattern, defaultval):
                # remap integer type to serial type
                remap = dict(
                    [ (it, 'serial2') for it in [ 'smallint', 'int2' ] ]
                    + [ (it, 'serial4') for it in [ 'integer', 'int4', 'int' ] ]
                    + [ (it, 'serial8') for it in [ 'bigint', 'int8' ] ]
                    )
                if typestr in remap:
                    return match_type(remap[typestr], None, policy)
                
            return typestr

        if typestr in policy:
            return rewrite_type(typestr)

        for preftype, alternatives in policy.items():
            if alternatives is not None:
                if typestr in alternatives.get('aliases', []):
                    # direct use of term alias
                    return rewrite_type(preftype)
                for pattern in alternatives.get('regexps', []):
                    if re.match(pattern, typestr):
                        return rewrite_type(preftype)

    try:
        preftype = match_type(typestr, defaultval, config['column_types'])
    except KeyError as te:
        raise ValueError('ERMrest config missing required policy: %s' % str(te))
    if preftype is not None:
        return preftype
    elif readonly:
        try:
            preftype = match_type(typestr, defaultval, config['column_types_readonly'])
        except KeyError as te:
            raise ValueError('ERMrest config missing required policy: %s' % str(te))
        if preftype is not None:
            return preftype
                
    raise exception.ConflictData('Unsupported type "%s"' % typestr)

class Type (object):
    """Represents a type."""
    is_array = False
    is_domain = False
    
    def __init__(self, **args):
        self.name = args['typename']
        self.length = args.get('length')
    
    def __str__(self):
        return str(self.name)
    
    def sql(self, basic_storage=False):
        if basic_storage:
            # convert sugared types to their basic storage type
            name = {
                'serial2': 'int2',
                'serial4': 'int4',
                'serial8': 'int8'
                }.get(self.name, self.name)
        else:
            name = self.name
        return name

    def url_parse(self, v):
        try:
            typname = self.sql(basic_storage=True)
            if typname in [ 'integer', 'int2', 'int4', 'int8', 'bigint', 'serial2', 'serial4', 'serial8' ]:
                return int(v)
            elif typname in [ 'float', 'float4', 'float8' ]:
                return float(v)
            elif typname in [ 'json', 'jsonb' ]:
                return json.loads(v)
            else:
                # text and text-like...
                return str(v)
        except ValueError:
            raise exception.BadData('Invalid %s: "%s"' % (self.name, v))

    def sql_literal(self, v):
        try:
            typname = self.sql(basic_storage=True)
            if typname in [ 'integer', 'int2', 'int4', 'int8', 'bigint', 'serial2', 'serial4', 'serial8' ]:
                return "%s" % int(v)
            elif typname in [ 'float', 'float4', 'float8' ]:
                return "%s" % float(v)
            else:
                if typname in [ 'json', 'jsonb' ]:
                    v = json.dumps(v)
                # text and text-like...
                return u"'" + str(v).replace(u"'", u"''") + u"'::%s" % self.sql()
        except ValueError:
            raise exception.BadData('Invalid %s: "%s"' % (self.name, v))

    def prejson(self):
        doc = dict(
            typename=str(self.name),
        )
        return doc

    def default_value(self, raw):
        """Converts raw default value with base_type hints.
        """
        if not raw:
            return raw

        if re.match(_pg_serial_default_pattern, raw) \
           and re.match('(big|small)?serial.*', self.name):
            # strip off sequence default since we indicate serial type
            return None

        m = re.match(r"NULL::[a-z ]*", raw)
        if m:
            return None

        m = re.match(r"[(]['(](?P<val>.*)[')]::[a-z ]*[)]::[a-z ]*", raw)
        if m:
            # nested expression  ('val'::base_type)::domain_type
            raw = m.groupdict()['val']
        else:
            # basic expression 'val'::type
            m = re.match(r"['(](?P<val>.*)[')]::[a-z ]*", raw)
            if m:
                raw = m.groupdict()['val']

        typname = self.sql(basic_storage=True)
        if typname in [ 'int2', 'int4', 'int8', 'smallint', 'bigint', 'integer', 'int' ]:
            return int(raw)
        elif typname in [ 'float', 'float4', 'float8', 'real', 'double precision' ]:
            return float(raw)
        elif typname in [ 'bool', 'boolean' ]:
            return raw is not None and raw.lower() == 'true'
        elif typname in [ 'json', 'jsonb' ]:
            return json.loads(raw)
        else:
            # fall back for text and text-like e.g. domains or other unknown types
            return raw

    def history_projection(self, c):
        if c.name in {'RID','RMB'}:
            return 'h.%s::%s' % (sql_identifier(c.name), self.sql(basic_storage=True))
        elif c.name == 'RMT':
            return 'lower(h.during)::%s AS "RMT"' % self.sql(basic_storage=True)
        elif self.name in {'json','jsonb'}:
            return '(h.rowdata->%s)::%s AS %s' % (sql_literal(c.rid), self.sql(basic_storage=True), c.sql_name())
        else:
            return '(h.rowdata->>%s)::%s AS %s' % (sql_literal(c.rid), self.sql(basic_storage=True), c.sql_name())

    @staticmethod
    def fromjson(typedoc, ermrest_config):
        return mock_type(typedoc, config=ermrest_config)

class ArrayType(Type):
    """Represents an array type."""
    is_array = True
    
    def __init__(self, **args):
        args['typename'] = args['base_type'].name + "[]"
        Type.__init__(self, **args)
        self.base_type = args['base_type']

    def prejson(self):
        return dict(
            typename=str(self.name),
            is_array=True,
            base_type=self.base_type.prejson()
            )

    def default_value(self, raw):
        if raw is None:
            return None
        if raw[0:6] == 'ARRAY[' and raw[-1] == ']':
            parts = raw[6:-1].split(',')
            return [ 
                self.default_value(part.strip())
                for part in parts
                ]
        else:
            return self.base_type.default_value(raw)

    def history_projection(self, c):
        # json storage can be `null` or `[...]` for this type
        return (
            "CASE"
            " WHEN jsonb_typeof(%(jfield)s) = 'null' THEN NULL"
            " ELSE (SELECT array_agg(e.x::%(base_type)s) FROM jsonb_array_elements_text(%(jfield)s) e(x))"
            " END AS %(fname)s"
        ) % {
            'jfield': "(h.rowdata->'%s')" % c.rid,
            'array_type': self.sql(basic_storage=True),
            'base_type': self.base_type.sql(basic_storage=True),
            'fname': c.sql_name(),
        }

class DomainType(Type):
    """Represents a domain type."""
    is_domain = True
    
    def __init__(self, **args):
        Type.__init__(self, **args)
        self.base_type = args['base_type']

    def sql(self, basic_storage=False):
        if basic_storage:
            return self.base_type.sql(basic_storage=True)
        else:
            return Type.sql(self)

    def prejson(self):
        return dict(
            is_domain=True,
            typename=str(self.name),
            base_type=self.base_type.prejson()
            )

    def default_value(self, raw):
        if raw is None:
            return None
        else:
            return self.base_type.default_value(raw)

    def history_projection(self, c):
        return self.base_type.history_projection(c)


text_type = mock_type({'typename': 'text', 'length': -1}, readonly=True)
tsvector_type = mock_type({'typename': 'tsvector', 'length': -1}, readonly=True)
int8_type = mock_type({'typename': 'int8', 'length': -1}, readonly=True)
float8_type = mock_type({'typename': 'float8', 'length': -1}, readonly=True)
jsonb_type = mock_type({'typename': 'jsonb', 'length': -1}, readonly=True)

class AggFunc(object):
    aggfunc = None
    aggfunc_sql = None
    supports_star = False
    distinct = ''
    template = '%(aggfunc)s(%(distinct)s %(attr)s::%(btype)s)'
    output_type = None

    def __init__(self, attribute, col, sql_attr):
        if attribute.alias is None:
            raise exception.BadSyntax('Aggregated column %s(%s) must be given an alias.' % (self.aggfunc, attribute))
        if col.is_star_column() and not self.supports_star:
            raise exception.BadSyntax('Aggregate function %s not allowed on star column.' % self.aggfunc)

        self.attribute = attribute
        self.col = col
        self.sql_attr = sql_attr

    def input_type_remap(self):
        ctype = self.col.type.sql(basic_storage=True)
        if ctype == 'json' or self.col.is_star_column():
            ctype = 'jsonb'
        return ctype

    def agg_element(self):
        return self.sql_attr

    def sql(self, template=None):
        if template is None:
            template = self.template
        return (
            template % {
                'aggfunc': self.aggfunc_sql if self.aggfunc_sql is not None else self.aggfunc,
                'distinct': self.distinct,
                'attr': self.agg_element(),
                'btype': self.input_type_remap(),
            },
            self.output_type
        )

class AggMin(AggFunc):
    aggfunc = 'min'

    def __init__(self, attribute, col, sql_attr):
        ctype = col.type
        if ctype.is_domain:
            ctype = ctype.base_type
        if ctype.is_array:
            ctype = ctype.base_type
        if ctype.sql(basic_storage=True) not in {
                'int2', 'int4', 'int8', 'float4', 'float8', 'numeric',
                'text', 'timestamptz', 'timestamp', 'date', 'time', 'timetz',
        }:
            raise exception.ConflictModel('Aggregate function "%s" not allowed on column %s with type %s.' % (self.aggfunc, col.name, col.type.name))
        AggFunc.__init__(self, attribute, col, sql_attr)

class AggMax(AggMin):
    aggfunc = 'max'

class AggAvg(AggFunc):
    aggfunc = 'avg'
    output_type = float8_type

    def __init__(self, attribute, col, sql_attr):
        if col.type.sql(basic_storage=True) not in {'int2', 'int4', 'int8', 'float4', 'float8', 'numeric'}:
            raise exception.ConflictModel('Aggregate function "avg" not allowed on column %s with type %s.' % (col.name, col.type.name))
        AggFunc.__init__(self, attribute, col, sql_attr)

class AggCntDistinct(AggFunc):
    aggfunc = 'cnt_d'
    aggfunc_sql = 'count'
    distinct = 'DISTINCT'
    output_type = int8_type

class AggCnt(AggFunc):
    aggfunc = 'cnt'
    aggfunc_sql = 'count'
    supports_star = True
    output_type = int8_type

    def sql(self):
        if self.col.is_star_column():
            return AggFunc.sql(self, template='count(*)')
        else:
            return AggFunc.sql(self)

class AggArray(AggFunc):
    aggfunc = 'array'
    supports_star = True
    template = 'array_to_json(array_agg(%(distinct)s %(attr)s))::jsonb'
    output_type = jsonb_type

    def agg_element(self):
        if not self.col.is_star_column():
            if self.col.type.is_domain and self.col.type.base_type.is_array or self.col.type.is_array:
                # convert arrays to JSON so we can nest them
                return 'array_to_json(%s::%s)::jsonb' % (self.sql_attr, self.input_type_remap())
        return '%s::%s' % (self.sql_attr, self.input_type_remap())

class AggArrayDistinct(AggArray):
    aggfunc = 'array_d'
    distinct = 'DISTINCT'

aggfuncs = {
    aggfunc.aggfunc: aggfunc
    for aggfunc in [
            AggMin,
            AggMax,
            AggAvg,
            AggCntDistinct,
            AggCnt,
            AggArrayDistinct,
            AggArray,
    ]
}
