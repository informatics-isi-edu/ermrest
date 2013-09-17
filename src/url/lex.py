

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

"""ERMREST URL tokenizer for resource address language.

The resource addressing language is built on the principal of using
only RFC 3986 reserved characters as special syntax for parsing.  This
is because only reserved characters are defined to have a distinct
quoted and unquoted interpretation.  Non-reserved characters are meant
to be semantically identical whether quoted or not.

Thus, we can use unquoted reserved characters as punctuation and
syntax, while allowing quoted forms to protect any such characters in
user-provided values, i.e. in identifier names or textual data.

Warning: Apache will violate this spec for '/' chars unless you enable
the AllowEncodedSlashes directive, which will break our parser for
any request bearing escaped slashes meant to be user data.

"""


import urllib
import ply.lex

from ermrest.exception import *

# except '%' which we do not want to recognize

# RFC 3986 reserved characters
# removed '*' because mozilla doesn't honor its reserved status
reserved = [
    '(', ')', ':', ';', ',', '=', '@', '&', '$', 
    '/', '?', '#', '[', ']', '!', '"', '\'', '+'
    ]

# only these literal punctuation are actually used in our language
literals = [
    '(', ')', ':', ';', ',', '=', '@', '&', '/'
    ]

# special strings which can be keywords when parsing
keywords = [
    'acl',
    'attribute',
    'catalog',
    'ciregexp',
    'column',
    'entity',
    'foreignkey',
    'geq',
    'gt',
    'key',
    'leq',
    'lt',
    'null',
    'query',
    'reference',
    'referencedby',
    'regexp',
    'schema',
    'table'
]
keywords = dict([
        (kw.lower(), kw.upper())
        for kw in keywords
        ])

tokens = [ 'ESCAPESTRING', 'STRING', 'NUMSTRING', 'OPMARK', 'REFL2R', 'REFR2L', 'ASSIGN' ] + list(keywords.values())

def urlunquote(url):
    if type(url) not in [ str, unicode ]:
        url = str(url)
    text = urllib.unquote_plus(url)
    if type(text) == str:
        text = unicode(text, 'utf8')
    elif type(text) == unicode:
        pass
    else:
        raise TypeError('unexpected decode type %s in rest.url.lex.urlunquote()' % type(text))
    return text

def t_OPMARK(t):
    r'::'
    return t

def t_REFL2R(t):
    r'=@'
    return t

def t_REFR2L(t):
    r'@='
    return t

def t_ASSIGN(t):
    r':='
    return t

# we decode percent-encoded forms as string content
def t_ESCAPESTRING(t):
    r'(%[0-9A-Fa-f][0-9A-Fa-f])+'
    t.value = urlunquote(t.value)
    return t

# we recognize decimal numbers as a subtype of string
def t_NUMSTRING(t):
    r'[0-9]+'
    return t

# unreserved characters in RFC 3986
# plus ASTERISK because mozilla doesn't quote it properly
def t_STRING(t):
    r'[-*_.~A-Za-z]+'
    t.type = keywords.get(t.value, 'STRING')
    return t

def t_error(t):
    raise LexicalError()

def make_lexer():
    return ply.lex.lex(debug=False, optimize=1, lextab='url_lextab')

