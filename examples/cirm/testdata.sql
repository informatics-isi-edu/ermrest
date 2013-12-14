
COPY cirm.box (id, section_date, sample_name, initials, disambiguator, comment) from stdin with csv delimiter ',' quote '"';
20131108-wnt1creZEGG-RES-0,2013-11-08,wnt1creZEGG,RES,0,"This is a box of origin"
\.

COPY cirm.experiment (id, experiment_date, experiment_description, initials, disambiguator, comment) from stdin with csv delimiter ',' quote '"';
20131112-myantibody1-SV-0,2013-11-12,myantibody1,SV,0,"This is Serban's experiment"
20131115-myantibody2-KC-0,2013-11-15,myantibody2,KC,0,"This is Karl's experiment"
\.

COPY cirm.slide (id, box_of_origin_id, experiment_id, sequence_num, revision, comment) from stdin with csv delimiter ',' quote '"';
20131108-wnt1creZEGG-RES-0-38-000,20131108-wnt1creZEGG-RES-0,,38,0,"This is a slide"
20131108-wnt1creZEGG-RES-0-38-001,20131108-wnt1creZEGG-RES-0,20131112-myantibody1-SV-0,38,1,"This is a slide"
20131108-wnt1creZEGG-RES-0-12-000,20131108-wnt1creZEGG-RES-0,20131112-myantibody1-SV-0,12,0,"This is a slide"
20131108-wnt1creZEGG-RES-0-84-000,20131108-wnt1creZEGG-RES-0,,84,0,"This is a slide"
20131108-wnt1creZEGG-RES-0-55-000,20131108-wnt1creZEGG-RES-0,20131115-myantibody2-KC-0,55,0,"This is a slide"
20131108-wnt1creZEGG-RES-0-09-000,20131108-wnt1creZEGG-RES-0,20131115-myantibody2-KC-0,9,0,"This is a slide"
\.

COPY cirm.scan (id, slide_id, scan_num, filename, thumbnail, tilesdir, comment) from stdin with csv delimiter ',' quote '"';
20131108-wnt1creZEGG-RES-0-38-000-000,20131108-wnt1creZEGG-RES-0-38-000,0,20131108-wnt1creZEGG-RES-0-38-000.czi,20131108-wnt1creZEGG-RES-0-38-000.jpeg,20131108-wnt1creZEGG-RES-0-38-000/,"This is a scan"
20131108-wnt1creZEGG-RES-0-38-000-001,20131108-wnt1creZEGG-RES-0-38-000,1,20131108-wnt1creZEGG-RES-0-38-000.czi,20131108-wnt1creZEGG-RES-0-38-000.jpeg,20131108-wnt1creZEGG-RES-0-38-000/,"This is a scan"
20131108-wnt1creZEGG-RES-0-38-001-000,20131108-wnt1creZEGG-RES-0-38-001,0,20131108-wnt1creZEGG-RES-0-38-000.czi,20131108-wnt1creZEGG-RES-0-38-000.jpeg,20131108-wnt1creZEGG-RES-0-38-000/,"This is a scan"
20131108-wnt1creZEGG-RES-0-12-000-000,20131108-wnt1creZEGG-RES-0-12-000,0,20131204-wnt1creZEGG-RES-0-27-000.czi,20131108-wnt1creZEGG-RES-0-12-000.jpeg,20131108-wnt1creZEGG-RES-0-12-000/,"This is a scan"
20131108-wnt1creZEGG-RES-0-12-000-001,20131108-wnt1creZEGG-RES-0-12-000,0,20131204-wnt1creZEGG-RES-0-27-000.czi,20131108-wnt1creZEGG-RES-0-12-000.jpeg,20131108-wnt1creZEGG-RES-0-12-000/,"This is a scan"
\.

