CREATE SCHEMA cansim;

CREATE TABLE cansim."simulation"
  (
    "id" integer PRIMARY KEY,
    "name" text NOT NULL
  );

CREATE TABLE cansim."UserInformation"
  (
    "id" integer PRIMARY KEY,
    "Name" text NOT NULL,
    "Phone" text NOT NULL,
    "URL" text NOT NULL,
    "Affiliation" text NOT NULL,
    "Location" text NOT NULL,
    "email" text NOT NULL
  );

CREATE TABLE cansim."ProgramInformation"
  (
    "id" integer PRIMARY KEY,
    "Name" text NOT NULL,
    "Author" text NOT NULL,
    "URL" text NOT NULL,
    "Compiled" text NOT NULL,
    "Version" text NOT NULL,
    "email" text NOT NULL
  );

CREATE TABLE cansim."reference"
  (
    "id" integer PRIMARY KEY,
    "URL" text NOT NULL,
    "note" text NOT NULL,
    "citation" text NOT NULL
  );

CREATE TABLE cansim."data_source"
  (
    "id" integer PRIMARY KEY,
    "description" text NOT NULL,
    "reference_id" integer NOT NULL,
    "created" text NOT NULL,
    "notes" text NOT NULL,
    "ProgramInformation_id" integer NOT NULL,
    "thumbnail" text NOT NULL,
    "filename" text NOT NULL,
    "UserInformation_id" integer NOT NULL,
    "last_modified" text NOT NULL,
    FOREIGN KEY ("reference_id") REFERENCES cansim."reference" (id),
    FOREIGN KEY ("ProgramInformation_id") REFERENCES cansim."ProgramInformation" (id),
    FOREIGN KEY ("UserInformation_id") REFERENCES cansim."UserInformation" (id)
  );

CREATE TABLE cansim."bounding_box"
  (
    "id" integer PRIMARY KEY,
    "upper_bounds" text NOT NULL,
    "lower_bounds" text NOT NULL
  );

CREATE TABLE cansim."metadata"
  (
    "id" integer PRIMARY KEY,
    "current_time" text NOT NULL,
    "bounding_box_id" integer NOT NULL,
    "data_source_id" integer NOT NULL,
    FOREIGN KEY ("bounding_box_id") REFERENCES cansim."bounding_box" (id),
    FOREIGN KEY ("data_source_id") REFERENCES cansim."data_source" (id)
  );

CREATE TABLE cansim."microenvironment_vector"
  (
    "id" integer PRIMARY KEY,
    "oxygen" text NOT NULL
  );

CREATE TABLE cansim."phenotype_parameter_vector"
  (
    "id" integer PRIMARY KEY,
    "duration_of_S" text NOT NULL,
    "Youngs_modulus" text NOT NULL,
    "fraction_failing_G1_checkpoint" text NOT NULL,
    "duration_of_G1" text NOT NULL,
    "duration_of_G2" text NOT NULL,
    "oxygen_uptake_rate_per_volume" text NOT NULL,
    "cell_volume" text NOT NULL,
    "cell_nuclear_volume" text NOT NULL,
    "duration_of_M" text NOT NULL,
    "maximum_cell_deformation" text NOT NULL,
    "fluid_fraction" text NOT NULL
  );
  
CREATE TABLE cansim."microenvironment_phenotype_pair"
  (
    "id" integer PRIMARY KEY,
    "microenvironment_vector_id" integer NOT NULL,
    "phenotype_parameter_vector_id" integer NOT NULL,
    FOREIGN KEY ("microenvironment_vector_id") REFERENCES cansim."microenvironment_vector" (id),
    FOREIGN KEY ("phenotype_parameter_vector_id") REFERENCES cansim."phenotype_parameter_vector" (id)
  );

CREATE TABLE cansim."cell_line"
  (
    "id" integer PRIMARY KEY,
    "data_source" text NOT NULL,
    "microenvironment_phenotype_pair_id" integer NOT NULL,
    FOREIGN KEY ("microenvironment_phenotype_pair_id") REFERENCES cansim."microenvironment_phenotype_pair" (id)
  );

CREATE TABLE cansim."MultiCell"
  (
    "id" integer PRIMARY KEY,
    "metadata_id" integer NOT NULL,
    "cell_line_id" integer NOT NULL,
    "simulation_id" integer NOT NULL,
    FOREIGN KEY ("simulation_id") REFERENCES cansim."simulation" (id),
    FOREIGN KEY ("metadata_id") REFERENCES cansim."metadata" (id),
    FOREIGN KEY ("cell_line_id") REFERENCES cansim."cell_line" (id)
  );

SET client_min_messages=ERROR;
VACUUM ANALYZE;

