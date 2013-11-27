CREATE SCHEMA cirm;

CREATE TABLE cirm.box
  (
    id varchar(30) PRIMARY KEY,
    section_date date NOT NULL,
    sample_name varchar(15) NOT NULL,
    initials varchar(3) NOT NULL,
    disambiguator char(1) NOT NULL,
    comment text
  );

CREATE INDEX ON cirm.box USING gin ( (to_tsvector('english', sample_name)) );
CREATE INDEX ON cirm.box USING gin ( (to_tsvector('english', initials)) );
CREATE INDEX ON cirm.box USING gin ( (to_tsvector('english', comment)) );

CREATE TABLE cirm.experiment
  (
    id varchar(30) PRIMARY KEY,
    experiment_date date NOT NULL,
    experiment_description varchar(15) NOT NULL,
    initials varchar(3) NOT NULL,
    disambiguator char(1) NOT NULL,
    comment text
  );

CREATE INDEX ON cirm.experiment USING gin ( (to_tsvector('english', experiment_description)) );
CREATE INDEX ON cirm.experiment USING gin ( (to_tsvector('english', initials)) );
CREATE INDEX ON cirm.experiment USING gin ( (to_tsvector('english', comment)) );

CREATE TABLE cirm.slide
  (
    id varchar(37) PRIMARY KEY,
    sequence_num integer NOT NULL,
    revision integer NOT NULL,
    box_of_origin_id varchar(30) NOT NULL,
    experiment_id varchar(30),
    comment text,
    FOREIGN KEY (box_of_origin_id) REFERENCES cirm.box (id),
    FOREIGN KEY (experiment_id) REFERENCES cirm.experiment (id)
  );

CREATE INDEX ON cirm.slide USING gin ( (to_tsvector('english', comment)) );

CREATE TABLE cirm.scan
  (
    id varchar(41) PRIMARY KEY,
    slide_id varchar(37),
    scan_num integer NOT NULL,
    filename text,
    thumbnail text,
    tilesdir text,
    comment text,
    FOREIGN KEY (slide_id) REFERENCES cirm.slide (id)
  );

CREATE INDEX ON cirm.scan USING gin ( (to_tsvector('english', comment)) );

