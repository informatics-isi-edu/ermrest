CREATE SCHEMA microscopy;

CREATE TABLE microscopy.study
  (
    id bigserial PRIMARY KEY,
    comment text
  );

CREATE TABLE microscopy.slide
  (
    id bigserial PRIMARY KEY,
    study_id bigint,
    label text,
    FOREIGN KEY (study_id) REFERENCES microscopy.study (id)
  );

CREATE TABLE microscopy.scan
  (
    id bigserial PRIMARY KEY,
    scan_id bigint,
    uri text,
    FOREIGN KEY (slide_id) REFERENCES microscopy.slide (id)
  );

