
# ERMrest History Operations

The [ERMrest](http://github.com/informatics-isi-edu/ermrest) history operations manipulate history storage in the catalog.

## History Range Discovery

A simple GET request can discover the shape of history:

    GET /ermrest/catalog/N/history/,
    Host: www.example.com

a successful response:

    HTTP/1.1 200 OK
    Content-Type: application/json
    
    {
      "amendver": null,
      "snaprange": [
        "2PV-1QEH-93Z6", 
        "2PX-WS30-E58W"
      ]
    }

The two values in the `snaprange` field represent an earliest and
latest snapshot identifier known to the catalog. The `amendver` will
indicate the latest amendment identifier for this range, if any
history mutation has occurred. A `null` value for `amendver` indicates
that the snapshots have not been modified administratively.

A narrower boundary can also be queried to find out whether that particular
range of history has been amended:

    GET /ermrest/catalog/N/history/2PV-1QEH-FFFF,2PX-WS30-0000
    Host: www.example.com
	
this will return a similar response but the `snaprange` and `amendver` fields
will only describe history within the requested range:

    HTTP/1.1 200 OK
    Content-Type: application/json
    
    {
      "amendver": null, 
      "snaprange": [
        "2PV-1QEM-D9T0", 
        "2PX-WS1Y-R5H0"
      ]
    }

## History Range Truncation

A single, bulk request can irreversibly truncate catalog history:

    DELETE /ermrest/catalog/N/history/,2PV-1QEH-93Z6
    Host: www.example.com

All historical model and data content with a death time before or
equal to the provided _until_ boundary, `2Pv-1QEH-93Z6` in this
example, time will be discarded. This can be used to implement a data
retention horizon and to reclaim storage resources.

## Amend Historical ACLs

A collection of ACL resources can be mutated over a *time span*:

    PUT /ermrest/catalog/N/history/2PV-1QEH-93Z6,2PX-WS30-E58W/acl
    Host: www.example.com
    Content-Type: application/json
    
    {"owner": ["admin1", "admin2"], "select": ["*"]}

In this example, the catalog-level ACLs applicable to all snapshots
within the given range _from_ to _until_ are set to the input value.
Using the subject-qualified URL format for individual model elements,
ACLs on other parts of the model may also be amended:

    PUT /ermrest/catalog/N/history/2PV-1QEH-93Z6,2PX-WS30-E58W/acl/mRID
    Host: www.example.com
    Content-Type: application/json
    
    {
      "owner": ["admin1", "admin2"],
      "select": ["*"]
    }

## Amend Historical ACL Bindings

A collection of ACL binding resources can be mutated over a *time span*:

    PUT /ermrest/catalog/N/history/2PV-1QEH-93Z6,2PX-WS30-E58W/acl_binding/mRID
    Host: www.example.com
    Content-Type: application/json
    
    {
      "My Binding": {
        "types": ["owner"], 
        "projection": "RCB",
        "projection_type": "acl",
        "scope_acl": ["registered-users-group"]
      }
	}

The effect of this operation will be to destructively overwrite the
effective ACL bindings for all revisions whose lifetimes are wholly
enclosed within the time span.

## Amend Historical Annotations

A collection of annotation resources can be mutated over a *time span*:

    PUT /ermrest/catalog/N/history/2PV-1QEH-93Z6,2PX-WS30-E58W/annotation
    Host: www.example.com
    Content-Type: application/json
    
    {
      "tag:misd.isi.edu,2015:display": {"show_nulls": true},
      "tag:isrd.isi.edu,2018:indexing-preferences": {"btree": true}
    }

The effect of this operation will be to destructively overwrite the
effective annotations for all revisions whose lifetimes are wholly
enclosed within the time span. The preceding example amends catalog-level
annotations, but annotations may also be amended on individual model
elements in the history:

    PUT /ermrest/catalog/N/history/2PV-1QEH-93Z6,2PX-WS30-E58W/annotation/mRID
    Host: www.example.com
    Content-Type: application/json
    
    {
      "tag:misd.isi.edu,2015:display": {"show_nulls": true},
      "tag:isrd.isi.edu,2018:indexing-preferences": {"btree": true}
    }


## Redact Historical Attributes

Specific attributes can be redacted over a *time span*:

    DELETE /ermrest/catalog/N/history/2PV-1QEH-93Z6,2PX-WS30-E58W/attribute/cRID
    Host: www.example.com

The effect of this operation is to redact (set NULL) all values of the
column whose RID is _CRID_ for all tuple revisions whose lifetimes are
wholly enclosed within the time span. The enclosing table is implicit
because _CRID_ uniquely identifies one column within the whole model.

More selective redaction can be made by a limited filter syntax:

    DELETE /ermrest/catalog/N/history/2PV-1QEH-93Z6,2PX-WS30-E58W/attribute/cRID/fRID=X
    Host: www.example.com

Here, only tuples with the given filter column whose RID is _fRID_
matches a given value _X_ are redacted.  More rich filtering syntax
may be considered in future enhancements to ERMrest. This syntax is
sufficient to target one row by its actual `RID` or all rows with a
certain *bad value* _X_ in the column being redacted.

