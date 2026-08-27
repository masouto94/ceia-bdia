"""Add opaque identity, recovery, membership-role, and bounded audit storage."""

# pyright: reportMissingImports=false

from alembic import op

revision = "20260330_02"
down_revision = "20260330_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET ROLE project_owner")
    op.execute("""
        CREATE TABLE sessions (id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES users(id), token_hash varchar(64) UNIQUE NOT NULL, csrf_hash varchar(64) NOT NULL, tenant_id uuid REFERENCES tenants(id), expires_at timestamptz NOT NULL, revoked_at timestamptz);
        CREATE TABLE recovery_tokens (id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES users(id), token_hash varchar(64) UNIQUE NOT NULL, expires_at timestamptz NOT NULL, used_at timestamptz);
        CREATE TABLE membership_roles (tenant_id uuid NOT NULL REFERENCES tenants(id), user_id uuid NOT NULL REFERENCES users(id), role_id uuid NOT NULL REFERENCES roles(id), PRIMARY KEY (tenant_id, user_id));
        CREATE TABLE audit_events (id uuid PRIMARY KEY, actor_id uuid REFERENCES users(id), tenant_id uuid REFERENCES tenants(id), action varchar(64) NOT NULL, outcome varchar(16) NOT NULL, resource varchar(120), created_at timestamptz NOT NULL DEFAULT now());
        ALTER TABLE membership_roles ENABLE ROW LEVEL SECURITY; ALTER TABLE membership_roles FORCE ROW LEVEL SECURITY;
        CREATE POLICY membership_roles_tenant_isolation ON membership_roles USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid AND NULLIF(current_setting('app.user_id', true), '') IS NOT NULL) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid AND NULLIF(current_setting('app.user_id', true), '') IS NOT NULL);
        CREATE OR REPLACE FUNCTION verified_membership(p_user uuid, p_tenant uuid) RETURNS boolean LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$ SELECT EXISTS (SELECT 1 FROM memberships WHERE user_id = p_user AND tenant_id = p_tenant AND active) $$;
        REVOKE ALL ON FUNCTION verified_membership(uuid, uuid) FROM PUBLIC; GRANT EXECUTE ON FUNCTION verified_membership(uuid, uuid) TO app_runtime;
        GRANT SELECT, INSERT, UPDATE ON sessions, recovery_tokens, audit_events TO app_runtime;
        GRANT SELECT, INSERT, UPDATE ON membership_roles TO app_runtime;
    """)
    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE project_owner")
    op.execute("DROP FUNCTION verified_membership(uuid, uuid); DROP TABLE audit_events; DROP TABLE membership_roles; DROP TABLE recovery_tokens; DROP TABLE sessions")
    op.execute("RESET ROLE")
