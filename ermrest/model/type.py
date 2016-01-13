# 
# Copyright 2013-2015 University of Southern California
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
        "serial2": { "aliases": [ "smallserial" ] },
        "serial4": { "aliases": [ "serial" ] },
        "serial8": { "aliases": [ "bigserial" ] },
        "text": { "aliases": [ "character varying"] },
        "timestamptz": { "aliases": [ "timestamp with time zone" ] },
        "uuid": None
        },
    
    "column_types_readonly": {
        "json": None,
        "text": { 
            "regexps": [ "(text|character)( +varying)?( *[(][0-9]+[)])?$" ]
            },
        "timestamp": { "aliases": [ "timestamp without time zone" ] }
        }
    }

_pg_serial_default_pattern = r"nextval[(]'[^']+'::regclass[)]$"

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
    """Represents a column type."""
    is_array = False
    
    def __init__(self, name):
        self.name = name
    
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
                # text and text-like...
                return u"'" + unicode(v).replace(u"'", u"''") + u"'::%s" % self.sql()
        except ValueError:
            raise exception.BadData('Invalid %s: "%s"' % (self.name, v))

    def prejson(self):
        return dict(
            typename=str(self.name)
            )

    def default_value(self, raw):
        """Converts raw default value with base_type hints.
        """
        # BUG: raw default value may have SQL cast syntax, e.g. '(0)::smallint', which is not a valid Python literal
        if not raw:
            return raw
        elif re.match(_pg_serial_default_pattern, raw) \
                and re.match('(big|small)?serial.*', self.name):
            # strip off sequence default since we indicate serial type
            return None
        elif self.name in [ 'int2', 'int4', 'int8', 'smallint', 'bigint', 'integer', 'int' ]:
            return int(raw)
        elif self.name in [ 'float', 'float4', 'float8', 'real', 'double precision' ]:
            return float(raw)
        elif self.name in [ 'bool', 'boolean' ]:
            return raw is not None and raw.lower() == 'true'
        
        m = re.match(r"'(?P<val>.*)'::[a-z ]*", raw)
        if m:
            return m.groupdict()['val']

        m = re.match(r"NULL::[a-z ]*", raw)
        if m:
            return None
        
        raise exception.ConflictData('Unhandled scalar default value: %s' % raw)

    @staticmethod
    def fromjson(typedoc, ermrest_config):
        if typedoc.get('is_array', False):
            return ArrayType.fromjson(typedoc, ermrest_config)
        return Type(canonicalize_column_type(typedoc['typename'], None, ermrest_config))

class ArrayType(Type):
    """Represents a column array type."""
    is_array = True
    
    def __init__(self, base_type):
        Type.__init__(self, base_type.name + "[]")
        self.base_type = base_type
    
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

    @staticmethod
    def fromjson(typedoc, ermrest_config):
        assert typedoc['is_array']
        if 'base_type' in typedoc:
            base_type = Type.fromjson(typedoc['base_type'], ermrest_config)
        else:
            raise exception.ConflictData('array types require a base type')
        if base_type.is_array:
            raise exception.ConflictData('base type of array cannot be another array type')
        return ArrayType( base_type )

