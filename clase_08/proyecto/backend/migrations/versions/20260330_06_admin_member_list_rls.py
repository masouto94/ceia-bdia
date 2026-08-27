"""Allow tenant administrators to read their member directory under FORCE RLS."""

# pyright: reportMissingImports=false

from alembic import op

revision = "20260330_06"
down_revision = "20260330_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET ROLE project_owner")
    op.execute("""
        CREATE OR REPLACE FUNCTION current_tenant_is_admin() RETURNS boolean
        LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
            SELECT EXISTS (
                SELECT 1
                FROM membership_roles mr
                JOIN roles r ON r.id = mr.role_id AND r.tenant_id = mr.tenant_id
                WHERE mr.user_id = NULLIF(current_setting('app.user_id', true), '')::uuid
                  AND mr.tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
                  AND r.name = 'admin'
            )
        $$;
        REVOKE ALL ON FUNCTION current_tenant_is_admin() FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION current_tenant_is_admin() TO app_runtime;

        DROP POLICY memberships_tenant_isolation ON memberships;
        CREATE POLICY memberships_tenant_insert ON memberships FOR INSERT WITH CHECK (
            tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            AND NULLIF(current_setting('app.user_id', true), '') IS NOT NULL
        );
        CREATE POLICY memberships_tenant_update ON memberships FOR UPDATE USING (
            tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            AND NULLIF(current_setting('app.user_id', true), '') IS NOT NULL
        ) WITH CHECK (
            tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            AND NULLIF(current_setting('app.user_id', true), '') IS NOT NULL
        );
        CREATE POLICY memberships_tenant_delete ON memberships FOR DELETE USING (
            tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            AND NULLIF(current_setting('app.user_id', true), '') IS NOT NULL
        );
        CREATE POLICY memberships_select_admin_tenant ON memberships FOR SELECT USING (
            tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            AND current_tenant_is_admin()
        );
    """)
    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE project_owner")
    op.execute("""
        DROP POLICY memberships_select_admin_tenant ON memberships;
        DROP POLICY memberships_tenant_delete ON memberships;
        DROP POLICY memberships_tenant_update ON memberships;
        DROP POLICY memberships_tenant_insert ON memberships;
        CREATE POLICY memberships_tenant_isolation ON memberships
        USING (
            tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            AND NULLIF(current_setting('app.user_id', true), '') IS NOT NULL
        )
        WITH CHECK (
            tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            AND NULLIF(current_setting('app.user_id', true), '') IS NOT NULL
        );
        DROP FUNCTION current_tenant_is_admin();
    """)
    op.execute("RESET ROLE")
