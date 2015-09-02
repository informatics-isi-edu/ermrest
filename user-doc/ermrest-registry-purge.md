# ermrest-registry-purge

ermrest-registry-purge -- purge ERMrest catalogs

## Synopsis

```
ermrest-registry-purge [-dfh] [-a|i INTERVAL] [-z DIR]
```

## Description

ermrest-registry-purge purges ERMrest catalogs. The user who executes this
command must be superuser. The command will run database utilities as the
_ermrest_ daemon user to drop databases and remove entries from the ERMrest
registry of catalogs. Optionally, it will force disconnect of client
connections and/or archive databases before dropping them. By default, it
purges any deleted database, but it includes options to purge all catalogs
or to purge only catalogs that are at least as old as a given age.

## Options

ermrest-registry-purge accepts the following command-line arguments: 

`-a`

    Purges all catalogs, not just those that have been deleted.

`-d`

    Dry run. Identify but do not purge catalogs that match selection criteria.

`-f`

    Force disconnect of clients before attempting purges.

`-h`

    Show help about this command and exit.

`-i INTERVAL`

    Only purge catalogs that were deleted prior to _INTERVAL_, where _INTERVAL_
    is a valid PostgreSQL timestamp interval such as '1 week', '2 years',
    '24 hours', '31 days', etc.

`-q`

    Executes quietly. By default, the command prints a line for each catalog
    that is being purged.

`-z DIR`

    Archive the catalog as a file in _DIR_. The archive filename includes the 
    catalog identifier, the database name, and the seconds since epoch. The
    file contains the complete _SQL_ commands required to recreate the catalog.
    The format of the archive file is _gzip_ compressed plain text.

## Exit Status

ermrest-registry-purge returns 0 to the shell if it finished normally or 1 if a
usage error occurs.

## Examples

To purge all deleted catalogs:

```
# ermrest-registry-purge
```

To purge all deleted catalogs that were deleted at least 7 days ago:

```
# ermrest-registry-purge -i '7 days'
```

To purge all deleted catalogs that were deleted at least 1 year ago and archive
them to /home/ermrest/backups:

```
# ermrest-registry-purge -i '1 year' -z /home/ermrest/backups
```

To purge all deleted catalogs that were deleted at least 1 hour ago and
force client disconnect:

```
# ermrest-registry-purge -f -i '1 hour'
```

To purge all catalogs, even those that have not been deleted, and force
disconnect:

```
# ermrest-registry-purge -a -f
```

To do a _dry run_ that will _not_ purge any catalogs:
 
```
# ermrest-registry-purge -d
```
