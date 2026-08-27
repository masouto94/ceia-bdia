"""Add immutable tenant/platform identity scope and scoped relationship integrity."""

from alembic import op

revision = "20260330_16"
down_revision = "20260330_15"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET ROLE project_owner")
    op.execute("""
      ALTER TABLE users ADD COLUMN account_scope varchar(16) NOT NULL DEFAULT 'tenant';
      ALTER TABLE users ADD CONSTRAINT users_account_scope_check CHECK (account_scope IN ('tenant', 'platform'));
      ALTER TABLE users ADD CONSTRAINT users_scope_key UNIQUE (id, account_scope);
      CREATE FUNCTION users_account_scope_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN IF NEW.account_scope <> OLD.account_scope THEN RAISE EXCEPTION 'account scope is immutable'; END IF; RETURN NEW; END $$;
      CREATE TRIGGER users_account_scope_immutable BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION users_account_scope_immutable();
      ALTER TABLE memberships ADD COLUMN account_scope varchar(16) NOT NULL DEFAULT 'tenant' CHECK (account_scope = 'tenant');
      ALTER TABLE memberships ADD CONSTRAINT memberships_tenant_identity FOREIGN KEY (user_id, account_scope) REFERENCES users(id, account_scope);
      CREATE TABLE platform_admins (user_id uuid PRIMARY KEY, account_scope varchar(16) NOT NULL DEFAULT 'platform' CHECK (account_scope = 'platform'), enabled boolean NOT NULL DEFAULT true,
        CONSTRAINT platform_admins_platform_identity FOREIGN KEY (user_id, account_scope) REFERENCES users(id, account_scope));
      ALTER TABLE sessions ADD COLUMN account_scope varchar(16) NOT NULL DEFAULT 'tenant';
      ALTER TABLE sessions ADD CONSTRAINT sessions_scope_shape CHECK ((account_scope = 'tenant' AND tenant_id IS NOT NULL) OR (account_scope = 'platform' AND tenant_id IS NULL));
      ALTER TABLE sessions ADD CONSTRAINT sessions_scoped_identity FOREIGN KEY (user_id, account_scope) REFERENCES users(id, account_scope);
      -- exact function ownership transfer is deferred until this change creates those functions.
      -- A temporary CREATE grant without a transfer would provide no security value.
    """)
    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE project_owner")
    op.execute("""
      ALTER TABLE sessions DROP CONSTRAINT sessions_scoped_identity, DROP CONSTRAINT sessions_scope_shape, DROP COLUMN account_scope;
      DROP TABLE platform_admins;
      ALTER TABLE memberships DROP CONSTRAINT memberships_tenant_identity, DROP COLUMN account_scope;
      DROP TRIGGER users_account_scope_immutable ON users;
      DROP FUNCTION users_account_scope_immutable();
      ALTER TABLE users DROP CONSTRAINT users_scope_key, DROP CONSTRAINT users_account_scope_check, DROP COLUMN account_scope;
    """)
    op.execute("RESET ROLE")
