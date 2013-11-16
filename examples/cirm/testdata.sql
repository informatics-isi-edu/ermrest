
COPY cirm.slide (id, experiment_date, sequence_num, genotype, comment, initials, revision) from stdin with csv delimiter ',' quote '"';
1,2013-11-01,1,wnt1creZEGG,"antibody used",RES,00
2,2013-11-02,83,wnt1creZEGG,"antibody used",RES,00
3,2013-11-03,21,wnt1creZEGG,"antibody used",RES,00
4,2013-11-04,9,wnt1creZEGG,"antibody used",RES,00
5,2013-11-05,59,wnt1creZEGG,"antibody used",RES,00
6,2013-11-06,3,wnt1creZEGG,"antibody used",RES,00
\.

COPY cirm.scan (id, slide_id, filename,thumbnail,tiles,comment) from stdin with csv delimiter ',' quote '"';
1,1,"1.czi","1.thumb.jpeg","1/","good"
2,2,"2.czi","2.thumnb.jpeg","2/","good"
3,4,"3.czi","3.thumnb.jpeg","3/","good"
4,6,"4.czi","4.thumnb.jpeg","4/","good"
5,1,"5.czi","5.thumnb.jpeg","5/","good"
\.


