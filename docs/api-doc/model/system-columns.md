
# Standard System Columns

ERMrest defines five special system columns with reserved column
names, types, and certain integrity constraints:

| Name | Type | Purpose |
|---|---|---|
| RID | ermrest_rid | a unique not-null identifier for each row in a table |
| RCT | ermrest_rct (domain over timestamptz) | not-null row creation time |
| RMT | ermrest_rmt (domain over timestamptz) | not-null latest row modification time |
| RCB | ermrest_rcb (domain over text) | row created by (client primary ID guid) |
| RMB | ermrest_rmb (domain over text) | latest row modified by (client primary ID guid) |

## Interface Guarantees

A client should be able to rely on the following behaviors from a compliant ERMrest catalog:

1. The five columns *must* appear in each mutable table and *must* have the column types described above.
2. Every row *must* have a unique RID value assigned at creation time and this value *must not* be recycled for use by another row in the same table.
3. Every row *must* have an immutable RCT time set during row creation.
4. Every tuple *must* have an RMT set during tuple creation. The RMT value *must* be equal to or greater than the RCT and every previously visible RMT for the same RID in the same table.
5. The RCB and RMB values *must* be comparable to the client ID space exposed by webauthn as the `id` field of the object returned from `GET /authn/session`. A NULL value may be present to indicate unknown provenance, e.g. for rows manipulated by server-side logic. However, a DBA may also substitute a distinct client ID representing an administrator or *robot* identity in such cases.
6. These system-managed columns have enforced policies described below.
   - The RID, RCT, and RMT are visible to all clients who can view a row
   - The RCB and RMB may be hidden from some clients who can view other row content
   - Clients may not supply substitute/override values for any of these columns

| Column | Forced Column ACLs | Default Column ACLs |
|---|---|---|
| RID | `{"select": ["*"], "update": [], "insert": []}` | n/a |
| RCT | `{"select": ["*"], "update": [], "insert": []}` | n/a |
| RMT | `{"select": ["*"], "update": [], "insert": []}` | n/a |
| RCB | `{"enumerate": ["*"], "update": [], "insert": []}` | `{"select": ["*"]}` |
| RMB | `{"enumerate": ["*"], "update": [], "insert": []}` | `{"select": ["*"]}` |
