
COPY cirm.box (id, section_date, sample_name, initials, disambiguator, comment) from stdin with csv delimiter ',' quote '"';
20131108-wnt1creZEGG-RES-0,2013-11-08,wnt1creZEGG,RES,0,"This is a box of origin"
\.

COPY cirm.slide (id, box_of_origin_id, sequence_num, revision, experiment_date, experiment_description, initials, comment) from stdin with csv delimiter ',' quote '"';
20131108-wnt1creZEGG-RES-0-38-000,20131108-wnt1creZEGG-RES-0,38,0,2013-11-20,"antibody used",RES,"This is a slide"
20131108-wnt1creZEGG-RES-0-38-001,20131108-wnt1creZEGG-RES-0,38,1,2013-11-21,"antibody used",RES,"This is a slide"
20131108-wnt1creZEGG-RES-0-12-000,20131108-wnt1creZEGG-RES-0,12,0,2013-11-20,"antibody used",RES,"This is a slide"
20131108-wnt1creZEGG-RES-0-84-000,20131108-wnt1creZEGG-RES-0,84,0,2013-11-19,"antibody used",RES,"This is a slide"
20131108-wnt1creZEGG-RES-0-55-000,20131108-wnt1creZEGG-RES-0,55,0,2013-11-22,"antibody used",RES,"This is a slide"
20131108-wnt1creZEGG-RES-0-09-000,20131108-wnt1creZEGG-RES-0,9,0,2013-11-22,"antibody used",RES,"This is a slide"
\.

COPY cirm.scan (id, slide_id, scan_num, filename, thumbnail, tilesdir, comment) from stdin with csv delimiter ',' quote '"';
20131108-wnt1creZEGG-RES-0-38-000-000,20131108-wnt1creZEGG-RES-0-38-000,0,20131108-wnt1creZEGG-RES-0-38-000.czi,20131108-wnt1creZEGG-RES-0-38-000.jpeg,20131108-wnt1creZEGG-RES-0-38-000/,"This is a scan"
20131108-wnt1creZEGG-RES-0-38-000-001,20131108-wnt1creZEGG-RES-0-38-000,1,20131108-wnt1creZEGG-RES-0-38-000(2).czi,20131108-wnt1creZEGG-RES-0-38-000(2).jpeg,20131108-wnt1creZEGG-RES-0-38-000(2)/,"This is a scan"
20131108-wnt1creZEGG-RES-0-38-001-000,20131108-wnt1creZEGG-RES-0-38-001,0,20131108-wnt1creZEGG-RES-0-38-001.czi,20131108-wnt1creZEGG-RES-0-38-001.jpeg,20131108-wnt1creZEGG-RES-0-38-001/,"This is a scan"
20131108-wnt1creZEGG-RES-0-12-000-000,20131108-wnt1creZEGG-RES-0-12-000,0,20131108-wnt1creZEGG-RES-0-12-000.czi,20131108-wnt1creZEGG-RES-0-12-000.jpeg,20131108-wnt1creZEGG-RES-0-12-000/,"This is a scan"
20131108-wnt1creZEGG-RES-0-84-000-000,20131108-wnt1creZEGG-RES-0-84-000,0,20131108-wnt1creZEGG-RES-0-84-000.czi,20131108-wnt1creZEGG-RES-0-84-000.jpeg,20131108-wnt1creZEGG-RES-0-84-000/,"This is a scan"
\.

