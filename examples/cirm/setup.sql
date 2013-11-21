CREATE SCHEMA cirm;

CREATE TABLE cirm.box
  (
    id char(30) PRIMARY KEY,
    section_date date NOT NULL,
    sample_name char(15) NOT NULL,
    initials char(3) NOT NULL,
    disambiguator char(1) NOT NULL,
    comment text
  );

CREATE INDEX ON cirm.box USING gin ( (to_tsvector('english', sample_name)) );
CREATE INDEX ON cirm.box USING gin ( (to_tsvector('english', initials)) );
CREATE INDEX ON cirm.box USING gin ( (to_tsvector('english', comment)) );

CREATE TABLE cirm.slide
  (
    id char(37) PRIMARY KEY,
    box_of_origin_id char(30) NOT NULL,
    sequence_num integer NOT NULL,
    revision integer NOT NULL,
    experiment_date date NOT NULL,
    experiment_description char(15) NOT NULL,
    initials char(3) NOT NULL,
    comment text,
    FOREIGN KEY (box_of_origin_id) REFERENCES cirm.box (id)
  );

CREATE INDEX ON cirm.slide USING gin ( (to_tsvector('english', experiment_description)) );
CREATE INDEX ON cirm.slide USING gin ( (to_tsvector('english', initials)) );
CREATE INDEX ON cirm.slide USING gin ( (to_tsvector('english', comment)) );

CREATE TABLE cirm.scan
  (
    id char(41) PRIMARY KEY,
    slide_id char(37),
    scan_num integer NOT NULL,
    filename text,
    thumbnail text,
    tilesdir text,
    comment text,
    FOREIGN KEY (slide_id) REFERENCES cirm.slide (id)
  );

CREATE INDEX ON cirm.scan USING gin ( (to_tsvector('english', comment)) );

