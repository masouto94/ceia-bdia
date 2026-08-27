"""Harden audit storage and expose an admin-only normalized read model."""

from alembic import op  # pyright: ignore[reportMissingImports]

revision = "20260330_14"
down_revision = "20260330_13"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET ROLE project_owner")
    op.execute("""
        ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS metadata jsonb NOT NULL DEFAULT '{}'::jsonb;
        ALTER TABLE audit_events ADD CONSTRAINT audit_events_outcome_check
          CHECK (outcome IN ('success', 'denied', 'failed', 'rate_limited', 'accepted'));
        CREATE INDEX audit_events_tenant_occurred_idx ON audit_events (tenant_id, created_at DESC, id DESC);
        CREATE INDEX audit_events_recovery_rate_idx ON audit_events (action, resource, created_at DESC)
          WHERE tenant_id IS NULL;
        ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
        ALTER TABLE audit_events FORCE ROW LEVEL SECURITY;
        CREATE POLICY audit_events_tenant_admin_select ON audit_events FOR SELECT USING (
          tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
          AND current_tenant_is_admin()
        );
        -- INSERT privileges remain revoked from app_runtime; this policy exists solely for the definer function.
        CREATE POLICY audit_events_definer_insert ON audit_events FOR INSERT WITH CHECK (true);
        CREATE TRIGGER audit_events_append_only BEFORE UPDATE OR DELETE ON audit_events
          FOR EACH ROW EXECUTE FUNCTION reject_historical_mutation();
        REVOKE INSERT, UPDATE, DELETE ON audit_events FROM app_runtime;
        GRANT SELECT ON audit_events TO app_runtime;

        CREATE OR REPLACE FUNCTION append_audit_event(
          p_actor uuid, p_tenant uuid, p_action varchar, p_outcome varchar,
          p_resource varchar, p_metadata jsonb
        ) RETURNS uuid
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
        DECLARE v_id uuid := gen_random_uuid();
        BEGIN
          IF p_action NOT IN (
            'auth.registration','auth.login','auth.logout','auth.recovery.request','auth.recovery.confirm','security.csrf_denied',
            'membership.created','membership.role_changed','membership.activation_changed',
            'document.upload','document.ingest.started','document.ingest.reprocessed',
            'experiment.created','experiment.renamed','experiment.result_added','experiment.archived','experiment.restored'
          ) THEN RAISE EXCEPTION 'invalid audit action'; END IF;
          IF p_outcome NOT IN ('success','denied','failed','rate_limited') THEN RAISE EXCEPTION 'invalid audit outcome'; END IF;
          IF p_resource IS NOT NULL AND char_length(p_resource) > 120 THEN RAISE EXCEPTION 'invalid audit resource'; END IF;
          IF p_metadata IS NULL OR jsonb_typeof(p_metadata) <> 'object' OR octet_length(p_metadata::text) > 2048
             OR EXISTS (SELECT 1 FROM jsonb_object_keys(p_metadata) k WHERE k NOT IN
               ('previous_archived','archived','previous_status','next_status','role','previous_role','active','previous_active','content_type','size_bytes','chunk_count','attempt'))
             OR EXISTS (SELECT 1 FROM jsonb_each(p_metadata) e WHERE jsonb_typeof(e.value) NOT IN ('string','number','boolean','null'))
          THEN RAISE EXCEPTION 'invalid audit metadata'; END IF;
          IF p_tenant IS NULL THEN
            IF p_action NOT IN ('auth.recovery.request','auth.recovery.confirm','security.csrf_denied') THEN RAISE EXCEPTION 'invalid global audit action'; END IF;
          ELSIF p_actor IS NULL OR NOT verified_membership(p_actor, p_tenant) THEN
            RAISE EXCEPTION 'unverified audit actor';
          END IF;
          INSERT INTO audit_events (id,actor_id,tenant_id,action,outcome,resource,metadata)
            VALUES (v_id,p_actor,p_tenant,p_action,p_outcome,p_resource,p_metadata);
          RETURN v_id;
        END $$;
        ALTER FUNCTION append_audit_event(uuid,uuid,varchar,varchar,varchar,jsonb) OWNER TO project_owner;
        REVOKE ALL ON FUNCTION append_audit_event(uuid,uuid,varchar,varchar,varchar,jsonb) FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION append_audit_event(uuid,uuid,varchar,varchar,varchar,jsonb) TO app_runtime;

        CREATE OR REPLACE FUNCTION recovery_request_count(p_resource varchar) RETURNS bigint
        LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
          SELECT count(*) FROM audit_events
          WHERE tenant_id IS NULL AND resource = p_resource
            AND action IN ('recovery_request','auth.recovery.request')
            AND created_at > now() - interval '1 hour'
        $$;
        ALTER FUNCTION recovery_request_count(varchar) OWNER TO project_owner;
        REVOKE ALL ON FUNCTION recovery_request_count(varchar) FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION recovery_request_count(varchar) TO app_runtime;

        CREATE TRIGGER ingestion_runs_append_only BEFORE UPDATE OR DELETE ON ingestion_runs
          FOR EACH ROW EXECUTE FUNCTION reject_historical_mutation();
        REVOKE UPDATE, DELETE ON ingestion_runs FROM app_runtime;
    """)
    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE project_owner")
    op.execute("""
        DROP TRIGGER ingestion_runs_append_only ON ingestion_runs;
        DROP FUNCTION recovery_request_count(varchar);
        DROP FUNCTION append_audit_event(uuid,uuid,varchar,varchar,varchar,jsonb);
        DROP TRIGGER audit_events_append_only ON audit_events;
        DROP POLICY audit_events_definer_insert ON audit_events;
        DROP POLICY audit_events_tenant_admin_select ON audit_events;
        DROP INDEX audit_events_recovery_rate_idx;
        DROP INDEX audit_events_tenant_occurred_idx;
        ALTER TABLE audit_events DROP CONSTRAINT audit_events_outcome_check;
        ALTER TABLE audit_events DROP COLUMN metadata;
    """)
    op.execute("RESET ROLE")
