
# Group table

The `ERMrest_Group` table in the `public` schema is created
automatically in newly created catalogs and is also added to existing
catalogs when `ermrest-deploy` upgrades a system.

The rows of this table are automatically maintained by ERMrest,
recording basic group (attribute) information as each 
authenticated client is encountered. No attempt is made to purge
records.

At time of writing, this contains these columns:

- `ID`: The `text` unique identifier of the group (possibly a URI).
- `URL`: A web URL for viewing or managing the group (if available).
- `Display_Name`: A more human-readable `text` identifier for the
  group.
- `Description`: A human-readable `text` description of the group.

The `ID` field is the primary key and cannot be NULL.  Each of the
other fields MAY be NULL, depending on what information is available
from the configured webauthn2 attribute provider.

The set of columns is a pragmatic choice, intended to reflect stable
group information which may be helpful when interpreting provenance
metadata or policies present in deployed systems.

## Extensibility and Localization

The DBA is allowed to add additional human-managed columns to the
`ERMrest_Group` table. These columns MUST have a properly configured
default value and/or allow NULL values so that ERMrest can insert
newly discovered groups while only configuring the subset of columns
which it understands.  Failure to do so may render the service
inoperative until this problem is rectified.

The DBA is also allowed to customize access control policies for
this table. It is impossible to hide the table from catalog owners,
but less privileged users need not be aware of it.

## Conservative default policy

When the table is introduced into a catalog, it is assigned a
default table-level policy:

    {
      "insert": [],
      "update": [],
      "delete": [],
      "select": [],
      "enumerate": []
    }

This effectively hides the table from clients who are not owners of
the whole catalog or the `public` schema.  A catalog administrator MAY
subsequently modify these policies to make content visible to clients
where appropriate.

## Interface Guarantees

The set of columns included in the table are based on the currently
known information from webauthn.  ERMrest requires the columns to be
present for correct function.

A future version of ERMrest MAY:

1. Extend the list of group metadata columns
   - Include additional columns when creating the table
   - Add columns to existing table instances in ermrest-deploy
2. Shorten the list of group metadata columns
   - Omit obsolete columns when creating the table
   - Ignore obsolete columns when operating on existing tables

The DBA is also allowed to mutate the `ERMrest_Group` table contents
to import knowledge about groups which have not yet been discovered by
the ERMrest service logic. However, when ERMrest encounters a group
corresponding to such an entry, it will automatically mutate the
columns it understands to reflect all the latest metadata
obtained from the webauthn attribute providers.

Therefore, it is not recommended that users be given access to modify
those fields, as they will become confused or frustrated when values
revert to the webauthn-established values.

Likewise, the DBA is allowed to purge stale entries from the
`ERMrest_Group` table, but catalog access by a purged group member will
automatically reinsert group information.  If a DBA wishes to hide
certain groups' information from the userbase, a dynamic ACL binding
should be defined to control access to individual rows while allowing
corresponding rows to be present for each active client and their
own groups.
