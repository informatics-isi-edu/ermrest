
COPY microscopy.study (id, comment) from stdin with csv delimiter ',' quote '"';
1,experiment A
2,experiment B
3,experiment C
\.

COPY microscopy.slide (id, study_id, label) from stdin with csv delimiter ',' quote '"';
1,1,A1
2,1,A2
3,1,A3
4,2,B1
5,2,B2
6,3,C1
\.

COPY microscopy.scan (id, slide_id, uri) from stdin with csv delimiter ',' quote '"';
1,1,"file://slide/A1/scan/1"
2,2,"file://slide/A2/scan/1"
3,4,"file://slide/B1/scan/1"
4,6,"file://slide/C1/scan/1"
5,1,"file://slide/A1/scan/2"
\.


