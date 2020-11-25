
# 
# Copyright 2010-2019 University of Southern California
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

from ..exception import *
from ..model import predicate, normalized_history_snaptime, current_history_amendver

from .lex import make_lexer, tokens, keywords
from . import ast

url_parse_func = None

################################################
# here's the grammar and ast production rules

start = 'start'

# there are multiple productions for most APIs depending on level of detail encoded in URL
def p_apis(p):
    """api   : service
             | serviceslash
             | catalog
             | catalogslash
             | comment
             | acls
             | aclsslash
             | acl
             | dynacls
             | dynaclsslash
             | dynacl
             | annotations
             | annotationsslash
             | annotation
             | schemas 
             | schema
             | schemaslash
             | tables 
             | tablesslash
             | table
             | tableslash
             | columns 
             | columnsslash
             | column
             | columnslash
             | keys 
             | key
             | keyslash
             | foreignkeys 
             | foreignkey
             | foreignkeyrefs 
             | foreignkeyreftable 
             | foreignkeyreftableslash
             | foreignkeyref
             | foreignkeyrefslash
             | textfacet
             | resolve_entity_rid
             | catalog_range
             | data_range
             | config_range
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

def p_service(p):
    """service : '/' string """
    p[0] = ast.Service()

def p_serviceslash(p):
    """serviceslash : service '/' """
    p[0] = p[1]

def p_catalog(p):
    """catalog : serviceslash CATALOG '/' string """ 
    p[0] = ast.Catalog(p[4])

def p_catalog_when(p):
    """catalog : serviceslash CATALOG '/' string '@' string"""
    p[0] = ast.Catalog(p[4])
    cur = web.ctx.ermrest_catalog_pc.cur
    web.ctx.ermrest_history_snaptime = normalized_history_snaptime(cur, p[6])
    web.ctx.ermrest_history_amendver = current_history_amendver(cur, web.ctx.ermrest_history_snaptime)

def p_resolve_entity_rid(p):
    """resolve_entity_rid : catalogslash ENTITY_RID '/' string"""
    p[0] = p[1].entity_rid(p[4])

def p_catalog_range(p):
    """cataloghistory : catalogslash HISTORY"""
    p[0] = p[1]

def p_catalog_history_slash(p):
    """cataloghistoryslash : cataloghistory '/'"""
    p[0] = p[1]

def p_catalog_range0(p):
    """catalog_range : cataloghistoryslash ',' """
    p[0] = ast.history.CatalogHistory(p[1].history_range('', ''))

def p_catalog_range1(p):
    """catalog_range : cataloghistoryslash ',' string """
    p[0] = ast.history.CatalogHistory(p[1].history_range('', p[3]))

def p_catalog_range2(p):
    """catalog_range : cataloghistoryslash string ',' string """
    p[0] = ast.history.CatalogHistory(p[1].history_range(p[2], p[4]))

def p_catalog_range3(p):
    """catalog_range : cataloghistoryslash string ',' """
    p[0] = ast.history.CatalogHistory(p[1].history_range(p[2], ''))

def p_catalog_rangeslash(p):
    """catalog_rangeslash : catalog_range '/'"""
    p[0] = p[1]

def p_data_range(p):
    """data_range : catalog_rangeslash ATTRIBUTE '/' string """
    p[0] = ast.history.DataHistory(p[1].catalog, p[4])

def p_data_range_filtered(p):
    """data_range : data_range '/' string '=' string """
    p[0] = p[1].filtered(p[3], p[5])

def p_config_api(p):
    """config_api : ACL
                  | ACL_BINDING
                  | ANNOTATION """
    p[0] = p[1]

def p_config_range(p):
    """config_range : catalog_rangeslash config_api """
    p[0] = ast.history.ConfigHistory(p[1].catalog, p[2])

def p_config_range2(p):
    """config_range : catalog_rangeslash config_api '/' string"""
    p[0] = ast.history.ConfigHistory(p[1].catalog, p[2], target_rid=p[4])

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
            | aggregate"""
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

def p_data_page_before(p):
    """datasort : datasort '@' BEFORE '(' pagelist ')' """
    p[0] = p[1].with_before(p[5])

def p_data_page_after(p):
    """datasort : datasort '@' AFTER '(' pagelist ')' """
    p[0] = p[1].with_after(p[5])

def p_pagelist(p):
    """pagelist : pageitem"""
    p[0] = ast.PageList([ p[1] ])

def p_pagelist_grow(p):
    """pagelist : pagelist ',' pageitem"""
    p[0] = p[1]
    p[0].append( p[3] )
    
def p_meta_key(p):
    """meta : catalogslash META '/' string """
    p[0] = p[1].meta(p[4])

def p_textfacet(p):
    """textfacet : catalogslash TEXTFACET '/' string """
    p[0] = p[1].textfacet(predicate.Value(p[4]))


def p_entity(p):
    """entity : catalogslash ENTITY '/' entityelem1 """
    p[0] = p[1].entity(p[4])

def p_attribute(p):
    """attribute : attribute_epath '/' attributeleaf """
    p[0] = p[1]
    p[0].set_projection(p[3])

def p_attributegroup(p):
    """attributegroup : attributegroup_epath '/' groupkeys ';' groupleaf """
    p[0] = p[1]
    p[0].set_projection(p[3], p[5])
    
def p_attributegroup_keysonly(p):
    """attributegroup : attributegroup_epath '/' groupkeys"""
    p[0] = p[1]
    p[0].set_projection(p[3], ast.NameList())
    
def p_aggregate(p):
    """aggregate : aggregate_epath '/' groupleaf"""
    p[0] = p[1]
    p[0].set_projection(p[3])


def p_attribute_epath(p):
    """attribute_epath : catalogslash ATTRIBUTE '/' entityelem1 """
    p[0] = p[1].attribute(p[4])
    
def p_attributegroup_epath(p):
    """attributegroup_epath : catalogslash ATTRIBUTEGROUP '/' entityelem1 """
    p[0] = p[1].attributegroup(p[4])
    
def p_aggregate_epath(p):
    """aggregate_epath : catalogslash AGGREGATE '/' entityelem1 """
    p[0] = p[1].aggregate(p[4])


def p_entity_grow(p):
    """entity : entity '/' entityelem2 """
    p[0] = p[1]
    p[0].append(p[3])

def p_attribute_grow(p):
    """attribute_epath : attribute_epath '/' entityelem2 """
    p[0] = p[1]
    p[0].append(p[3])

def p_attributegroup_grow(p):
    """attributegroup_epath : attributegroup_epath '/' entityelem2 """
    p[0] = p[1]
    p[0].append(p[3])

def p_aggregate_grow(p):
    """aggregate_epath : aggregate_epath '/' entityelem2 """
    p[0] = p[1]
    p[0].append(p[3])


def p_aleaf(p):
    """attributeleaf : attrlist1"""
    p[0] = p[1]

def p_groupkeys(p):
    """groupkeys : attrlist1"""
    p[0] = p[1]

def p_groupleaf(p):
    """groupleaf : leafattrlist1"""
    p[0] = p[1]


def p_entityelem_single(p):
    """entityelem : sname """
    p[0] = ast.data.path.TableElem(p[1])

def p_entityelem1(p):
    """entityelem1 : sname """
    p[0] = ast.data.path.TableElem(p[1])

def p_entityelem1_bind(p):
    """entityelem1 : string ASSIGN entityelem1"""
    p[3].set_alias(p[1])
    p[0] = p[3]

def p_outer(p):
    """outer : LEFT 
             | RIGHT 
             | FULL """
    p[0] = p[1]
    
def p_outer_columnselem(p):
    """columnselem : outer '(' snamelist1 ')' """
    p[0] = ast.data.path.ColumnsElem(p[3])
    p[0].set_outer_type(p[1])

def p_columnselem(p):
    """columnselem : '(' snamelist1 ')' """
    p[0] = ast.data.path.ColumnsElem(p[2])

def p_linkelem(p):
    """linkelem : columnselem '=' '(' snamelist1 ')' """
    p[0] = p[1].add_link_rhs(p[4])

def p_entityelem_link(p):
    """entityelem : columnselem 
                  | linkelem"""
    p[0] = p[1]

def p_entityelem2(p):
    """entityelem2 : entityelem"""
    p[0] = p[1]

def p_entityelem2_bind(p):
    """entityelem2 : string ASSIGN entityelem"""
    p[3].set_alias(p[1])
    p[0] = p[3]

def p_entityelem2_filter(p):
    """entityelem2 : filter"""
    p[0] = ast.data.path.FilterElem(p[1]) 

def p_entityelem2_context(p):
    """entityelem2 : '$' sname"""
    p[0] = ast.data.path.ContextResetElem(p[2])
    
def p_bname(p):
    """bname : string"""
    p[0] = ast.Name().with_suffix(p[1])

def p_sortitem(p):
    """sortitem : string"""
    p[0] = ast.Sortkey(p[1])

def p_sortitem_descending(p):
    """sortitem : string OPMARK DESC OPMARK"""
    p[0] = ast.Sortkey(p[1], True)

def p_pageitem(p):
    """pageitem : string"""
    p[0] = predicate.Value(p[1])

def p_pageitem_null(p):
    """pageitem : OPMARK NULL OPMARK"""
    p[0] = predicate.Value(None)

def p_pageitem_empty(p):
    """pageitem : """
    p[0] = predicate.Value('')

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
                | aggfunc
                | binfunc"""
    p[0] = p[1]

def p_aggfunc_name(p):
    """aggfunc_name : ARRAY
                    | ARRAY_D
                    | AVG
                    | SUM
                    | CNT
                    | CNT_D
                    | MIN
                    | MAX"""
    p[0] = p[1]

def p_attrcore_agg(p):
    """aggfunc : aggfunc_name '(' sname ')'"""
    p[0] = ast.Aggregate(p[1], p[3])

# TODO: uncomment if we implement automatic binning modes

#def p_attrcore_bin_0(p):
#    """binfunc : BIN '(' sname ')'"""
#    p[0] = ast.Binning(p[3])

#def p_binfunc_1(p):
#    """binfunc : BIN '(' sname ';' expr ')'"""
#    p[0] = ast.Binning(p[3], nbins=p[5])

def p_binfunc_3(p):
    """binfunc : BIN '(' sname ';' expr ';' expr ';' expr ')'"""
    p[0] = ast.Binning(p[3], nbins=p[5], minv=p[7], maxv=p[9])

def p_leafattritem(p):
    """leafattritem : attrcore"""
    p[0] = p[1]

def p_leafattritem_aliased(p):
    """leafattritem : string ASSIGN attrcore"""
    p[0] = p[3].set_alias(p[1])

def p_attritem(p):
    """attritem : sname
                | binfunc"""
    p[0] = p[1]

def p_attritem_aliased(p):
    """attritem : string ASSIGN sname
                | string ASSIGN binfunc"""
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

def p_filter(p):
    """filter : disjunction
              | conjunction"""
    p[0] = p[1]

def p_predicate2(p):
    """predicate : sname op expr """
    p[0] = predicate.predicatecls(p[2])(p[1], p[3])

def p_predicate1(p):
    """predicate : sname opnull """
    p[0] = predicate.predicatecls(p[2])(p[1])

def p_neg_predicate1(p):
    """npredicate : predicate """
    p[0] = p[1]

def p_neg_predicate2(p):
    """npredicate : '!' predicate """
    p[0] = predicate.Negation( p[2] )

def p_paren_predicate(p):
    """predicate : '(' filter ')' """
    p[0] = p[2]

def p_conjunction_base(p):
    """conjunction : npredicate """
    p[0] = predicate.Conjunction([p[1]])

def p_conjunction_grow(p):
    """conjunction : conjunction '&' npredicate"""
    p[0] = p[1]
    p[0].append( p[3] )

def p_disjunction_base(p):
    """disjunction : conjunction ';' conjunction"""
    p[0] = predicate.Disjunction([p[1], p[3]])

def p_disjunction_grow(p):
    """disjunction : disjunction ';' conjunction"""
    p[0] = p[1]
    p[0].append( p[3] )

def p_expr_const(p):
    """expr : string """
    p[0] = predicate.Value(p[1])

def p_expr_name(p):
    """expr : name """
    p[0] = p[1]

def p_expr_empty(p):
    """expr : """
    p[0] = predicate.Value('')
    
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

def p_commentable(p):
    """commentable : schemaslash
                   | tableslash
                   | columnslash
                   | keyslash
                   | foreignkeyrefslash
    """
    p[0] = p[1]

def p_comment(p):
    """comment : commentable COMMENT"""
    p[0] = p[1].comment()

def p_aclable(p):
    """aclable : catalogslash
               | schemaslash
               | tableslash
               | columnslash
               | foreignkeyrefslash"""
    p[0] = p[1]

def p_acls(p):
    """acls : aclable ACL"""
    p[0] = p[1].acls()

def p_aclsslash(p):
    """aclsslash : acls '/' """
    p[0] = p[1]

def p_acl(p):
    """acl : aclsslash string"""
    p[0] = p[1].acl(p[2])

def p_dynaclable(p):
    """dynaclable : tableslash
                  | columnslash
                  | foreignkeyrefslash"""
    p[0] = p[1]

def p_dynacls(p):
    """dynacls : dynaclable ACL_BINDING"""
    p[0] = p[1].dynacls()

def p_dynaclsslash(p):
    """dynaclsslash : dynacls '/' """
    p[0] = p[1]

def p_dynacl(p):
    """dynacl : dynaclsslash string"""
    p[0] = p[1].dynacl(p[2])

def p_annotatable(p):
    """annotatable : catalogslash
                   | schemaslash
                   | tableslash
                   | columnslash
                   | keyslash
                   | foreignkeyrefslash
    """
    p[0] = p[1]

def p_annotations(p):
    """annotations : annotatable ANNOTATION"""
    p[0] = p[1].annotations()

def p_annotationsslash(p):
    """annotationsslash : annotations '/' """
    p[0] = p[1]

def p_annotation(p):
    """annotation : annotationsslash string"""
    p[0] = p[1].annotation(p[2])
    
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

def p_columns(p):
    """columns : tableslash COLUMN """
    p[0] = p[1].columns()

def p_columns2(p):
    """columnsslash : columns '/' """
    p[0] = p[1]

def p_column(p):
    """column : columnsslash sname """
    if len(p[2]) > 1:
        raise ParseError(p[2], 'Qualified column name not allowed: ')
    p[0] = p[1].column(p[2])

def p_columnslash(p):
    """columnslash : column '/'"""
    p[0] = p[1]

def p_keys(p):
    """keys : tableslash KEY slashopt """
    p[0] = p[1].keys()

def p_key(p):
    """key : tableslash KEY '/' snamelist1 """
    for name in p[4]:
        if len(name) > 1:
            raise ParseError(name, 'Qualified key column name not allowed: ')
    p[0] = p[1].key(p[4])

def p_keyslash(p):
    """keyslash : key '/' """
    p[0] = p[1]

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

def p_foreignkeyrefslash(p):
    """foreignkeyrefslash : foreignkeyref '/'"""
    p[0] = p[1]

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
    if k in q:
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
    return yacc.yacc(debug=False, optimize=1, tabmodule='url_parsetab', write_tables=0)
    #return yacc.yacc(debug=True, write_tables=1)

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

