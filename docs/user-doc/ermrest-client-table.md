
# Client table

The `ERMrest_Client` table in the `public` schema is created
automatically in newly created catalogs and is also added to existing
catalogs when `ermrest-deploy` upgrades a system.

The rows of this table are automatically maintained by ERMrest,
recording basic client information as each new authenticated client is
encountered. No attempt is made to purge records.

At time of writing, this contains these columns:

- `ID`: The `text` unique identifier of the client (possibly a URI).
- `Display_Name`: A more human-readable `text` representation of the
  client identity (possibly a domain-qualified username which looks
  similar to an email address).
- `Full_Name`: The human-readable `text` name of the client.
- `Email`: A `text` email address to contact the client.
- `Client_Object`: A `jsonb` object containing client metadata.

The `ID` field is the primary key and cannot be NULL.  Each of the
other fields MAY be NULL, depending on what information is available
from the configured webauthn2 identity provider.

The set of columns is a pragmatic choice, intended to reflect stable
client information which may be helpful when interpreting provenance
metadata and which is usually present in deployed systems. For
performance reasons, we do not wish to have high-resolution temporal
information such as access or expiration times, as these would cause
too many database updates in what are otherwise read-only ERMrest
requests.

## Extensibility and Localization

The DBA is allowed to add additional human-managed columns to the
`ERMrest_Client` table. These columns MUST have a properly configured
default value and/or allow NULL values so that ERMrest can insert
newly discovered clients while only configuring the subset of columns
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

1. Change the set of properties in the `Client_Object` field
2. Extend the list of client metadata columns
   - Include additional columns when creating the table
   - Add columns to existing table instances in ermrest-deploy
3. Shorten the list of client metadata columns
   - Omit obsolete columns when creating the table
   - Ignore obsolete columns when operating on existing tables

The DBA is also allowed to mutate the `ERMrest_Client` table contents
to import knowledge about clients who have not yet been discovered by
the ERMrest service logic. However, when ERMrest encounters a client
corresponding to such an entry, it will automatically mutate the
columns it understands to reflect all the latest client metadata
obtained from the webauthn identity providers.

Therefore, it is not recommended that users be given access to modify
those fields, as they will become confused or frustrated when values
revert to the webauthn-established values.

Likewise, the DBA is allowed to purge stale entries from the
`ERMrest_Client` table, but catalog access by a purged client will
automatically reinsert their information.  If a DBA wishes to hide
certain clients' information from the userbase, a dynamic ACL binding
should be defined to control access to individual rows while allowing
corresponding rows to be present for each active client.
