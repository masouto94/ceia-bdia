"""Repair audit policies and bind definer writes to trusted request context."""

from alembic import op  # pyright: ignore[reportMissingImports]

revision = "20260330_15"
down_revision = "20260330_14"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET ROLE project_owner")
    op.execute("""
        ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
        ALTER TABLE audit_events FORCE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS audit_events_definer_insert ON audit_events;
        CREATE POLICY audit_events_definer_insert ON audit_events FOR INSERT
          WITH CHECK (current_user = 'project_owner');
        DROP POLICY IF EXISTS audit_events_definer_global_select ON audit_events;
        CREATE POLICY audit_events_definer_global_select ON audit_events FOR SELECT
          USING (tenant_id IS NULL AND current_user = 'project_owner');

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
          -- app_runtime is the application trust boundary. The local GUCs are set only
          -- by authenticated request code and bind tenant events to that request.
          IF p_tenant IS NULL THEN
            IF p_actor IS NOT NULL OR p_action <> 'auth.recovery.request'
               OR p_outcome NOT IN ('success', 'rate_limited')
               OR p_resource IS NULL OR p_metadata <> '{}'::jsonb
            THEN RAISE EXCEPTION 'invalid global audit event'; END IF;
          ELSE
            IF p_tenant IS DISTINCT FROM NULLIF(current_setting('app.tenant_id', true), '')::uuid
               OR p_actor IS DISTINCT FROM NULLIF(current_setting('app.user_id', true), '')::uuid
               OR p_actor IS NULL OR NOT verified_membership(p_actor, p_tenant)
            THEN RAISE EXCEPTION 'unverified audit request context'; END IF;
          END IF;
          INSERT INTO audit_events (id,actor_id,tenant_id,action,outcome,resource,metadata)
            VALUES (v_id,p_actor,p_tenant,p_action,p_outcome,p_resource,p_metadata);
          RETURN v_id;
        END $$;
        ALTER FUNCTION append_audit_event(uuid,uuid,varchar,varchar,varchar,jsonb) OWNER TO project_owner;
        REVOKE ALL ON FUNCTION append_audit_event(uuid,uuid,varchar,varchar,varchar,jsonb) FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION append_audit_event(uuid,uuid,varchar,varchar,varchar,jsonb) TO app_runtime;
    """)
    op.execute("RESET ROLE")


def downgrade() -> None:
    """Restore the revision-14 policy and function definitions exactly in behavior."""
    op.execute("SET ROLE project_owner")
    op.execute("""
        DROP POLICY IF EXISTS audit_events_definer_global_select ON audit_events;
        DROP POLICY IF EXISTS audit_events_definer_insert ON audit_events;
        CREATE POLICY audit_events_definer_insert ON audit_events FOR INSERT WITH CHECK (true);
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
    """)
    op.execute("RESET ROLE")
