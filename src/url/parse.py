

# 
# Copyright 2010-2013 University of Southern California
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

"""ERMREST URL parser grammar for resource address language.

This grammar parses whole URL text for all ERMREST REST URL formats,
handling the complex syntax allowed under each API prefix.  The resulting
abstract syntax tree (AST) 

"""

import ply.yacc as yacc
import threading
import web
import urllib

from ermrest.exception import *

from lex import make_lexer, tokens, keywords
import ast

url_parse_func = None

################################################
# here's the grammar and ast production rules

start = 'start'

# there are multiple productions for most APIs depending on level of detail encoded in URL
def p_apis(p):
    """api   : catalogs 
             | catalog
             | schemas 
             | schema
             | schemaslash
             | tables 
             | tablesslash
             | table
             | tableslash
             | tablecomment
             | columns 
             | column
             | columncomment
             | keys 
             | key
             | foreignkeys 
             | foreignkey
             | foreignkeyrefs 
             | foreignkeyreftable 
             | foreignkeyreftableslash
             | foreignkeyref
             | meta
             | data
             | datasort"""
    p[0] = p[1]

def p_start(p):
    """start : api queryopts"""
    p[0] = p[1].with_queryopts(p[2])

def p_slashopt(p):
    """slashopt : '/' 
                | """
    p[0] = None

def p_catalogs(p):
    """catalogs : '/' string '/' CATALOG slashopt """
    p[0] = ast.Catalogs()

def p_catalog(p):
    """catalog : '/' string '/' CATALOG '/' NUMSTRING """ 
    p[0] = ast.Catalog(p[6])

def p_catalogslash(p):
    """catalogslash : catalog '/' """
    p[0] = p[1]

def p_meta(p):
    """meta : catalogslash META slashopt """
    p[0] = p[1].meta()

def p_data(p):
    """data : entity
            | attribute
            | attributegroup
            | aggregate
            | query"""
    p[0] = p[1]

def p_data_sort(p):
    """datasort : data '@' SORT '(' sortlist ')' """
    p[0] = p[1].with_sort(p[5])

def p_sortlist(p):
    """sortlist : sortitem"""
    p[0] = ast.SortList([ p[1] ])

def p_sortlist_grow(p):
    """sortlist : sortlist ',' sortitem"""
    p[0] = p[1]
    p[0].append( p[3] )

def p_meta_key(p):
    """meta : catalogslash META '/' string slashopt """
    p[0] = p[1].meta(p[4])

def p_meta_key_value(p):
    """meta : catalogslash META '/' string '/' string slashopt """
    p[0] = p[1].meta(p[4], p[6])

def p_entity(p):
    """entity : catalogslash ENTITY '/' entitypath """
    p[0] = p[1].entity(p[4])

def p_attribute(p):
    """attribute : catalogslash ATTRIBUTE '/' entitypath '/' attributeleaf """
    path = p[4]
    path.append(p[6])
    p[0] = p[1].attribute(path)

def p_attributegroup(p):
    """attributegroup : catalogslash ATTRIBUTEGROUP '/' entitypath '/' groupkeys ';' groupleaf """
    path = p[4]
    path.append(p[6])
    path.append(p[8])
    p[0] = p[1].attributegroup(path)

def p_attributegroup_keysonly(p):
    """attributegroup : catalogslash ATTRIBUTEGROUP '/' entitypath '/' groupkeys"""
    path = p[4]
    path.append(p[6])
    path.append(ast.NameList())
    p[0] = p[1].attributegroup(path)

def p_aggregate(p):
    """aggregate : catalogslash AGGREGATE '/' entitypath '/' groupleaf"""
    path = p[4]
    path.append(p[6])
    p[0] = p[1].aggregate(path)

def p_query(p):
    """query : catalogslash QUERY '/' entitypath '/' attributeleaf """
    path = p[4]
    path.append(p[5])
    p[0] = p[1].query(path)

def p_aleaf(p):
    """attributeleaf : attrlist1"""
    p[0] = p[1]

def p_groupkeys(p):
    """groupkeys : attrlist1"""
    p[0] = p[1]

def p_groupleaf(p):
    """groupleaf : leafattrlist1"""
    p[0] = p[1]

def p_entityroot(p):
    """entitypath : entityelem """
    p[0] = ast.data.path.Path()
    p[0].append( p[1] )

def p_entityroot_alias(p):
    """entitypath : string ASSIGN entityelem """
    p[0] = ast.data.path.Path()
    p[3].set_alias(p[1])
    p[0].append( p[3] )

def p_entitypath(p):
    """entitypath : entitypath '/' entityelem """
    p[0] = p[1]
    p[0].append( p[3] )

def p_entitypath_alias(p):
    """entitypath : entitypath '/' string ASSIGN entityelem """
    p[0] = p[1]
    p[5].set_alias(p[3])
    p[0].append( p[5] )


def p_entityelem_single(p):
    """entityelem : sname """
    p[0] = ast.data.path.TableElem(p[1])

def p_entityelem_cols(p):
    """entityelem : '(' snamelist1 ')' """
    p[0] = ast.data.path.ColumnsElem(p[2])

def p_bname(p):
    """bname : string"""
    p[0] = ast.Name().with_suffix(p[1])

def p_sortitem(p):
    """sortitem : string"""
    p[0] = ast.Sortkey(p[1])

def p_sortitem_descending(p):
    """sortitem : string OPMARK DESC OPMARK"""
    p[0] = ast.Sortkey(p[1], True)

def p_bname_grow(p):
    """bname : bname ':' string"""
    p[0] =  p[1].with_suffix(p[3])

def p_name(p):
    """name : ':' bname """
    p[0] = p[2]

def p_sname(p):
    """sname : bname 
             | name"""
    p[0] = p[1]

def p_leafattrlist1(p):
    """leafattrlist1 : leafattritem"""
    p[0] = ast.NameList([ p[1] ])

def p_leafattrlist1_grow(p):
    """leafattrlist1 : leafattrlist1 ',' leafattritem"""
    p[0] = p[1]
    p[0].append( p[3] )

def p_attrlist1(p):
    """attrlist1 : attritem"""
    p[0] = ast.NameList([ p[1] ])

def p_attrlist1_grow(p):
    """attrlist1 : attrlist1 ',' attritem"""
    p[0] = p[1]
    p[0].append( p[3] )

def p_attrcore(p):
    """attrcore : sname
                | aggfunc"""
    p[0] = p[1]

def p_attrcore_agg(p):
    """aggfunc : string '(' sname ')'"""
    p[0] = ast.Aggregate(p[1], p[3])

def p_leafattritem(p):
    """leafattritem : attrcore"""
    p[0] = p[1]

def p_leafattritem_aliased(p):
    """leafattritem : string ASSIGN attrcore"""
    p[0] = p[3].set_alias(p[1])

def p_attritem(p):
    """attritem : sname"""
    p[0] = p[1]

def p_attritem_aliased(p):
    """attritem : string ASSIGN sname"""
    p[0] = p[3].set_alias(p[1])

def p_snamelist1(p):
    """snamelist1 : sname """
    p[0] = ast.NameList([ p[1] ])

def p_namelist(p):
    """snamelist1 : snamelist2 """
    p[0] = p[1]

def p_namelist2(p):
    """snamelist2 : sname ',' sname"""
    p[0] = ast.NameList([ p[1], p[3] ])

def p_namelist2_grow(p):
    """snamelist2 : snamelist2 ',' sname"""
    p[0] = p[1]
    p[0].append( p[3] )

#def p_refop(p):
#    """refop : REFL2R
#             | REFR2L
#             | '@' """
#    p[0] = p[1]

def p_entity_filter(p):
    """entitypath : entitypath '/' filter """
    p[0] = p[1]
    p[0].append( ast.data.path.FilterElem( p[3] ) )

def p_filter(p):
    """filter : disjunction
              | conjunction"""
    p[0] = p[1]

def p_predicate2(p):
    """predicate : sname op expr """
    p[0] = ast.data.path.predicatecls(p[2])(p[1], p[3])

def p_predicate1(p):
    """predicate : sname opnull """
    p[0] = ast.data.path.predicatecls(p[2])(p[1])

def p_neg_predicate1(p):
    """npredicate : predicate """
    p[0] = p[1]

def p_neg_predicate2(p):
    """npredicate : '!' predicate """
    p[0] = ast.data.path.Negation( p[2] )

def p_paren_predicate(p):
    """predicate : '(' filter ')' """
    p[0] = p[2]

def p_conjunction_base(p):
    """conjunction : npredicate """
    p[0] = ast.data.path.Conjunction([p[1]])

def p_conjunction_grow(p):
    """conjunction : conjunction '&' npredicate"""
    p[0] = p[1]
    p[0].append( p[3] )

def p_disjunction_base(p):
    """disjunction : conjunction ';' conjunction"""
    p[0] = ast.data.path.Disjunction([p[1], p[3]])

def p_disjunction_grow(p):
    """disjunction : disjunction ';' conjunction"""
    p[0] = p[1]
    p[0].append( p[3] )

def p_expr_const(p):
    """expr : string """
    p[0] = ast.Value(p[1])

def p_expr_name(p):
    """expr : name """
    p[0] = p[1]

def p_op(p):
    """op : '='"""
    p[0] = p[1]

def p_opnull(p):
    """opnull : OPMARK NULL OPMARK"""
    p[0] = p[2]

def p_op_labeled(p):
    """op : OPMARK oplabel OPMARK """
    p[0] = p[2]

def p_oplabel(p):
    """oplabel : GEQ
               | GT
               | LEQ 
               | LT
               | REGEXP 
               | CIREGEXP
               | TS """
    p[0] = p[1]

def p_schemas(p):
    """schemas : catalogslash SCHEMA slashopt """
    p[0] = p[1].schemas()

def p_schema(p):
    """schema : catalogslash SCHEMA '/' sname """
    p[0] = p[1].schema(p[4])

def p_schema2(p):
    """schemaslash : schema '/'"""
    p[0] = p[1]

def p_tables(p):
    """tables : schemaslash TABLE"""
    p[0] = p[1].tables()

def p_tables2(p):
    """tablesslash : tables '/'"""
    p[0] = p[1]

def p_table(p):
    """table : tablesslash sname """
    if len(p[2]) > 1:
        raise ParseError(p[2], 'Qualified table name not allowed: ')
    p[0] = p[1].table(p[2])

def p_table2(p):
    """tableslash : table '/' """
    p[0] = p[1]

def p_tablecomment(p):
    """tablecomment : tableslash COMMENT """
    p[0] = p[1].comment()

def p_columns(p):
    """columns : tableslash COLUMN slashopt """
    p[0] = p[1].columns()

def p_column(p):
    """column : tableslash COLUMN '/' sname """
    if len(p[4]) > 1:
        raise ParseError(p[4], 'Qualified column name not allowed: ')
    p[0] = p[1].column(p[4])

def p_columncomment(p):
    """columncomment : column '/' COMMENT"""
    p[0] = p[1].comment()

def p_keys(p):
    """keys : tableslash KEY slashopt """
    p[0] = p[1].keys()

def p_key(p):
    """key : tableslash KEY '/' snamelist1 """
    for name in p[4]:
        if len(name) > 1:
            raise ParseError(name, 'Qualified key column name not allowed: ')
    p[0] = p[1].key(p[4])


def p_foreignkeys(p):
    """foreignkeys : tableslash FOREIGNKEY slashopt """
    p[0] = p[1].foreignkeys()

def p_foreignkey(p):
    """foreignkey : tableslash FOREIGNKEY '/' snamelist1 """
    for name in p[4]:
        if len(name) > 1:
            raise ParseError(name, 'Qualified foreign key column name not allowed: ')
    p[0] = p[1].foreignkey(p[4])


def p_foreignkey_reference(p):
    """foreignkeyrefs : foreignkey '/' REFERENCE slashopt """
    p[0] = p[1].references()

def p_foreignkey_reftable(p):
    """foreignkeyreftable : foreignkey '/' REFERENCE '/' sname """
    p[0] = p[1].references().with_to_table_name(p[5])

def p_foreignkey_reftable2(p):
    """foreignkeyreftableslash : foreignkeyreftable '/'"""
    p[0] = p[1]

def p_foreignkey_reftable_columns(p):
    """foreignkeyref : foreignkeyreftableslash snamelist1 """
    for name in p[2]:
        if len(name) > 1:
            raise ParseError(name, 'Qualified key column name not allowed: ')
    p[0] = p[1].with_to_columns(p[2])


def p_queryopts(p):
    """queryopts : queryopts_empty
                 | queryopts_nonempty"""
    p[0] = p[1]

def p_queryopts_empty(p):
    """queryopts_empty : """
    p[0] = web.storage()

def queryopts_add(q, k, v=None):
    """Add value to queryopts by key, handling special cases.

       We support a key with value None to represent a bare query
       parameter with no value assigned.

       We support a key with a single value to represent a basic query
       parameter with one value assigned.

       We support a key with a set of values to represent a query
       parameter with a comma-separated list of strings and/or a
       repetition of a query parameter with different values assigned.

       We follow a promotion from one case to the next as keys and
       values are added.
    """
    if q.has_key(k):
        v0 = q[k]
        if v0 is None:
            q[k] = v
            return
        elif type(v0) != set:
            v0 = set([ v0 ])
            q[k] = v0
        if v is None:
            return
        elif type(v) is set:
            v0.update(v)
        else:
            v0.add(v)
    else:
        q[k] = v

def p_queryopts_nonempty(p):
    """queryopts_nonempty : '?' queryopts_elem"""
    p[0] = web.storage()
    k, v = p[2]
    queryopts_add(p[0], k, v)

def p_queryopts_elem(p):
    """queryopts_elem : string '=' string
                      | string '=' stringset"""
    p[0] = (p[1], p[3])

def p_queryopts_elem_short(p):
    """queryopts_elem : string
                      | string '='"""
    p[0] = (p[1], None)

def p_queryopts_grow(p):
    """queryopts_nonempty : queryopts_nonempty '&' queryopts_elem
                          | queryopts_nonempty ';' queryopts_elem"""
    p[0] = p[1]
    k, v = p[3]
    queryopts_add(p[0], k, v)

def p_stringset(p):
    """stringset : string ',' string"""
    p[0] = set([p[1], p[3]])

def p_stringset_grow(p):
    """stringset : stringset ',' string"""
    p[0] = p[1]
    p[1].add(p[3])

def p_spacestring(p):
    """spacestring : '+'"""
    p[0] = ' '

# grammatically, keywords can also be valid string values...
def p_stringany(p):
    """stub"""
    # weird bit:
    # this doc string is a grammar rule allowing all keywords to be used as string content
    # in contexts where strings are expected.  to avoid this list being inconsistent with
    # changes to the token set, we generate it automatically.
    # this will fail if __doc__ cannot be mutated before yacc reads it
    p[0] = p[1]

p_stringany.__doc__ =  "stringpart : " + " \n| ".join(keywords.values()) + ' \n| ESCAPESTRING \n| STRING \n| NUMSTRING \n| spacestring'

def p_string(p):
    """string : stringpart"""
    p[0] = p[1]

def p_string_concat(p):
    """string : string stringpart"""
    p[0] = p[1] + p[2]

def p_error(t):
    raise ParseError(t)



################################################
# provide wrappers to get a parser instance

def make_parser():
    # use this to shut it up: errorlog=yacc.NullLogger()
    # NullLogger attribute not supported by Python 2.4
    # return yacc.yacc(debug=False, errorlog=yacc.NullLogger())
    return yacc.yacc(debug=True, optimize=1, tabmodule='url_parsetab', write_tables=1)
#    return yacc.yacc()

def make_parse():
    lock = threading.Lock()
    lock.acquire()
    try:
        parser = make_parser()
        lexer = make_lexer()
    finally:
        lock.release()
        
    def parse(s):
        lock.acquire()
        try:
            return parser.parse(s, lexer=lexer)
        finally:
            lock.release()
    return parse

# provide a mutexed parser instance for all to use
url_parse_func = make_parse()

