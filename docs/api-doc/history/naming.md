
# History Resource Naming

The [ERMrest](https://github.com/informatics-isi-edu/ermrest) history resource names have a common root
relative to an identified catalog:

- _service_ `/catalog/` _cid_ `/history/` _from_ `,` _until_

where the components in this URL structure are:

- _service_: the ERMrest service endpoint such as `https://www.example.com/ermrest`.
- _cid_: the catalog identifier for one dataset such as `42`.
- _from_: a lower bound snapshot identifier for a history range, such as as `2NJ-6ZXW-FDFE`
- _until_: an upper bound snapshot identifier for a history range, such as `2PY-1MC0-VMZ2`

In some history resources, either or both of _from_ and _until_ MAY be
the empty string in order to express a partially bound
interval. However, for history amendment, the effective _until_
boundary MUST be clamped by the implementation to only affect *dead*
storage. In other words, history amendment operation cannot affect
*live* catalog state.

## History Range

The historical range of the catalog is named as:

- _service_ `/catalog/` _cid_ `/history/,`

This is the root history with neither upper or lower bound specified in
the URL.

## Historical ACLs

Historical ACL resources are named as:

- _service_ `/catalog/` _cid_ `/history/` _from_ `,` _until_ `/acl`
- _service_ `/catalog/` _cid_ `/history/` _from_ `,` _until_ `/acl/` _RID_

The first form names the set of catalog ACLs, while the second form
names a set of model-element ACLs for a specific subject identified by
its static `RID` property. Subjects identified by _RID_ may be:

- One schema
- One table
- One column
- One foreign key

## Historical ACL Bindings

Historical ACL binding resources are named as:

- _service_ `/catalog/` _cid_ `/history/` _from_ `,` _until_ `/acl_binding/` _RID_

This URL names a set of model-element ACL bindings for a specific subject
identified by its static `RID` property. Subjects identified by _RID_ may
be:

- One table
- One column
- One foreign key

## Historical Annotations

Historical annotation resources are named as:

- _service_ `/catalog/` _cid_ `/history/` _from_ `,` _until_ `/annotation`
- _service_ `/catalog/` _cid_ `/history/` _from_ `,` _until_ `/annotation/` _RID_

The first form names the set of catalog annotations, while the second
form names a set of model-element annotations for a specific subject
identified by its static `RID` property. Subjects identified by _RID_ may
be:

- One schema
- One table
- One column
- One key
- One foreign key

## Historical Attributes

Historical attribute resources are named as:

- _service_ `/catalog/` _cid_ `/history/` _from_ `,` _until_ `/attribute/` _cRID_
- _service_ `/catalog/` _cid_ `/history/` _from_ `,` _until_ `/attribute/` _cRID_ `/` _fRID_ `=` _val_

These URLs name a set of attributes (values) bound to the column
identified by _cRID_ which is the static `RID` property of one column
definition in the model. The first form names attributes for **all**
entity snapshots within the historical interval. The second form is
further restricted to only entities matching a simple value test
where another filtering column identified by _fRID_ is bound to
the provided static value _val_.

The second, filtering, form of historical attribute URL supports
several idioms:

1. By using an _fRID_ corresponding to the `RID` column and a _val_
   corresponding to one record ID, any column of a specific entity
   can be addressed.
2. By using an _fRID_ and _cRID_ corresponding to the `RID` of a data
   column, all entities with the same _val_ can be addressed.

