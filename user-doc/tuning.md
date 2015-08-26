
# Performance Tuning

There are a few things you can do to improve performance of your new ERMrest installation.
- Tune Apache HTTPD to allow better reuse of TLS connections
  - `KeepAlive On`
  - `MaxKeepAliveRequests 1000`
  - `KeepAliveTimeout 30`
- Tune Postgres for your server capacity and workload
  - `shared_buffers = 1GB` ?
  - `work_mem = 128MB` ?
  - `maintenance_work_mem = 128MB` ?
  - `effective_cache_size = 8 GB` (your typical file buffer cache size available to Postgres...)
  - `from_collapse_limit = 500` (stronger optimization of complex queries)
  - `join_collapse_limit = 500` (stronger optimization of complex queries)
  - `geqo_threshold = 10` (may affect planner latency)
  - `geqo_effort = 5` (May affect planner latency)
- Vacuum databases to allow better query planner optimization
  - Run `VACUUM ANALYZE` on `ermrest` database that holds registry of catalogs
  - Run `VACUUM ANALYZE` on each `_ermrest_` _RANDOMKEY_ database that holds catalog-specific data
- Create indices to accelerate text-search and regular expression operators. Without these indices, all text-search will be brute-force and visit every row of the filtered table to evaluate the requested text patterns. We provide a command-line utility to assist in creating (or recreating) the appropriate value indices which will accelerate the two free text search modes. It takes a catalog ID number as first argument and one or more schema names as subsequent arguments; it will create indices on all tables in each schema specified on the command-line:
    - `ermrest-freetext-indices 1 public myschema1`
