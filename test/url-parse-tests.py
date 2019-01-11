#!/usr/bin/python

import web

import sys

from ermrest.url import url_parse_func
from ermrest.url.parse import ParseError

# positive tests

for url in [
    '/ermrest/catalog',
    '/ermrest/catalog/',
    '/ermrest/catalog/232',
    '/ermrest/catalog/232/schema',
    '/ermrest/catalog/232/schema/S1',
    '/ermrest/catalog/232/schema/S1/table',
    '/ermrest/catalog/232/schema/S1/table/T1',
    '/ermrest/catalog/232/schema/S1/table/T1/column',
    '/ermrest/catalog/232/schema/S1/table/T1/column/C1',
    '/ermrest/catalog/232/schema/S1/table/T1/key',
    '/ermrest/catalog/232/schema/S1/table/T1/key/C1,C2,C3',
    '/ermrest/catalog/232/schema/S1/table/T1/key/C1,C2,C3/referencedby/T2',
    '/ermrest/catalog/232/schema/S1/table/T1/key/C1,C2,C3/referencedby/S2:T2',
    '/ermrest/catalog/232/schema/S1/table/T1/key/C1,C2,C3/referencedby/T2/Cx,Cy,Cz',
    '/ermrest/catalog/232/schema/S1/table/T1/foreignkey',
    '/ermrest/catalog/232/schema/S1/table/T1/foreignkey/Cx,Cy,Cz',
    '/ermrest/catalog/232/schema/S1/table/T1/foreignkey/Cx,Cy,Cz/reference',
    '/ermrest/catalog/232/schema/S1/table/T1/foreignkey/Cx,Cy,Cz/reference/T2',
    '/ermrest/catalog/232/schema/S1/table/T1/foreignkey/Cx,Cy,Cz/reference/S2:T2',
    '/ermrest/catalog/232/schema/S1/table/T1/foreignkey/Cx,Cy,Cz/reference/T2/C1,C2,C3',
    '/ermrest/catalog/232/schema/S1/table/T1/referencedby/T2',
    '/ermrest/catalog/232/schema/S1/table/T1/referencedby/S2:T2',
    '/ermrest/catalog/232/schema/S1/table/T1/referencedby/T2/Cx,Cy,Cz',
    '/ermrest/catalog/232/schema/S1/table/T1/referencedby/T2/Cx,Cy,Cz/key',
    '/ermrest/catalog/232/schema/S1/table/T1/referencedby/T2/Cx,Cy,Cz/key/C1,C2,C3',
    '/ermrest/catalog/232/schema/S1/table/T1/reference',
    '/ermrest/catalog/232/schema/S1/table/T1/reference/S2:T2',
    '/ermrest/catalog/232/schema/S1/table/T1/reference/S2:T2/C1,C2,C3',
    '/ermrest/catalog/232/schema/S1/table/T1/reference/S2:T2/C1,C2,C3/foreignkey',
    '/ermrest/catalog/232/schema/S1/table/T1/reference/S2:T2/C1,C2,C3/foreignkey/Cx,Cy,Cz',
    '/ermrest/catalog/232/entity/S1:T1',
    '/ermrest/catalog/232/entity/S1:T1/C1/alias:=C2/N1,N2/(N1)/alias(C1,C2)=@(Cx,Cy)S2:T2/@=(C3,C4)S3:T3',
    '/ermrest/catalog/232/attribute/S1:T1/C1,C2,C3',
    '/ermrest/catalog/232/query/S1:T1/C1,C2,C3'
    ]:
    try:
        url_parse_func(url)
    except Exception as e:
        sys.stderr.write('got exception for: %s\n' % url)
        raise


# negative tests throwing ValueError

for url in [
    '/ermrest/catalog/232/schema/S1/table/T1/key/C1,C2,C3/referencedby/S2:T2:bad',
    '/ermrest/catalog/232/schema/S1/table/T1/foreignkey/Cx,Cy,Cz/reference/S2:T2:bad',
    '/ermrest/catalog/232/schema/S1/table/T1/referencedby/S2:T2:bad/Cx,Cy,Cz/key/C1,C2,C3',
    '/ermrest/catalog/232/schema/S1/table/T1/reference/S2:T2:bad'
    ]:
    got_error = False
    try:
        url_parse_func(url)
    except ValueError:
        got_error = True

    if not got_error:
        raise ValueError('negative test did not raise expected ValueError for: %s' % url)


# negative tests throwing ParseError

for url in [
    '/ermrest/catalog/232/entity'
    ]:
    got_error = False
    try:
        url_parse_func(url)
    except ParseError:
        got_error = True

    if not got_error:
        raise ValueError('negative test did not raise expected ParseError for: %s' % url)

