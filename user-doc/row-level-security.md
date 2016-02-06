
# Row-Level Authorization

With ERMrest, all web requests execute under the `ermrest` daemon
account using its own PostgreSQL identity. Therefore, policy features
using PostgreSQL roles are insufficient to provide differentiated
privileges for different web clients sharing an ERMrest database
catalog.

Row-level security is useful because it allows arbitrary boolean
expressions in the policy statements and rewrites these into all
queries executed against the database. We can grant access to the
`ermrest` user only when additional data constraints are met that are
able to consider:

  - The content of existing rows for SELECT, UPDATE, and DELETE.
  - The new or replacement row content for INSERT and UPDATE.
  - The value of `(SELECT _ermrest.current_client())` scalar subquery of type `text`.
  - The value of `(SELECT _ermrest.current_attributes())` scalar subquery of type `text[]`.
  - Other scalar subqueries which MAY lookup indirect values from other tables to find links between the affected row content and the current ermrest client or attributes context.

## Considerations

Row-level security affects all access to tables for which it is
enabled. Backup database dumps could be incomplete unless taken by a
PostgreSQL superuser.

## Instructions and Examples

1. Upgrade your postgres to 9.5

2. Have latest ERMrest master code deployed (as of 2016-02-05 16:30 PST).

3. Adjust ownership on the table or tables we will restrict with row-level access control.  The owner MUST NOT be the ermrest daemon as ownership provides implicit access to all table rows.  As an example, assuming a local dev/DBA psql account such as `karlcz`:

    BEGIN;
    ALTER TABLE my_example OWNER TO karlcz;
    GRANT ALL ON TABLE my_example TO ermrest;
    COMMIT;

4. Enable row-level security:

    ALTER TABLE my_example ENABLE ROW SECURITY;

   At this point, ERMrest should still work (a smart thing to test) but data operations on this table will fail as the default policies do not allow any operations on any row data!  Go back to normal with:

    ALTER TABLE my_example DISABLE ROW SECURITY;

5. Create row-level policies to restore all access:

    CREATE POLICY select_all ON my_example FOR SELECT USING (True);
    CREATE POLICY delete_all ON my_example FOR DELETE USING (True);
    CREATE POLICY insert_all ON my_example FOR INSERT WITH CHECK (True);
    CREATE POLICY update_all ON my_example FOR UPDATE USING (True) WITH CHECK (True);

   At this point, all data access is possible again.  In general, the `USING (expr)` part must evaluate to true for existing rows to be accessed while `WITH CHECK (expr)` part must evaluate true for new row content to be applied.

6. Drop policies to limit it again:

    DROP POLICY update_all ON my_example;
    DROP POLICY insert_all ON my_example;
    DROP POLICY delete_all ON my_example;
    DROP POLICY select_all ON my_example;

7. Make policies that check against webauthn context but not row data:

    CREATE POLICY select_group
    ON my_example
	FOR SELECT
	USING ( 'g:f69e0a7a-99c6-11e3-95f6-12313809f035' = ANY ((SELECT _ermrest.current_attributes())) );
	
	CREATE POLICY select_user
	ON my_example
	FOR SELECT
	USING ( 'karlcz' = (SELECT _ermrest.current_client()) );

8. Drop those policies:

    DROP POLICY select_group ON my_example;
	DROP POLICY select_user ON my_example;

9. Consider row-data in more complete example:

    -- allow members of group to insert but enforce provenance of owner column
    CREATE POLICY insert_group
    ON my_example
	FOR INSERT
	WITH CHECK (
	  'g:f69e0a7a-99c6-11e3-95f6-12313809f035' = ANY ((SELECT _ermrest.current_attributes()))
      AND owner = (SELECT _ermrest.current_owner())
    );

	-- owner can update his own rows
	-- but continue to enforce provenance of owner column too
	CREATE POLICY update_owner
    ON my_example
	FOR UPDATE
	USING ( owner = (SELECT _ermrest.current_owner()) )
	WITH CHECK ( owner = (SELECT _ermrest.current_owner()) ) ;

	-- owner can delete his own rows
	CREATE POLICY delete_owner
	ON my_example
	FOR DELETE
	USING ( owner = (SELECT _ermrest.current_owner()) );

	-- owner can read
	-- as can members of groups in ACL
	CREATE POLICY select_owner_acl
	ON my_example
	FOR SELECT
	USING (
	  owner = (SELECT _ermrest.current_owner())
      OR acl && (SELECT _ermrest.current_attributes())
    );

