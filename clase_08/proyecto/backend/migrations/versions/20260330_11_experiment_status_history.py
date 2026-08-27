"""Add append-only, tenant-isolated experiment status transition history."""

from alembic import op  # pyright: ignore[reportMissingImports]

revision = "20260330_11"
down_revision = "20260330_10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET ROLE project_owner")
    op.execute("""
        CREATE TABLE experiment_status_transitions (
            id uuid PRIMARY KEY,
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            experiment_id uuid NOT NULL,
            previous_status varchar(16) NOT NULL CHECK (previous_status IN ('draft','running','completed','failed')),
            next_status varchar(16) NOT NULL CHECK (next_status IN ('draft','running','completed','failed')),
            actor_id uuid NOT NULL,
            occurred_at timestamptz NOT NULL DEFAULT now(),
            reason varchar(1000),
            FOREIGN KEY (tenant_id,experiment_id) REFERENCES experiments(tenant_id,id),
            FOREIGN KEY (tenant_id,actor_id) REFERENCES memberships(tenant_id,user_id),
            CHECK (previous_status <> next_status)
        );
        CREATE INDEX experiment_status_transitions_experiment_occurred_idx
            ON experiment_status_transitions (tenant_id,experiment_id,occurred_at,id);
        ALTER TABLE experiment_status_transitions ENABLE ROW LEVEL SECURITY;
        ALTER TABLE experiment_status_transitions FORCE ROW LEVEL SECURITY;
        CREATE POLICY experiment_status_transitions_tenant_isolation ON experiment_status_transitions
            USING (
                tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
                AND NULLIF(current_setting('app.user_id', true), '') IS NOT NULL
            )
            WITH CHECK (
                tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
                AND NULLIF(current_setting('app.user_id', true), '') IS NOT NULL
            );
        CREATE TRIGGER experiment_status_transitions_append_only
            BEFORE UPDATE OR DELETE ON experiment_status_transitions
            FOR EACH ROW EXECUTE FUNCTION reject_historical_mutation();
        GRANT SELECT, INSERT ON experiment_status_transitions TO app_runtime;
        REVOKE UPDATE, DELETE ON experiment_status_transitions FROM app_runtime;
    """)
    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE project_owner")
    op.execute("DROP TABLE experiment_status_transitions")
    op.execute("RESET ROLE")
