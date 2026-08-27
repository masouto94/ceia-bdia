"""Protect reversible membership updates and audit their state transitions."""

# pyright: reportMissingImports=false

from alembic import op

revision = "20260330_12"
down_revision = "20260330_11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET ROLE project_owner")
    op.execute("""
        ALTER TABLE audit_events
            ADD COLUMN IF NOT EXISTS metadata jsonb NOT NULL DEFAULT '{}'::jsonb;

        CREATE OR REPLACE FUNCTION membership_update_protect_last_admin() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
        DECLARE active_admins integer;
        BEGIN
            PERFORM pg_advisory_xact_lock(hashtextextended(NEW.tenant_id::text, 0));
            IF TG_TABLE_NAME = 'memberships' THEN
                IF OLD.active AND NOT NEW.active AND EXISTS (
                    SELECT 1
                    FROM membership_roles mr
                    JOIN roles r ON r.id = mr.role_id AND r.tenant_id = mr.tenant_id
                    WHERE mr.tenant_id = OLD.tenant_id AND mr.user_id = OLD.user_id AND r.name = 'admin'
                ) THEN
                    SELECT count(*) INTO active_admins
                    FROM memberships m
                    JOIN membership_roles mr ON mr.tenant_id = m.tenant_id AND mr.user_id = m.user_id
                    JOIN roles r ON r.id = mr.role_id AND r.tenant_id = mr.tenant_id
                    WHERE m.tenant_id = OLD.tenant_id AND m.active AND r.name = 'admin';
                    IF active_admins <= 1 THEN
                        RAISE EXCEPTION 'tenant must retain an active admin' USING ERRCODE = '23514';
                    END IF;
                END IF;
            ELSIF TG_TABLE_NAME = 'membership_roles' THEN
                IF EXISTS (
                    SELECT 1 FROM roles WHERE id = OLD.role_id AND tenant_id = OLD.tenant_id AND name = 'admin'
                ) AND NOT EXISTS (
                    SELECT 1 FROM roles WHERE id = NEW.role_id AND tenant_id = NEW.tenant_id AND name = 'admin'
                ) AND EXISTS (
                    SELECT 1 FROM memberships WHERE tenant_id = OLD.tenant_id AND user_id = OLD.user_id AND active
                ) THEN
                    SELECT count(*) INTO active_admins
                    FROM memberships m
                    JOIN membership_roles mr ON mr.tenant_id = m.tenant_id AND mr.user_id = m.user_id
                    JOIN roles r ON r.id = mr.role_id AND r.tenant_id = mr.tenant_id
                    WHERE m.tenant_id = OLD.tenant_id AND m.active AND r.name = 'admin';
                    IF active_admins <= 1 THEN
                        RAISE EXCEPTION 'tenant must retain an active admin' USING ERRCODE = '23514';
                    END IF;
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$;
        REVOKE ALL ON FUNCTION membership_update_protect_last_admin() FROM PUBLIC;

        CREATE TRIGGER memberships_protect_last_admin
            BEFORE UPDATE OF active ON memberships
            FOR EACH ROW WHEN (OLD.active IS DISTINCT FROM NEW.active)
            EXECUTE FUNCTION membership_update_protect_last_admin();
        CREATE TRIGGER membership_roles_protect_last_admin
            BEFORE UPDATE OF role_id ON membership_roles
            FOR EACH ROW WHEN (OLD.role_id IS DISTINCT FROM NEW.role_id)
            EXECUTE FUNCTION membership_update_protect_last_admin();
    """)
    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE project_owner")
    op.execute("""
        DROP TRIGGER membership_roles_protect_last_admin ON membership_roles;
        DROP TRIGGER memberships_protect_last_admin ON memberships;
        DROP FUNCTION membership_update_protect_last_admin();
        ALTER TABLE audit_events DROP COLUMN metadata;
    """)
    op.execute("RESET ROLE")
