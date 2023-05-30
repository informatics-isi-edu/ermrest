
# RID Lease table

The `ERMrest_RID_Lease` table in the `public` schema is created
automatically in newly created catalogs and is also added to existing
catalogs when `ermrest-deploy` upgrades a system.

This table supports an _optional_ RID pre-allocation scheme to allow
clients to obtain RIDs for use with the `?nondefaults=RID` mode of the
POST `/entity/` API. This allows a two-phase process for clients to
create regular table records with a known RID, in case they wish to
coordinate naming of external resources created _before_ a table
record is recorded:

1. Client POSTs to /entity/public:ERMrest_RID_Lease to lease a RID.
2. Client names external resources using leased RID.
3. Client POSTs to /entity/S:T?nondefaults=RID to claim leased RID.

When the real record is created, the service will atomically remove
the lease record at the same time it introduces the claimed RID into
an application-specific record.

We refer to these pre-allocated RIDs as "leases" because a service
operator MAY choose to expire unclaimed leases after some reasonable
period of time. Future enhancements may introduce more management
controls for such lease expiration, but for now it is an out of band
characteristic of individual service instances.

At time of writing, the lease table definition contains these columns:

- `RID`: Normal system column. Also represents leased RID.
- `RCB`: Normal system column. Also represents lessee.
- `RCT`: Normal system column. Also represents beginning of lease.
- `RMB`: Normal system column.
- `RMT`: Normal system column.
- `ID`: An _optional_ correlation key unique to the lessee, i.e. the combination of (`RCT', `ID`) forms a unique binary key for the lease.

The optional ID allows the client to supply a client-meaningful correlation key to each lease. This may help with error-handling or stat-recovery mechanisms in a client acquiring leases for ongoing tasks which will produce resources named by RID. However, a naive client can just leave this field NULL and generate multiple leases without recording any explicit correlation key.

## Access policy

When the table is introduced into a catalog, it is assigned a
conservative default policy.  However, its policy can and should be
managed just like any other table in ERMrest. See below for more
information about the default policy and considerations when
customizing access rules.

### Default policy

The default policy has these static ACLs:

{
  "insert": null,
  "select": [],
  "update": [],
  "delete": []
}

This means it might inherit `insert` permissions from the schema or
catalog level, but it restricts other general access.

Additionally, the following dynamic ACL binding is set at the table
level to allow clients general access to their own leases:

```
{
  "lessee_access": {
    "types": ["select", "update", "delete"],
    "projection": ["RCB"],
    "projection_type": "acl",
    "scope_acl": ["*"]
  }
}
```

### Minimum access

At bare minimum, `insert` access is required to allow use of the RID
leasing feature.

There is only a minor denial-of-service risk to allowing clients to
create lease records. They could generate many leases in a short
period of time to consume server IO capacity, or accumulate many
leases to consume more storate resources. However, leases are of
trivial cost compared to any normal application table that has system
columns and other application columns. Thus, there is _minimal
marginal risk_ to enabling leasing for clients who already have
insertion rights on any application table.

### Client isolation concerns

A client may benefit from additional rights with respect to their leases:

- `select` access allows for state-recovery, where a client can retrieve their existing lease states.
- `update` access allows for synchronization, where a client updates their correlation keys.
- `delete` access allows for lease termination, where a client aborts without claiming the RID in a new record.

However, all of these operations could be hazardous if granted broadly to all rows:

- `select` could expose confidential information about other clients' leasing behaviors or correlation keys.
- `update` could allow corruption of other clients' correlation keys.
- `delete` could allow hijacking of RIDs being used by a client to name external resources.

All of these concerns can be best addressed with the default ACL
binding granting row-level `select`, `update`, and `delete` rights to
the client matching the row's `RCB` column. This isolates each
client's view of the lease table.

## Interface Guarantees

ERMrest only requires the core system columns to be present in order
to support claiming of RID leases during POST request processing on
other tables. The claiming logic is tied to the `RCB` and `RID`
columns to identify the lessee and the leased RID, respectively.

Any deployment SHOULD provide the `ID` column and binary key
constraint as described above, as a courtesy to any clients allowed
access to this feature. Otherwise, interoperability problems will be
introduced.

Future revisions MAY introduce an interpretation of `RCT` and/or `RMT`
timestamps for use with automatic lease expiration rules.

When querying the lease table, a client SHOULD include an `RCB=`
_client ID_ filter to find their own leases. They should not rely on a
particular server implementing total lease isolation, and so should
not expect that implicit filtering will occur to hide leases of other
clients.

