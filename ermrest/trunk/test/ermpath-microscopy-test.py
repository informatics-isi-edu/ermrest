#!/usr/bin/python

import sys
import psycopg2
from ermrest import sanepg2, model
from ermrest.url import url_parse_func

# this test uses default database for user calling test, i.e. one named by username
conn = psycopg2.connect(database='', connection_factory=sanepg2.connection)

m = model.introspect(conn)
#print m.schemas['microscopy'].tables['scan'].columns

# schema microscopy
# study: id (pkey), comment
# slide: id (pkey), study_id -> study.id, label
# scan:  id (pkey), slide_id -> slide.id, uri

# entity URL positive tests
for url in [
    '/ermrest/catalog/1/entity/microscopy:scan',
    '/ermrest/catalog/1/entity/microscopy:slide',
    '/ermrest/catalog/1/entity/microscopy:study',
    '/ermrest/catalog/1/entity/scan',
    '/ermrest/catalog/1/entity/slide',
    '/ermrest/catalog/1/entity/study',
    '/ermrest/catalog/1/entity/study/slide',
    '/ermrest/catalog/1/entity/study/microscopy:slide',
    '/ermrest/catalog/1/entity/study/:microscopy:slide',
    '/ermrest/catalog/1/entity/scan/slide',
    '/ermrest/catalog/1/entity/study/slide/scan',
    '/ermrest/catalog/1/entity/scan/slide/study',
    '/ermrest/catalog/1/entity/scan/slide/study/slide/scan',
    '/ermrest/catalog/1/entity/a:=scan/b:=slide/c:=study/d:=slide/e:=scan',
    '/ermrest/catalog/1/entity/a:=scan/b:=slide_id',
    '/ermrest/catalog/1/entity/a:=scan/slide/study/a:slide_id',
    '/ermrest/catalog/1/entity/study/slide:study_id',
    '/ermrest/catalog/1/entity/study/:microscopy:slide:study_id',
    '/ermrest/catalog/1/entity/study/microscopy:slide:study_id',
    '/ermrest/catalog/1/entity/a:=scan/b:=slide_id,slide_id',
    '/ermrest/catalog/1/entity/a:=scan/slide/study/a:slide_id,a:slide_id',
    '/ermrest/catalog/1/entity/a:=scan/slide/study/slide:study_id,:microscopy:slide:study_id',
    '/ermrest/catalog/1/entity/study/id=1/comment=experiment%20A/slide/scan'
    ]:
    
    ast = url_parse_func(url)
    
    epath = ast.resolve(m)
    
    print '----------------------------'
    print url
    print str(epath)
    print epath.sql_get()
    content_type = ['application/json', 'text/csv', dict, tuple][0]
    output_file = [None, sys.stdout][0]
    #epath.get_to_file(conn, sys.stdout, content_type)
    print ''.join([ str(r) + '\n' for r in epath.get(conn, content_type, output_file) ])
    print ''

