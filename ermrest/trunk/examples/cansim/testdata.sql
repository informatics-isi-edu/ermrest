COPY cansim."simulation" ("id", "name") from stdin with csv delimiter ',' quote '"';
"1","hypoxia"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"1","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"1","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"1","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"1","3D agent-based model","1","insert code","none","1","sample_hypoxia/output_000000.xml","1","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"1","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"1","0","1","1"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"1","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"1","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"1","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"1","1","1","1"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"2","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"2","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"2","1","2","2"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"1","1","1","1"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"2","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"2","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"2","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"2","3D agent-based model","2","insert code","none","2","sample_hypoxia/output_000001.xml","2","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"2","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"2","0","2","2"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"2","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"3","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"3","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"3","2","3","3"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"4","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"4","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"4","2","4","4"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"2","2","2","1"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"3","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"3","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"3","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"3","3D agent-based model","3","insert code","none","3","sample_hypoxia/output_000002.xml","3","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"3","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"3","0","3","3"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"3","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"5","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"5","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"5","3","5","5"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"6","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"6","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"6","3","6","6"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"3","3","3","1"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"4","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"4","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"4","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"4","3D agent-based model","4","insert code","none","4","sample_hypoxia/output_000003.xml","4","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"4","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"4","0","4","4"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"4","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"7","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"7","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"7","4","7","7"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"8","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"8","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"8","4","8","8"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"4","4","4","1"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"5","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"5","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"5","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"5","3D agent-based model","5","insert code","none","5","sample_hypoxia/output_000004.xml","5","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"5","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"5","0","5","5"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"5","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"9","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"9","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"9","5","9","9"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"10","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"10","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"10","5","10","10"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"5","5","5","1"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"6","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"6","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"6","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"6","3D agent-based model","6","insert code","none","6","sample_hypoxia/output_000005.xml","6","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"6","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"6","0","6","6"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"6","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"11","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"11","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"11","6","11","11"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"12","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"12","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"12","6","12","12"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"6","6","6","1"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"7","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"7","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"7","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"7","3D agent-based model","7","insert code","none","7","sample_hypoxia/output_000006.xml","7","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"7","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"7","0","7","7"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"7","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"13","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"13","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"13","7","13","13"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"14","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"14","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"14","7","14","14"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"7","7","7","1"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"8","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"8","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"8","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"8","3D agent-based model","8","insert code","none","8","sample_hypoxia/output_000007.xml","8","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"8","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"8","0","8","8"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"8","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"15","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"15","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"15","8","15","15"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"16","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"16","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"16","8","16","16"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"8","8","8","1"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"9","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"9","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"9","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"9","3D agent-based model","9","insert code","none","9","sample_hypoxia/output_000008.xml","9","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"9","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"9","0","9","9"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"9","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"17","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"17","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"17","9","17","17"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"18","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"18","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"18","9","18","18"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"9","9","9","1"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"10","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"10","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"10","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"10","3D agent-based model","10","insert code","none","10","sample_hypoxia/output_000009.xml","10","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"10","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"10","0","10","10"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"10","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"19","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"19","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"19","10","19","19"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"20","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"20","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"20","10","20","20"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"10","10","10","1"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"11","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"11","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"11","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"11","3D agent-based model","11","insert code","none","11","sample_hypoxia/output_000010.xml","11","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"11","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"11","0","11","11"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"11","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"21","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"21","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"21","11","21","21"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"22","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"22","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"22","11","22","22"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"11","11","11","1"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"12","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"12","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"12","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"12","3D agent-based model","12","insert code","none","12","sample_hypoxia/output_000011.xml","12","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"12","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"12","0","12","12"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"12","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"23","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"23","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"23","12","23","23"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"24","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"24","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"24","12","24","24"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"12","12","12","1"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"13","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"13","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"13","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"13","3D agent-based model","13","insert code","none","13","sample_hypoxia/output_000012.xml","13","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"13","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"13","0","13","13"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"13","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"25","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"25","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"25","13","25","25"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"26","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"26","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"26","13","26","26"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"13","13","13","1"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"14","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"14","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"14","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"14","3D agent-based model","14","insert code","none","14","sample_hypoxia/output_000013.xml","14","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"14","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"14","0","14","14"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"14","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"27","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"27","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"27","14","27","27"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"28","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"28","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"28","14","28","28"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"14","14","14","1"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"15","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"15","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"15","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"15","3D agent-based model","15","insert code","none","15","sample_hypoxia/output_000014.xml","15","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"15","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"15","0","15","15"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"15","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"29","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"29","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"29","15","29","29"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"30","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"30","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"30","15","30","30"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"15","15","15","1"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"16","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"16","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"16","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"16","3D agent-based model","16","insert code","none","16","sample_hypoxia/output_000015.xml","16","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"16","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"16","0","16","16"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"16","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"31","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"31","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"31","16","31","31"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"32","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"32","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"32","16","32","32"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"16","16","16","1"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"17","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"17","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"17","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"17","3D agent-based model","17","insert code","none","17","sample_hypoxia/output_000016.xml","17","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"17","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"17","0","17","17"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"17","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"33","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"33","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"33","17","33","33"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"34","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"34","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"34","17","34","34"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"17","17","17","1"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"18","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"18","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"18","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"18","3D agent-based model","18","insert code","none","18","sample_hypoxia/output_000017.xml","18","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"18","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"18","0","18","18"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"18","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"35","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"35","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"35","18","35","35"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"36","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"36","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"36","18","36","36"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"18","18","18","1"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"19","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"19","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"19","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"19","3D agent-based model","19","insert code","none","19","sample_hypoxia/output_000018.xml","19","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"19","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"19","0","19","19"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"19","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"37","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"37","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"37","19","37","37"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"38","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"38","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"38","19","38","38"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"19","19","19","1"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"20","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"20","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"20","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"20","3D agent-based model","20","insert code","none","20","sample_hypoxia/output_000019.xml","20","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"20","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"20","0","20","20"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"20","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"39","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"39","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"39","20","39","39"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"40","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"40","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"40","20","40","40"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"20","20","20","1"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"21","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"21","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"21","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"21","3D agent-based model","21","insert code","none","21","sample_hypoxia/output_000020.xml","21","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"21","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"21","0","21","21"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"21","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"41","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"41","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"41","21","41","41"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"42","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"42","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"42","21","42","42"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"21","21","21","1"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"22","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"22","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"22","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"22","3D agent-based model","22","insert code","none","22","sample_hypoxia/output_000021.xml","22","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"22","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"22","0","22","22"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"22","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"43","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"43","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"43","22","43","43"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"44","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"44","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"44","22","44","44"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"22","22","22","1"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"23","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"23","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"23","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"23","3D agent-based model","23","insert code","none","23","sample_hypoxia/output_000022.xml","23","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"23","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"23","0","23","23"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"23","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"45","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"45","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"45","23","45","45"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"46","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"46","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"46","23","46","46"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"23","23","23","1"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"24","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"24","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"24","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"24","3D agent-based model","24","insert code","none","24","sample_hypoxia/output_000023.xml","24","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"24","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"24","0","24","24"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"24","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"47","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"47","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"47","24","47","47"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"48","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"48","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"48","24","48","48"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"24","24","24","1"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"25","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"25","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"25","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"25","3D agent-based model","25","insert code","none","25","sample_hypoxia/output_000024.xml","25","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"25","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"25","0","25","25"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"25","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"49","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"49","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"49","25","49","49"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"50","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"50","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"50","25","50","50"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"25","25","25","1"
\.

COPY cansim."simulation" ("id", "name") from stdin with csv delimiter ',' quote '"';
"2","normoxia"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"26","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"26","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"26","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"26","3D agent-based model","26","insert code","none","26","sample_output1/output_000000.xml","26","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"26","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"26","0","26","26"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"26","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"51","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"51","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"51","26","51","51"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"52","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"52","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"52","26","52","52"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"26","26","26","2"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"27","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"27","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"27","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"27","3D agent-based model","27","insert code","none","27","sample_output1/output_000001.xml","27","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"27","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"27","0","27","27"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"27","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"53","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"53","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"53","27","53","53"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"54","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"54","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"54","27","54","54"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"27","27","27","2"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"28","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"28","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"28","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"28","3D agent-based model","28","insert code","none","28","sample_output1/output_000002.xml","28","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"28","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"28","0","28","28"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"28","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"55","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"55","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"55","28","55","55"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"56","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"56","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"56","28","56","56"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"28","28","28","2"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"29","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"29","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"29","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"29","3D agent-based model","29","insert code","none","29","sample_output1/output_000003.xml","29","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"29","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"29","0","29","29"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"29","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"57","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"57","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"57","29","57","57"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"58","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"58","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"58","29","58","58"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"29","29","29","2"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"30","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"30","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"30","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"30","3D agent-based model","30","insert code","none","30","sample_output1/output_000004.xml","30","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"30","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"30","0","30","30"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"30","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"59","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"59","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"59","30","59","59"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"60","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"60","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"60","30","60","60"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"30","30","30","2"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"31","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"31","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"31","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"31","3D agent-based model","31","insert code","none","31","sample_output1/output_000005.xml","31","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"31","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"31","0","31","31"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"31","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"61","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"61","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"61","31","61","61"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"62","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"62","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"62","31","62","62"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"31","31","31","2"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"32","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"32","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"32","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"32","3D agent-based model","32","insert code","none","32","sample_output1/output_000006.xml","32","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"32","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"32","0","32","32"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"32","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"63","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"63","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"63","32","63","63"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"64","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"64","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"64","32","64","64"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"32","32","32","2"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"33","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"33","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"33","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"33","3D agent-based model","33","insert code","none","33","sample_output1/output_000007.xml","33","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"33","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"33","0","33","33"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"33","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"65","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"65","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"65","33","65","65"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"66","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"66","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"66","33","66","66"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"33","33","33","2"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"34","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"34","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"34","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"34","3D agent-based model","34","insert code","none","34","sample_output1/output_000008.xml","34","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"34","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"34","0","34","34"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"34","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"67","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"67","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"67","34","67","67"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"68","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"68","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"68","34","68","68"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"34","34","34","2"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"35","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"35","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"35","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"35","3D agent-based model","35","insert code","none","35","sample_output1/output_000009.xml","35","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"35","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"35","0","35","35"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"35","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"69","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"69","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"69","35","69","69"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"70","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"70","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"70","35","70","70"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"35","35","35","2"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"36","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"36","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"36","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"36","3D agent-based model","36","insert code","none","36","sample_output1/output_000010.xml","36","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"36","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"36","0","36","36"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"36","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"71","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"71","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"71","36","71","71"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"72","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"72","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"72","36","72","72"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"36","36","36","2"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"37","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"37","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"37","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"37","3D agent-based model","37","insert code","none","37","sample_output1/output_000011.xml","37","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"37","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"37","0","37","37"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"37","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"73","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"73","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"73","37","73","73"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"74","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"74","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"74","37","74","74"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"37","37","37","2"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"38","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"38","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"38","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"38","3D agent-based model","38","insert code","none","38","sample_output1/output_000012.xml","38","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"38","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"38","0","38","38"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"38","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"75","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"75","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"75","38","75","75"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"76","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"76","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"76","38","76","76"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"38","38","38","2"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"39","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"39","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"39","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"39","3D agent-based model","39","insert code","none","39","sample_output1/output_000013.xml","39","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"39","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"39","0","39","39"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"39","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"77","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"77","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"77","39","77","77"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"78","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"78","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"78","39","78","78"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"39","39","39","2"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"40","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"40","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"40","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"40","3D agent-based model","40","insert code","none","40","sample_output1/output_000014.xml","40","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"40","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"40","0","40","40"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"40","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"79","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"79","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"79","40","79","79"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"80","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"80","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"80","40","80","80"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"40","40","40","2"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"41","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"41","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"41","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"41","3D agent-based model","41","insert code","none","41","sample_output1/output_000015.xml","41","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"41","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"41","0","41","41"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"41","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"81","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"81","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"81","41","81","81"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"82","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"82","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"82","41","82","82"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"41","41","41","2"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"42","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"42","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"42","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"42","3D agent-based model","42","insert code","none","42","sample_output1/output_000016.xml","42","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"42","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"42","0","42","42"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"42","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"83","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"83","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"83","42","83","83"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"84","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"84","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"84","42","84","84"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"42","42","42","2"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"43","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"43","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"43","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"43","3D agent-based model","43","insert code","none","43","sample_output1/output_000017.xml","43","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"43","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"43","0","43","43"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"43","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"85","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"85","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"85","43","85","85"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"86","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"86","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"86","43","86","86"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"43","43","43","2"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"44","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"44","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"44","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"44","3D agent-based model","44","insert code","none","44","sample_output1/output_000018.xml","44","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"44","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"44","0","44","44"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"44","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"87","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"87","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"87","44","87","87"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"88","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"88","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"88","44","88","88"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"44","44","44","2"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"45","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"45","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"45","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"45","3D agent-based model","45","insert code","none","45","sample_output1/output_000019.xml","45","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"45","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"45","0","45","45"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"45","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"89","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"89","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"89","45","89","89"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"90","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"90","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"90","45","90","90"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"45","45","45","2"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"46","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"46","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"46","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"46","3D agent-based model","46","insert code","none","46","sample_output1/output_000020.xml","46","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"46","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"46","0","46","46"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"46","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"91","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"91","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"91","46","91","91"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"92","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"92","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"92","46","92","92"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"46","46","46","2"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"47","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"47","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"47","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"47","3D agent-based model","47","insert code","none","47","sample_output1/output_000021.xml","47","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"47","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"47","0","47","47"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"47","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"93","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"93","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"93","47","93","93"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"94","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"94","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"94","47","94","94"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"47","47","47","2"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"48","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"48","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"48","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"48","3D agent-based model","48","insert code","none","48","sample_output1/output_000022.xml","48","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"48","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"48","0","48","48"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"48","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"95","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"95","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"95","48","95","95"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"96","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"96","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"96","48","96","96"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"48","48","48","2"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"49","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"49","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"49","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"49","3D agent-based model","49","insert code","none","49","sample_output1/output_000023.xml","49","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"49","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"49","0","49","49"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"49","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"97","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"97","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"97","49","97","97"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"98","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"98","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"98","49","98","98"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"49","49","49","2"
\.

COPY cansim."UserInformation" ("id", "Name", "Phone", "URL", "Affiliation", "Location", "email") from stdin with csv delimiter ',' quote '"';
"50","Paul Macklin","None","http://MathCancer.org","Center for Applied Molecular Medicine, Keck School of Medicine of USC","Los Angeles, CA USA","Paul.Macklin@usc.edu"
\.

COPY cansim."ProgramInformation" ("id", "Name", "Author", "URL", "Compiled", "Version", "email") from stdin with csv delimiter ',' quote '"';
"50","liver_organoid","Paul Macklin","http://MathCancer.org","today","0.00","Paul.Macklin@usc.edu"
\.

COPY cansim."reference" ("id", "URL", "note", "citation") from stdin with csv delimiter ',' quote '"';
"50","http://www.MathCancer.org/Publications.php#macklin12_jtb","DOI: 10.1016/j.jtbi.2012.02.002","P. Macklin et al., J. Theor. Biol. (2012)"
\.

COPY cansim."data_source" ("id", "description", "reference_id", "created", "notes", "ProgramInformation_id", "filename", "UserInformation_id", "last_modified") from stdin with csv delimiter ',' quote '"';
"50","3D agent-based model","50","insert code","none","50","sample_output1/output_000024.xml","50","insert code"
\.

COPY cansim."bounding_box" ("id", "upper_bounds", "lower_bounds") from stdin with csv delimiter ',' quote '"';
"50","(3200,3200,520)","(-3200,-3200,-20)"
\.

COPY cansim."metadata" ("id", "current_time", "bounding_box_id", "data_source_id") from stdin with csv delimiter ',' quote '"';
"50","0","50","50"
\.

COPY cansim."cell_line" ("id", "data_source") from stdin with csv delimiter ',' quote '"';
"50","unknown"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"99","1"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"99","769.8","1","2.58e-006","1071.16","184.8","1","4188.79","523.599","183.6","1.5","0.7"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"99","50","99","99"
\.

COPY cansim."microenvironment_vector" ("id", "oxygen") from stdin with csv delimiter ',' quote '"';
"100","0.2"
\.

COPY cansim."phenotype_parameter_vector" ("id", "duration_of_S", "Youngs_modulus", "fraction_failing_G1_checkpoint", "duration_of_G1", "duration_of_G2", "oxygen_uptake_rate_per_volume", "cell_volume", "cell_nuclear_volume", "duration_of_M", "maximum_cell_deformation", "fluid_fraction") from stdin with csv delimiter ',' quote '"';
"100","769.8","1","0.258","1.0716e+006","184.8","1","4188.79","523.599","183.6","1.5","0"
\.

COPY cansim."microenvironment_phenotype_pair" ("id", "cell_line_id", "microenvironment_vector_id", "phenotype_parameter_vector_id") from stdin with csv delimiter ',' quote '"';
"100","50","100","100"
\.

COPY cansim."MultiCell" ("id", "metadata_id", "cell_line_id", "simulation_id") from stdin with csv delimiter ',' quote '"';
"50","50","50","2"
\.

SET client_min_messages=ERROR;
VACUUM ANALYZE;

