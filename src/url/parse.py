

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
             | tables 
             | table
             | columns 
             | column
             | keys 
             | key
             | foreignkeys 
             | foreignkey
             | foreignkeyrefs 
             | foreignkeyreftable 
             | foreignkeyref
             | references 
             | referencedtable 
             | referencedtableslash
             | referencedtablecols
             | referencedtablecolsslash
             | referencedtablecolsslashkey
             | referencedtablecolsslashkeyslash
             | treferencedbys 
             | treferencedbytable 
             | treferencedbytableslash
             | treferencedbytablecols
             | treferencedbytablecolsslash
             | treferencedbytablecolsslashkey
             | treferencedbytablecolsslashkeyslash
             | kreferencedbys 
             | kreferencedbytable 
             | kreferencedbytableslash
             | meta
             | entity
             | attribute
             | query"""
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

def p_meta_key(p):
    """meta : catalogslash META '/' STRING slashopt """
    p[0] = p[1].meta(p[4])

def p_meta_key_value(p):
    """meta : catalogslash META '/' STRING '/' STRING slashopt """
    p[0] = p[1].meta(p[4], p[6])

def p_entity(p):
    """entity : catalogslash ENTITY '/' entitypath """
    p[0] = p[1].entity(p[4])

def p_attribute(p):
    """attribute : catalogslash ATTRIBUTE '/' entitypath '/' attributeleaf """
    path = p[4]
    path.append(p[6])
    p[0] = p[1].attribute(path)

def p_query(p):
    """query : catalogslash QUERY '/' entitypath '/' attributeleaf """
    path = p[4]
    path.append(p[5])
    p[0] = p[1].query(path)

def p_aleaf(p):
    """attributeleaf : namelist1"""
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
    """entityelem : name """
    p[0] = ast.data.path.SingleElem(p[1])

def p_entityelem_multi(p):
    """entityelem : namelist2 """
    p[0] = ast.data.path.MultiElem(p[1])

def p_entityelem_cols(p):
    """entityelem : '(' namelist1 ')' """
    p[0] = ast.data.path.MultiElem(p[2])

def p_entityelem_variants(p):
    """entityelem : ref_left
                  | ref_right """
    p[0] = p[1]

def p_entityelem_fromalias(p):
    """ref_left : string '(' namelist1 ')' """
    p[0] = ast.data.path.ReferenceLeft(p[1], p[3])

def p_entityelem_totable(p):
    """ref_right : '(' namelist1 ')' name """
    p[0] = ast.data.path.ReferenceRight(p[4], p[2])

def p_entityelem_leftdir(p):
    """entityelem : ref_left refop"""
    p[0] = ast.data.path.ReferenceElem(p[1], p[2])

def p_entityelem_rightdir(p):
    """entityelem : refop ref_right"""
    p[0] = ast.data.path.ReferenceElem(None, p[1], p[2])

def p_entityelem_full(p):
    """entityelem : ref_left refop ref_right"""
    p[0] = ast.data.path.ReferenceElem(p[1], p[2], p[3])


def p_name(p):
    """name : string"""
    p[0] = ast.Name().with_suffix(p[1])

def p_name_abs(p):
    """name : ':' string """
    p[0] = ast.Name(absolute=True).with_suffix(p[2])

def p_name_grow(p):
    """name : name ':' string"""
    p[0] = p[1].with_suffix(p[3])


def p_namelist1(p):
    """namelist1 : name """
    p[0] = ast.NameList([ p[1] ])

def p_namelist(p):
    """namelist1 : namelist2 """
    p[0] = p[1]

def p_namelist2(p):
    """namelist2 : name ',' name"""
    p[0] = ast.NameList([ p[1], p[3] ])

def p_namelist2_grow(p):
    """namelist2 : namelist2 ',' name"""
    p[0] = p[1]
    p[0].append( p[3] )


def p_refop(p):
    """refop : REFL2R
             | REFR2L
             | '@' """
    p[0] = p[1]

def p_entity_filter(p):
    """entitypath : entitypath '/' filter """
    p[0] = p[1]
    p[0].append( ast.data.path.FilterElem( p[3] ) )

def p_filter(p):
    """filter : predicate
              | disjunction """
    p[0] = p[1]


def p_predicate2(p):
    """predicate : name op expr """
    p[0] = ast.data.path.predicatecls(p[2])(p[1], p[3])

def p_predicate1(p):
    """predicate : name op """
    p[0] = ast.data.path.predicatecls(p[2])(p[1])

def p_neg_predicate(p):
    """predicate : '!' predicate """
    p[0] = ast.data.path.Negation( p[2] )

def p_paren_predicate(p):
    """predicate : '(' filter ')' """
    p[0] = p[1]

def p_disjunction_base(p):
    """disjunction : predicate ';' predicate"""
    p[0] = ast.data.path.Disjunction([p[1], p[3]])

def p_disjunction_grow(p):
    """disjunction : disjunction ';' predicate"""
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
               | TS
               | NULL """
    p[0] = p[1]

def p_schemas(p):
    """schemas : catalogslash SCHEMA slashopt """
    p[0] = p[1].schemas()

def p_schema(p):
    """schema : catalogslash SCHEMA '/' name """
    p[0] = p[1].schema(p[4])


def p_tables(p):
    """tables : schema '/' TABLE slashopt """
    p[0] = p[1].tables()

def p_table(p):
    """table : schema '/' TABLE '/' name """
    p[0] = p[1].table(p[5])


def p_columns(p):
    """columns : table '/' COLUMN slashopt """
    p[0] = p[1].columns()

def p_column(p):
    """column : table '/' COLUMN '/' name """
    p[0] = p[1].column(p[5])


def p_keys(p):
    """keys : table '/' KEY slashopt """
    p[0] = p[1].keys()

def p_key(p):
    """key : table '/' KEY '/' namelist1 """
    p[0] = p[1].key(p[5])


def p_foreignkeys(p):
    """foreignkeys : table '/' FOREIGNKEY slashopt """
    p[0] = p[1].foreignkeys()

def p_foreignkey(p):
    """foreignkey : table '/' FOREIGNKEY '/' namelist1 """
    p[0] = p[1].foreignkey(p[5])


def p_foreignkey_reference(p):
    """foreignkeyrefs : foreignkey '/' REFERENCE slashopt """
    p[0] = p[1].references()

def p_foreignkey_reftable(p):
    """foreignkeyreftable : foreignkey '/' REFERENCE '/' name """
    p[0] = p[1].references().with_to_table_name(p[5])

def p_foreignkey_reftable_columns(p):
    """foreignkeyref : foreignkeyreftable '/' namelist1 """
    p[0] = p[1].with_to_columns(p[3])


def p_table_references(p):
    """references : table '/' REFERENCE slashopt """
    p[0] = p[1].references()

def p_table_reftable(p):
    """referencedtable : table '/' REFERENCE '/' name """
    p[0] = p[1].references().with_to_table_name(p[5])

def p_table_reftable_slash(p):
    """referencedtableslash : referencedtable '/' """
    p[0] = p[1]

def p_table_reftable_columns(p):
    """referencedtablecols : referencedtableslash namelist1 """
    p[0] = p[1].with_to_columns(p[2])

def p_table_reftable_columns_slash(p):
    """referencedtablecolsslash : referencedtablecols '/' """
    p[0] = p[1]

def p_table_reftable_columns_slash_key(p):
    """referencedtablecolsslashkey : referencedtablecolsslash FOREIGNKEY """
    p[0] = p[1]

def p_table_reftable_columns_slash_key_slash(p):
    """referencedtablecolsslashkeyslash : referencedtablecolsslashkey '/' """
    p[0] = p[1]

def p_table_reftable_columns_foreignkey(p):
    """foreignkeyref : referencedtablecolsslashkeyslash namelist1 """
    p[0] = p[1].with_from_columns(p[2])


def p_t_refbys(p):
    """treferencedbys : treferencedby slashopt """
    p[0] = p[1]

def p_t_refby(p):
    """treferencedby : table '/' REFERENCEDBY """
    p[0] = p[1].referencedbys()

def p_t_refby_table(p):
    """treferencedbytable : treferencedby '/' name """
    p[0] = p[1].with_from_table_name(p[3])

def p_t_refby_table_slash(p):
    """treferencedbytableslash : treferencedbytable '/' """
    p[0] = p[1]

def p_t_refby_table_cols(p):
    """treferencedbytablecols : treferencedbytableslash namelist1 """
    p[0] = p[1].with_from_columns(p[2])

def p_t_refby_table_cols_slash(p):
    """treferencedbytablecolsslash : treferencedbytablecols '/' """
    p[0] = p[1]

def p_t_refby_table_cols_slash_key(p):
    """treferencedbytablecolsslashkey : treferencedbytablecolsslash KEY """
    p[0] = p[1]

def p_t_refby_table_cols_slash_key_slash(p):
    """treferencedbytablecolsslashkeyslash : treferencedbytablecolsslashkey '/' """
    p[0] = p[1]

def p_t_refby_table_cols_slash_key_slash_foreignkey(p):
    """foreignkeyref : treferencedbytablecolsslashkey '/' namelist1"""
    p[0] = p[1].with_to_columns(p[3])


def p_k_refbys(p):
    """kreferencedbys : kreferencedby slashopt """
    p[0] = p[1]

def p_k_refby(p):
    """kreferencedby : key '/' REFERENCEDBY """
    p[0] = p[1].referencedbys()

def p_k_refby_table(p):
    """kreferencedbytable : kreferencedby '/' name """
    p[0] = p[1].with_from_table_name(p[3])

def p_k_refby_table_slash(p):
    """kreferencedbytableslash : kreferencedbytable '/' """
    p[0] = p[1]

def p_k_refby_table_foreignkey(p):
    """foreignkeyref : kreferencedbytableslash namelist1 """
    p[0] = p[1].with_from_columns(p[2])


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
    return yacc.yacc(debug=False, optimize=1, tabmodule='url_parsetab', write_tables=1)
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

