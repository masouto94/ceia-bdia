"""Harden experiment lifecycle, tenant foreign keys, and append-only provenance."""

from alembic import op

revision = "20260330_07"
down_revision = "20260330_06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET ROLE project_owner")
    op.execute("""
        ALTER TABLE experiments ADD COLUMN created_at timestamptz NOT NULL DEFAULT now();
        ALTER TABLE experiments ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now();
        ALTER TABLE experiments ADD CONSTRAINT experiments_tenant_id_id_key UNIQUE (tenant_id,id);

        ALTER TABLE results ADD COLUMN input_summary text;
        ALTER TABLE results RENAME COLUMN summary TO output_summary;
        ALTER TABLE results ADD COLUMN created_at timestamptz NOT NULL DEFAULT now();
        ALTER TABLE results ADD CONSTRAINT results_status_check CHECK (status IN ('completed','failed'));
        ALTER TABLE results ADD CONSTRAINT results_tenant_id_id_key UNIQUE (tenant_id,id);
        ALTER TABLE results DROP CONSTRAINT results_experiment_id_fkey;
        ALTER TABLE results ADD CONSTRAINT results_tenant_experiment_fk
            FOREIGN KEY (tenant_id,experiment_id) REFERENCES experiments(tenant_id,id);

        ALTER TABLE metrics ADD COLUMN creator_id uuid REFERENCES users(id);
        UPDATE metrics SET creator_id = r.creator_id FROM results r WHERE r.id=metrics.result_id;
        ALTER TABLE metrics ALTER COLUMN creator_id SET NOT NULL;
        ALTER TABLE metrics ALTER COLUMN number_value TYPE numeric USING number_value::numeric;
        ALTER TABLE metrics ADD COLUMN unit varchar(40);
        ALTER TABLE metrics ADD COLUMN step integer CHECK (step >= 0);
        ALTER TABLE metrics ADD COLUMN recorded_at timestamptz NOT NULL DEFAULT now();
        ALTER TABLE metrics DROP CONSTRAINT metrics_result_id_fkey;
        ALTER TABLE metrics ADD CONSTRAINT metrics_tenant_result_fk
            FOREIGN KEY (tenant_id,result_id) REFERENCES results(tenant_id,id);
        ALTER TABLE metrics ADD CONSTRAINT metrics_typed_value_check CHECK (
            (value_type='number' AND number_value IS NOT NULL AND text_value IS NULL AND boolean_value IS NULL AND json_value IS NULL) OR
            (value_type='text' AND number_value IS NULL AND text_value IS NOT NULL AND boolean_value IS NULL AND json_value IS NULL) OR
            (value_type='boolean' AND number_value IS NULL AND text_value IS NULL AND boolean_value IS NOT NULL AND json_value IS NULL) OR
            (value_type='json' AND number_value IS NULL AND text_value IS NULL AND boolean_value IS NULL AND json_value IS NOT NULL)
        );

        CREATE FUNCTION enforce_experiment_transition() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.status <> OLD.status AND NOT (
                (OLD.status='draft' AND NEW.status='running') OR
                (OLD.status='running' AND NEW.status IN ('completed','failed'))
            ) THEN RAISE EXCEPTION 'invalid experiment lifecycle transition'; END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER experiments_lifecycle BEFORE UPDATE OF status ON experiments
            FOR EACH ROW EXECUTE FUNCTION enforce_experiment_transition();
        CREATE FUNCTION reject_historical_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'historical experiment records are append-only'; END $$;
        CREATE TRIGGER results_append_only BEFORE UPDATE OR DELETE ON results
            FOR EACH ROW EXECUTE FUNCTION reject_historical_mutation();
        CREATE TRIGGER metrics_append_only BEFORE UPDATE OR DELETE ON metrics
            FOR EACH ROW EXECUTE FUNCTION reject_historical_mutation();
        REVOKE UPDATE, DELETE ON results, metrics FROM app_runtime;
        GRANT DELETE ON experiments TO app_runtime;
    """)
    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE project_owner")
    op.execute("""
        DROP TRIGGER metrics_append_only ON metrics; DROP TRIGGER results_append_only ON results;
        DROP FUNCTION reject_historical_mutation();
        DROP TRIGGER experiments_lifecycle ON experiments; DROP FUNCTION enforce_experiment_transition();
        ALTER TABLE metrics DROP CONSTRAINT metrics_typed_value_check;
        ALTER TABLE metrics DROP CONSTRAINT metrics_tenant_result_fk;
        ALTER TABLE metrics ADD CONSTRAINT metrics_result_id_fkey FOREIGN KEY (result_id) REFERENCES results(id);
        ALTER TABLE metrics DROP COLUMN recorded_at, DROP COLUMN step, DROP COLUMN unit, DROP COLUMN creator_id;
        ALTER TABLE metrics ALTER COLUMN number_value TYPE integer USING number_value::integer;
        ALTER TABLE results DROP CONSTRAINT results_tenant_experiment_fk;
        ALTER TABLE results ADD CONSTRAINT results_experiment_id_fkey FOREIGN KEY (experiment_id) REFERENCES experiments(id);
        ALTER TABLE results DROP CONSTRAINT results_tenant_id_id_key, DROP CONSTRAINT results_status_check;
        ALTER TABLE results DROP COLUMN created_at; ALTER TABLE results RENAME COLUMN output_summary TO summary;
        ALTER TABLE results DROP COLUMN input_summary;
        ALTER TABLE experiments DROP CONSTRAINT experiments_tenant_id_id_key;
        ALTER TABLE experiments DROP COLUMN updated_at, DROP COLUMN created_at;
        GRANT UPDATE ON results, metrics TO app_runtime;
    """)
    op.execute("RESET ROLE")
