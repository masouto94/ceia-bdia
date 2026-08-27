"""Add reversible, tenant-safe experiment archival."""

from alembic import op  # pyright: ignore[reportMissingImports]

revision = "20260330_13"
down_revision = "20260330_12"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET ROLE project_owner")
    op.execute("""
        ALTER TABLE experiments ADD COLUMN archived_at timestamptz NULL;
        ALTER TABLE experiments ADD COLUMN archived_by uuid NULL;
        ALTER TABLE experiments ADD CONSTRAINT experiments_tenant_archived_by_fk
            FOREIGN KEY (tenant_id,archived_by) REFERENCES memberships(tenant_id,user_id);
        CREATE INDEX experiments_tenant_archived_idx
            ON experiments (tenant_id, archived_at, created_at DESC);

        CREATE OR REPLACE FUNCTION enforce_experiment_archive_policy() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.archived_at IS NOT NULL AND NEW.status = 'running' THEN
                RAISE EXCEPTION 'running experiments cannot be archived';
            END IF;
            IF NEW.status <> OLD.status AND OLD.archived_at IS NOT NULL THEN
                RAISE EXCEPTION 'archived experiments cannot change status';
            END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER experiments_archive_policy
            BEFORE UPDATE OF archived_at, archived_by, status ON experiments
            FOR EACH ROW EXECUTE FUNCTION enforce_experiment_archive_policy();

        CREATE OR REPLACE FUNCTION reject_archived_experiment_result() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM experiments
                WHERE tenant_id=NEW.tenant_id AND id=NEW.experiment_id AND archived_at IS NOT NULL
            ) THEN
                RAISE EXCEPTION 'archived experiments cannot receive results';
            END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER results_reject_archived_experiment
            BEFORE INSERT ON results FOR EACH ROW EXECUTE FUNCTION reject_archived_experiment_result();
    """)
    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE project_owner")
    op.execute("""
        DROP TRIGGER results_reject_archived_experiment ON results;
        DROP FUNCTION reject_archived_experiment_result();
        DROP TRIGGER experiments_archive_policy ON experiments;
        DROP FUNCTION enforce_experiment_archive_policy();
        DROP INDEX experiments_tenant_archived_idx;
        ALTER TABLE experiments DROP CONSTRAINT experiments_tenant_archived_by_fk;
        ALTER TABLE experiments DROP COLUMN archived_by, DROP COLUMN archived_at;
    """)
    op.execute("RESET ROLE")
