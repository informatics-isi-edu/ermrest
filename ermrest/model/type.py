# 
# Copyright 2013-2016 University of Southern California
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

from .. import exception

# only to allow module to be used outside normal service context
_default_config = {
    "column_types": {
        "boolean": { "aliases": [ "bool" ] },
        "date": None,
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
        "json": None,
        "tsvector": None,
        "text": {
            "aliases": [ "char", "bpchar", "varchar" ],
            "regexps": [ "(text|character)( +varying)?( *[(][0-9]+[)])?$" ]
            },
        "timestamp": { "aliases": [ "timestamp without time zone" ] }
        }
    }

_pg_serial_default_pattern = r"nextval[(]'[^']+'::regclass[)]$"

def build_type(doc, defaultval=None, config=None, readonly=False):
    if defaultval is None:
        defaultval = doc.get('default')

    if doc.get('is_array', False):
        doc['base_type'] = build_type(doc['base_type'], config=config, readonly=readonly)
        return ArrayType(**doc)

    doc['typename'] = canonicalize_column_type(doc['typename'], defaultval, config, readonly)
    
    if doc.get('is_domain', False):
        doc['base_type'] = build_type(doc['base_type'], config=config, readonly=readonly)
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

        for preftype, alternatives in policy.iteritems():
            if alternatives is not None:
                if typestr in alternatives.get('aliases', []):
                    # direct use of term alias
                    return rewrite_type(preftype)
                for pattern in alternatives.get('regexps', []):
                    if re.match(pattern, typestr):
                        return rewrite_type(preftype)

    try:
        preftype = match_type(typestr, defaultval, config['column_types'])
    except (KeyError), te:
        raise ValueError('ERMrest config missing required policy: %s' % str(te))
    if preftype is not None:
        return preftype
    elif readonly:
        try:
            preftype = match_type(typestr, defaultval, config['column_types_readonly'])
        except (KeyError), te:
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

    def sql_literal(self, v):
        try:
            if self.name in [ 'integer', 'int2', 'int4', 'int8', 'bigint', 'serial2', 'serial4', 'serial8' ]:
                return "%s" % int(v)
            elif self.name in [ 'float', 'float4', 'float8' ]:
                return "%s" % float(v)
            else:
                if self.name in [ 'json', 'jsonb' ]:
                    v = json.dumps(v)
                # text and text-like...
                return u"'" + unicode(v).replace(u"'", u"''") + u"'::%s" % self.sql()
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

        m = re.match(r"['(](?P<val>.*)[')]::[a-z ]*", raw)
        if m:
            raw = m.groupdict()['val']

        if self.name in [ 'int2', 'int4', 'int8', 'smallint', 'bigint', 'integer', 'int' ]:
            return int(raw)
        elif self.name in [ 'float', 'float4', 'float8', 'real', 'double precision' ]:
            return float(raw)
        elif self.name in [ 'bool', 'boolean' ]:
            return raw is not None and raw.lower() == 'true'
        elif self.name in [ 'json', 'jsonb' ]:
            return json.loads(raw)
        else:
            # fall back for text and text-like e.g. domains or other unknown types
            return raw

    @staticmethod
    def fromjson(typedoc, ermrest_config):
        return build_type(typedoc, config=ermrest_config)

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

class DomainType(Type):
    """Represents a domain type."""
    is_domain = True
    
    def __init__(self, **args):
        Type.__init__(self, **args)
        self.base_type = args['base_type']

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


text_type = build_type({'typename': 'text', 'length': -1}, readonly=True)
tsvector_type = build_type({'typename': 'tsvector', 'length': -1}, readonly=True)
