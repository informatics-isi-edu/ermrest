
COPY cirm.box (id, section_date, sample_name, initials, disambiguator, comment) from stdin with csv delimiter ',' quote '"';
20131108-wnt1creZEGG-RES-0,2013-11-08,wnt1creZEGG,RES,0,"My sectioned sample returned from lab"
20131110-wnt1creZEGG-RES-0,2013-12-01,wnt1creZEGG,RES,0,"Another of my boxes back from lab"
\.

COPY cirm.experiment (id, experiment_date, experiment_description, initials, disambiguator, comment) from stdin with csv delimiter ',' quote '"';
20131112-myantibody1-SV-0,2013-11-12,myantibody1,SV,0,"This is Serban's experiment"
20131115-myantibody2-KC-0,2013-11-15,myantibody2,KC,0,"This is Karl's experiment"
\.

COPY cirm.slide (id, box_of_origin_id, experiment_id, sequence_num, revision, comment) from stdin with csv delimiter ',' quote '"';
20131108-wnt1creZEGG-RES-0-09-000,20131108-wnt1creZEGG-RES-0,20131115-myantibody2-KC-0,9,0,"under further review"
20131108-wnt1creZEGG-RES-0-12-000,20131108-wnt1creZEGG-RES-0,20131112-myantibody1-SV-0,12,0,"using in experiment"
20131108-wnt1creZEGG-RES-0-38-000,20131108-wnt1creZEGG-RES-0,20131112-myantibody1-SV-0,38,0,"looks interesting"
20131108-wnt1creZEGG-RES-0-38-001,20131108-wnt1creZEGG-RES-0,,38,1,"--"
20131108-wnt1creZEGG-RES-0-39-000,20131108-wnt1creZEGG-RES-0,20131115-myantibody2-KC-0,39,0,"--"
20131108-wnt1creZEGG-RES-0-40-000,20131108-wnt1creZEGG-RES-0,,40,0,"--"
20131108-wnt1creZEGG-RES-0-41-000,20131108-wnt1creZEGG-RES-0,,41,0,"--"
20131108-wnt1creZEGG-RES-0-42-000,20131108-wnt1creZEGG-RES-0,,42,0,"--"
20131108-wnt1creZEGG-RES-0-55-000,20131108-wnt1creZEGG-RES-0,20131115-myantibody2-KC-0,55,0,"assigned to experiment"
20131108-wnt1creZEGG-RES-0-81-000,20131108-wnt1creZEGG-RES-0,,81,0,"--"
20131108-wnt1creZEGG-RES-0-82-000,20131108-wnt1creZEGG-RES-0,,82,0,"--"
20131108-wnt1creZEGG-RES-0-83-000,20131108-wnt1creZEGG-RES-0,,83,0,"--"
20131108-wnt1creZEGG-RES-0-84-000,20131108-wnt1creZEGG-RES-0,,84,0,"--"
\.

COPY cirm.slide (id, box_of_origin_id, experiment_id, sequence_num, revision, comment) from stdin with csv delimiter ',' quote '"';
20131110-wnt1creZEGG-RES-0-06-000,20131110-wnt1creZEGG-RES-0,20131115-myantibody2-KC-0,6,0,"slide to be reviewed further"
20131110-wnt1creZEGG-RES-0-12-000,20131110-wnt1creZEGG-RES-0,20131112-myantibody1-SV-0,12,0,"assigned to my experiment"
20131110-wnt1creZEGG-RES-0-25-000,20131110-wnt1creZEGG-RES-0,,25,0,"--"
20131110-wnt1creZEGG-RES-0-26-000,20131110-wnt1creZEGG-RES-0,,26,0,"--"
20131110-wnt1creZEGG-RES-0-27-000,20131110-wnt1creZEGG-RES-0,,27,0,"--"
20131110-wnt1creZEGG-RES-0-28-000,20131110-wnt1creZEGG-RES-0,,28,0,"--"
20131110-wnt1creZEGG-RES-0-29-000,20131110-wnt1creZEGG-RES-0,20131112-myantibody1-SV-0,29,0,"slide is of interest"
20131110-wnt1creZEGG-RES-0-29-001,20131110-wnt1creZEGG-RES-0,,29,1,"discard this one"
20131110-wnt1creZEGG-RES-0-30-000,20131110-wnt1creZEGG-RES-0,,30,0,"--"
20131110-wnt1creZEGG-RES-0-31-000,20131110-wnt1creZEGG-RES-0,20131115-myantibody2-KC-0,31,0,"slide needs more review"
20131110-wnt1creZEGG-RES-0-51-000,20131110-wnt1creZEGG-RES-0,,51,0,"--"
20131110-wnt1creZEGG-RES-0-52-000,20131110-wnt1creZEGG-RES-0,,52,0,"--"
20131110-wnt1creZEGG-RES-0-53-000,20131110-wnt1creZEGG-RES-0,,53,0,"--"
\.

COPY cirm.scan (id, slide_id, scan_num, filename, thumbnail, tilesdir, comment) from stdin with csv delimiter ',' quote '"';
20131108-wnt1creZEGG-RES-0-09-000-000,20131108-wnt1creZEGG-RES-0-09-000,0,sample2.czi,sample2.jpeg,sample2/,"should use this"
20131108-wnt1creZEGG-RES-0-12-000-000,20131108-wnt1creZEGG-RES-0-12-000,0,sample2.czi,sample2.jpeg,sample2/,"scan under review"
20131108-wnt1creZEGG-RES-0-12-000-001,20131108-wnt1creZEGG-RES-0-12-000,0,sample3.czi,sample3.jpeg,sample3/,"should use this one"
20131108-wnt1creZEGG-RES-0-38-000-000,20131108-wnt1creZEGG-RES-0-38-000,0,sample1.czi,sample1.jpeg,sample1/,"some ROIs"
20131108-wnt1creZEGG-RES-0-38-000-001,20131108-wnt1creZEGG-RES-0-38-000,1,sample1.czi,sample1.jpeg,sample1/,"another scan of 38"
20131108-wnt1creZEGG-RES-0-39-000-000,20131108-wnt1creZEGG-RES-0-39-000,0,sample1.czi,sample1.jpeg,sample1/,"more ROIs"
20131108-wnt1creZEGG-RES-0-55-000-000,20131108-wnt1creZEGG-RES-0-55-000,0,sample3.czi,sample3.jpeg,sample3/,"still working on this"
\.

COPY cirm.scan (id, slide_id, scan_num, filename, thumbnail, tilesdir, comment) from stdin with csv delimiter ',' quote '"';
20131110-wnt1creZEGG-RES-0-06-000-000,20131110-wnt1creZEGG-RES-0-06-000,0,sample3.czi,sample3.jpeg,sample3/,"found something"
20131110-wnt1creZEGG-RES-0-12-000-000,20131110-wnt1creZEGG-RES-0-12-000,0,sample2.czi,sample2.jpeg,sample2/,"scan under review"
20131110-wnt1creZEGG-RES-0-29-000-000,20131110-wnt1creZEGG-RES-0-29-000,0,sample1.czi,sample1.jpeg,sample1/,"some ROIs"
20131110-wnt1creZEGG-RES-0-29-000-001,20131110-wnt1creZEGG-RES-0-29-000,1,sample1.czi,sample1.jpeg,sample1/,"another scan of 29"
20131110-wnt1creZEGG-RES-0-31-000-000,20131110-wnt1creZEGG-RES-0-31-000,0,sample2.czi,sample2.jpeg,sample2/,"scan under review"
\.

SET client_min_messages=ERROR;
VACUUM ANALYZE;

