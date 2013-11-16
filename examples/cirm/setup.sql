CREATE SCHEMA cirm;

CREATE TABLE cirm.slide
  (
    id bigserial PRIMARY KEY,
    experiment_date date,
    sequence_num integer,
    genotype text,
    comment text,
    initials text,
    revision integer
  );

CREATE INDEX ON cirm.slide USING gin ( (to_tsvector('english', genotype)) );
CREATE INDEX ON cirm.slide USING gin ( (to_tsvector('english', comment)) );
CREATE INDEX ON cirm.slide USING gin ( (to_tsvector('english', initials)) );

CREATE TABLE cirm.scan
  (
    id bigserial PRIMARY KEY,
    slide_id bigint,
    filename text,
    thumbnail text,
    tiles text,
    comment text,
    FOREIGN KEY (slide_id) REFERENCES cirm.slide (id)
  );

-- Note: english config doesn't seem to parse URIs very well...
CREATE INDEX ON cirm.scan USING gin ( (to_tsvector('english', comment)) );

