CREATE SCHEMA microscopy;

CREATE TABLE microscopy.study
  (
    id bigserial PRIMARY KEY,
    comment text
  );

CREATE INDEX ON microscopy.study USING gin ( (to_tsvector('english', COALESCE(comment::text, ''::text))) );

CREATE TABLE microscopy.slide
  (
    id bigserial PRIMARY KEY,
    study_id bigint,
    label text,
    FOREIGN KEY (study_id) REFERENCES microscopy.study (id)
  );

CREATE INDEX ON microscopy.slide USING gin ( (to_tsvector('english', COALESCE(label::text, ''::text))) );

CREATE TABLE microscopy.scan
  (
    id bigserial PRIMARY KEY,
    slide_id bigint,
    uri text,
    FOREIGN KEY (slide_id) REFERENCES microscopy.slide (id)
  );

-- Note: english config doesn't seem to parse URIs very well...
CREATE INDEX ON microscopy.scan USING gin ( (to_tsvector('english', COALESCE(uri::text, ''::text))) );

