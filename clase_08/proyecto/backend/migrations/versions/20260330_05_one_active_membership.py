"""Enforce the MVP's one-active-membership-per-user tenant model."""

# pyright: reportMissingImports=false

from alembic import op

revision = "20260330_05"
down_revision = "20260330_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET ROLE project_owner")
    op.execute("""
        CREATE UNIQUE INDEX memberships_one_active_user ON memberships (user_id) WHERE active;
        CREATE OR REPLACE FUNCTION sole_active_membership_tenant(p_user uuid) RETURNS uuid
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
        DECLARE membership_count integer; tenant uuid;
        BEGIN
            PERFORM set_config('app.user_id', p_user::text, true);
            SELECT count(*) INTO membership_count FROM memberships WHERE user_id = p_user AND active;
            IF membership_count != 1 THEN RETURN NULL; END IF;
            SELECT tenant_id INTO tenant FROM memberships WHERE user_id = p_user AND active;
            RETURN tenant;
        END;
        $$;
        REVOKE ALL ON FUNCTION sole_active_membership_tenant(uuid) FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION sole_active_membership_tenant(uuid) TO app_runtime;
    """)
    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE project_owner")
    op.execute("DROP FUNCTION sole_active_membership_tenant(uuid)")
    op.execute("DROP INDEX memberships_one_active_user")
    op.execute("RESET ROLE")
