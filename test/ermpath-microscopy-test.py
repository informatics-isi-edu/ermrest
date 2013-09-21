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
    '/catalog/1/entity/microscopy:scan',
    '/catalog/1/entity/microscopy:slide',
    '/catalog/1/entity/microscopy:study',
    '/catalog/1/entity/scan',
    '/catalog/1/entity/slide',
    '/catalog/1/entity/study',
    '/catalog/1/entity/study/slide',
    '/catalog/1/entity/study/microscopy:slide',
    '/catalog/1/entity/study/:microscopy:slide',
    '/catalog/1/entity/scan/slide',
    '/catalog/1/entity/study/slide/scan',
    '/catalog/1/entity/scan/slide/study',
    '/catalog/1/entity/scan/slide/study/slide/scan',
    '/catalog/1/entity/a:=scan/b:=slide/c:=study/d:=slide/e:=scan',
    '/catalog/1/entity/a:=scan/b:=slide_id',
    '/catalog/1/entity/a:=scan/slide/study/a:slide_id',
    '/catalog/1/entity/study/slide:study_id',
    '/catalog/1/entity/study/:microscopy:slide:study_id',
    '/catalog/1/entity/study/microscopy:slide:study_id',
    '/catalog/1/entity/a:=scan/b:=slide_id,slide_id',
    '/catalog/1/entity/a:=scan/slide/study/a:slide_id,a:slide_id',
    '/catalog/1/entity/a:=scan/slide/study/slide:study_id,:microscopy:slide:study_id',
    '/catalog/1/entity/study/id=1/comment=experiment%20A/slide/scan'
    ]:
    
    ast = url_parse_func(url)
    
    epath = ast.resolve(m)
    
    print '----------------------------'
    print url
    print str(epath)
    print epath.sql_get()
    content_type = ['application/json', 'text/csv'][0]
    epath.get_to_file(conn, sys.stdout, content_type)
    #print ''.join(epath.get_iter(conn, content_type))
    #print ''.join([ str(r) + '\n' for r in epath.get_iter(conn, None, dict) ])
    print ''

