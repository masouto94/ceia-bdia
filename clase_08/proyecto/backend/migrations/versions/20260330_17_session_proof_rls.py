"""Bind tenant authorization and assistant views to active session proofs."""

# pyright: reportMissingImports=false

from alembic import op

revision = "20260330_17"
down_revision = "20260330_16"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET ROLE project_owner")
    op.execute("""
      ALTER TABLE users ADD COLUMN credential_version integer NOT NULL DEFAULT 1;
      ALTER TABLE public.memberships FORCE ROW LEVEL SECURITY;
      CREATE POLICY memberships_project_owner_audit_verified_membership_lookup ON public.memberships FOR SELECT TO project_owner USING (true);
      -- admin-tools is a one-shot project_migrator process that explicitly SET ROLEs to
      -- the NOLOGIN/NOBYPASSRLS/NOINHERIT project_owner for deterministic fixture writes.
      -- Runtime and assistant principals receive neither these policies nor owner membership.
      CREATE POLICY tenants_project_owner_admin_tools ON public.tenants FOR ALL TO project_owner USING (true) WITH CHECK (true);
      CREATE POLICY memberships_project_owner_admin_tools ON public.memberships FOR ALL TO project_owner USING (true) WITH CHECK (true);
      CREATE POLICY roles_project_owner_admin_tools ON public.roles FOR ALL TO project_owner USING (true) WITH CHECK (true);
      CREATE POLICY role_permissions_project_owner_admin_tools ON public.role_permissions FOR ALL TO project_owner USING (true) WITH CHECK (true);
      CREATE POLICY membership_roles_project_owner_admin_tools ON public.membership_roles FOR ALL TO project_owner USING (true) WITH CHECK (true);
      CREATE POLICY experiments_project_owner_admin_tools ON public.experiments FOR ALL TO project_owner USING (true) WITH CHECK (true);
      CREATE POLICY results_project_owner_admin_tools ON public.results FOR ALL TO project_owner USING (true) WITH CHECK (true);
      CREATE POLICY metrics_project_owner_admin_tools ON public.metrics FOR ALL TO project_owner USING (true) WITH CHECK (true);
      CREATE POLICY documents_project_owner_admin_tools ON public.documents FOR ALL TO project_owner USING (true) WITH CHECK (true);
      CREATE POLICY chunks_project_owner_admin_tools ON public.chunks FOR ALL TO project_owner USING (true) WITH CHECK (true);
      CREATE POLICY embeddings_project_owner_admin_tools ON public.embeddings FOR ALL TO project_owner USING (true) WITH CHECK (true);
      CREATE POLICY membership_roles_project_owner_current_tenant_is_admin_lookup ON public.membership_roles FOR SELECT TO project_owner USING (true);
      CREATE POLICY roles_project_owner_current_tenant_is_admin_lookup ON public.roles FOR SELECT TO project_owner USING (true);
      -- Curated assistant views run as project_owner and require these exact FORCE RLS lookup policies.
      CREATE POLICY experiments_project_owner_assistant_view_lookup ON public.experiments FOR SELECT TO project_owner USING (true);
      CREATE POLICY results_project_owner_assistant_view_lookup ON public.results FOR SELECT TO project_owner USING (true);
      CREATE POLICY metrics_project_owner_assistant_view_lookup ON public.metrics FOR SELECT TO project_owner USING (true);
      CREATE POLICY memberships_session_issuer_lookup ON public.memberships FOR SELECT TO session_issuer_owner USING (true);
      CREATE POLICY sessions_session_issuer_lookup ON public.sessions FOR SELECT TO session_issuer_owner USING (true);
      GRANT SELECT ON public.users, public.memberships, public.sessions, public.recovery_tokens TO session_issuer_owner;
          GRANT INSERT, UPDATE ON public.sessions TO session_issuer_owner;
          GRANT SELECT, INSERT ON public.users, public.tenants, public.memberships, public.roles, public.permissions, public.role_permissions, public.membership_roles TO session_issuer_owner;
          CREATE POLICY users_session_issuer_registration ON public.users FOR ALL TO session_issuer_owner USING (true) WITH CHECK (account_scope = 'tenant');
          CREATE POLICY tenants_session_issuer_registration ON public.tenants FOR INSERT TO session_issuer_owner WITH CHECK (true);
          CREATE POLICY memberships_session_issuer_registration ON public.memberships FOR INSERT TO session_issuer_owner WITH CHECK (account_scope = 'tenant' AND active);
          CREATE POLICY roles_session_issuer_registration ON public.roles FOR INSERT TO session_issuer_owner WITH CHECK (true);
          CREATE POLICY permissions_session_issuer_registration ON public.permissions FOR ALL TO session_issuer_owner USING (true) WITH CHECK (true);
          CREATE POLICY role_permissions_session_issuer_registration ON public.role_permissions FOR INSERT TO session_issuer_owner WITH CHECK (true);
          CREATE POLICY membership_roles_session_issuer_registration ON public.membership_roles FOR INSERT TO session_issuer_owner WITH CHECK (true);
          GRANT INSERT ON public.audit_events TO session_issuer_owner;
          CREATE POLICY audit_events_session_issuer_registration ON public.audit_events FOR INSERT TO session_issuer_owner WITH CHECK (actor_id IS NOT NULL AND tenant_id IS NOT NULL AND action = 'auth.registration' AND outcome = 'success' AND metadata = '{}'::jsonb);
          REVOKE CREATE ON SCHEMA public FROM PUBLIC;

      GRANT CREATE ON SCHEMA public TO session_issuer_owner;
      GRANT EXECUTE ON FUNCTION public.append_audit_event(uuid,uuid,varchar,varchar,varchar,jsonb) TO session_issuer_owner;
      SET ROLE session_issuer_owner;
      CREATE FUNCTION public.issue_tenant_session(p_user uuid, p_version integer, p_token varchar, p_csrf varchar, p_expires timestamptz)
      RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
      DECLARE v_tenant uuid;
      BEGIN
        SELECT m.tenant_id INTO v_tenant FROM public.users u JOIN public.memberships m ON m.user_id=u.id
          WHERE u.id=p_user AND u.account_scope = 'tenant' AND u.credential_version=p_version AND m.active LIMIT 1;
        IF v_tenant IS NULL OR p_token !~ '^[0-9a-f]{64}$' OR p_csrf !~ '^[0-9a-f]{64}$' OR p_expires <= now() THEN
          RAISE EXCEPTION 'session issuance rejected';
        END IF;
        INSERT INTO public.sessions(id,user_id,token_hash,csrf_hash,tenant_id,account_scope,expires_at)
          VALUES(gen_random_uuid(),p_user,p_token,p_csrf,v_tenant,'tenant',p_expires);
          END $$;
          CREATE FUNCTION public.register_tenant_bootstrap(
            p_user uuid, p_tenant uuid, p_admin_role uuid, p_member_role uuid, p_viewer_role uuid,
            p_email varchar, p_password_hash varchar, p_tenant_name varchar
          ) RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
          BEGIN
            IF p_user IS NULL OR p_tenant IS NULL OR p_admin_role IS NULL OR p_member_role IS NULL OR p_viewer_role IS NULL
              OR p_user IN (p_tenant,p_admin_role,p_member_role,p_viewer_role) OR p_tenant IN (p_admin_role,p_member_role,p_viewer_role)
              OR p_admin_role IN (p_member_role,p_viewer_role) OR p_member_role = p_viewer_role
              OR p_email IS NULL OR p_email !~ '^[a-z0-9.!#$%&''*+/=?^_`{|}~-]+@[a-z0-9.-]+[.][a-z0-9-]+$'
              OR p_password_hash IS NULL OR char_length(p_password_hash) NOT BETWEEN 20 AND 255
              OR p_tenant_name IS NULL OR char_length(btrim(p_tenant_name)) NOT BETWEEN 1 AND 120 THEN
              RAISE EXCEPTION 'registration rejected';
            END IF;
            IF EXISTS (SELECT 1 FROM public.users WHERE email = p_email) THEN RAISE EXCEPTION 'registration rejected'; END IF;
            INSERT INTO public.users (id,email,password_hash,account_scope) VALUES (p_user,p_email,p_password_hash,'tenant');
            INSERT INTO public.tenants (id,name) VALUES (p_tenant,btrim(p_tenant_name));
            INSERT INTO public.memberships (tenant_id,user_id,account_scope,active) VALUES (p_tenant,p_user,'tenant',true);
            INSERT INTO public.roles (id,tenant_id,name) VALUES
              (p_admin_role,p_tenant,'admin'), (p_member_role,p_tenant,'member'), (p_viewer_role,p_tenant,'viewer');
            INSERT INTO public.permissions (code) VALUES ('members:manage') ON CONFLICT (code) DO NOTHING;
            INSERT INTO public.role_permissions (tenant_id,role_id,permission_code) VALUES (p_tenant,p_admin_role,'members:manage');
            INSERT INTO public.membership_roles (tenant_id,user_id,role_id) VALUES (p_tenant,p_user,p_admin_role);
                INSERT INTO public.audit_events (id,actor_id,tenant_id,action,outcome,resource,metadata)
                  VALUES (gen_random_uuid(),p_user,p_tenant,'auth.registration','success',p_user::text,'{}'::jsonb);
          END $$;
          CREATE FUNCTION public.resolve_runtime_session(p_token varchar)

      RETURNS TABLE(user_id uuid, tenant_id uuid, account_scope varchar)
      LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
        SELECT s.user_id, s.tenant_id, s.account_scope
        FROM public.sessions s
        JOIN public.users u ON u.id=s.user_id
        JOIN public.memberships m ON m.user_id=s.user_id AND m.tenant_id=s.tenant_id AND m.active
        WHERE p_token ~ '^[0-9a-f]{64}$' AND s.token_hash=p_token AND s.revoked_at IS NULL
          AND s.expires_at > now() AND s.account_scope = 'tenant' AND s.tenant_id IS NOT NULL
          AND u.account_scope = 'tenant'
      $$;
      CREATE FUNCTION public.tenant_session_scope_is_valid() RETURNS boolean
      LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
        SELECT current_setting('app.account_scope',true) = 'tenant'
          AND current_setting('app.session_proof',true) ~ '^[0-9a-f]{64}$'
          AND current_setting('app.user_id',true) ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
          AND current_setting('app.tenant_id',true) ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
          AND EXISTS (
            SELECT 1 FROM public.sessions s
            JOIN public.users u ON u.id=s.user_id
            JOIN public.memberships m ON m.user_id=s.user_id AND m.tenant_id=s.tenant_id AND m.active
            WHERE s.token_hash=current_setting('app.session_proof',true)
              AND s.revoked_at IS NULL AND s.expires_at > now()
              AND s.account_scope = 'tenant' AND s.tenant_id IS NOT NULL AND u.account_scope = 'tenant'
              AND s.user_id=NULLIF(current_setting('app.user_id',true),'')::uuid
              AND s.tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
          )
      $$;
      CREATE FUNCTION public.session_csrf_is_valid(p_token varchar, p_csrf varchar, p_scope varchar)
      RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
        SELECT p_token ~ '^[0-9a-f]{64}$' AND p_csrf ~ '^[0-9a-f]{64}$' AND p_scope = 'tenant'
          AND EXISTS (SELECT 1 FROM public.sessions s WHERE s.token_hash=p_token AND s.csrf_hash=p_csrf
            AND s.account_scope=p_scope AND s.revoked_at IS NULL AND s.expires_at > now())
      $$;
      CREATE FUNCTION public.revoke_recovery_sessions(p_token varchar)
      RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
      DECLARE v_user uuid;
      BEGIN
        SELECT user_id INTO v_user FROM public.recovery_tokens
          WHERE token_hash=p_token AND used_at IS NOT NULL AND expires_at > now();
        IF v_user IS NULL OR p_token !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'session revocation rejected'; END IF;
        UPDATE public.sessions SET revoked_at=now() WHERE user_id=v_user AND revoked_at IS NULL;
      END $$;
      CREATE FUNCTION public.revoke_own_session(p_token varchar, p_csrf varchar, p_scope varchar)
      RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
      BEGIN
        UPDATE public.sessions SET revoked_at=now()
          WHERE token_hash=p_token AND csrf_hash=p_csrf AND account_scope=p_scope
            AND revoked_at IS NULL AND expires_at > now();
        IF NOT FOUND THEN RAISE EXCEPTION 'session revocation rejected'; END IF;
      END $$;
      RESET ROLE;
      SET ROLE project_owner;
      REVOKE CREATE ON SCHEMA public FROM session_issuer_owner;
      DO $$ BEGIN
        IF EXISTS (
          SELECT 1 FROM pg_namespace n CROSS JOIN LATERAL aclexplode(n.nspacl) a
          WHERE n.nspname = 'public' AND a.privilege_type = 'CREATE'
            AND a.grantee IN (0, 'session_issuer_owner'::regrole)
        ) OR EXISTS (
          SELECT 1 FROM unnest(ARRAY[
            'public.issue_tenant_session(uuid,integer,character varying,character varying,timestamp with time zone)'::regprocedure,
            'public.resolve_runtime_session(character varying)'::regprocedure,
            'public.tenant_session_scope_is_valid()'::regprocedure,
            'public.session_csrf_is_valid(character varying,character varying,character varying)'::regprocedure,
            'public.revoke_recovery_sessions(character varying)'::regprocedure,
            'public.revoke_own_session(character varying,character varying,character varying)'::regprocedure
          ]) p WHERE (SELECT proowner FROM pg_proc WHERE oid=p) <> 'session_issuer_owner'::regrole
        ) THEN RAISE EXCEPTION 'session issuer ownership assertion failed'; END IF;
      END $$;
      REVOKE ALL ON sessions FROM app_runtime;
      REVOKE ALL ON sessions FROM auth_runtime;
      REVOKE ALL ON TABLE public.sessions FROM assistant_reader;
      SET ROLE session_issuer_owner;
      ALTER FUNCTION public.tenant_session_scope_is_valid() OWNER TO session_issuer_owner;
      RESET ROLE;
      SET ROLE project_owner;
      -- SECURITY DEFINER functions default to PUBLIC EXECUTE: their final owner revokes and grants exact ACLs.
      SET ROLE session_issuer_owner;
          REVOKE ALL ON FUNCTION public.issue_tenant_session(uuid,integer,varchar,varchar,timestamptz) FROM PUBLIC;
          REVOKE ALL ON FUNCTION public.register_tenant_bootstrap(uuid,uuid,uuid,uuid,uuid,varchar,varchar,varchar) FROM PUBLIC;
          REVOKE ALL ON FUNCTION public.resolve_runtime_session(varchar) FROM PUBLIC;

      REVOKE ALL ON FUNCTION public.tenant_session_scope_is_valid() FROM PUBLIC;
      REVOKE ALL ON FUNCTION public.session_csrf_is_valid(varchar,varchar,varchar) FROM PUBLIC;
      REVOKE ALL ON FUNCTION public.revoke_recovery_sessions(varchar) FROM PUBLIC;
      REVOKE ALL ON FUNCTION public.revoke_own_session(varchar,varchar,varchar) FROM PUBLIC;
          GRANT EXECUTE ON FUNCTION public.issue_tenant_session(uuid,integer,varchar,varchar,timestamptz) TO auth_runtime;
          GRANT EXECUTE ON FUNCTION public.register_tenant_bootstrap(uuid,uuid,uuid,uuid,uuid,varchar,varchar,varchar) TO auth_runtime;
          GRANT EXECUTE ON FUNCTION public.append_audit_event(uuid,uuid,varchar,varchar,varchar,jsonb) TO session_issuer_owner;
          GRANT EXECUTE ON FUNCTION public.tenant_session_scope_is_valid() TO app_runtime;
          GRANT EXECUTE ON FUNCTION public.tenant_session_scope_is_valid() TO project_owner;

      GRANT EXECUTE ON FUNCTION public.resolve_runtime_session(varchar) TO app_runtime;
      GRANT EXECUTE ON FUNCTION public.session_csrf_is_valid(varchar,varchar,varchar) TO app_runtime;
      GRANT EXECUTE ON FUNCTION public.revoke_recovery_sessions(varchar) TO app_runtime;
      GRANT EXECUTE ON FUNCTION public.revoke_own_session(varchar,varchar,varchar) TO app_runtime;
      RESET ROLE;
      SET ROLE project_owner;


      -- Every app_runtime tenant policy retains its original role-specific predicate and
      -- adds the non-spoofable proof validator as a conjunct.
      DROP POLICY tenants_tenant_isolation ON public.tenants;
      CREATE POLICY tenants_tenant_isolation ON public.tenants TO app_runtime USING (id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL AND public.tenant_session_scope_is_valid()) WITH CHECK (id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL AND public.tenant_session_scope_is_valid());
      DROP POLICY roles_tenant_isolation ON public.roles;
      CREATE POLICY roles_tenant_isolation ON public.roles TO app_runtime USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL AND public.tenant_session_scope_is_valid()) WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL AND public.tenant_session_scope_is_valid());
      DROP POLICY role_permissions_tenant_isolation ON public.role_permissions;
      CREATE POLICY role_permissions_tenant_isolation ON public.role_permissions TO app_runtime USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL AND public.tenant_session_scope_is_valid()) WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL AND public.tenant_session_scope_is_valid());
      DROP POLICY experiments_tenant_isolation ON public.experiments;
      CREATE POLICY experiments_tenant_isolation ON public.experiments TO app_runtime USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL AND public.tenant_session_scope_is_valid()) WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL AND public.tenant_session_scope_is_valid());
      DROP POLICY results_tenant_isolation ON public.results;
      CREATE POLICY results_tenant_isolation ON public.results TO app_runtime USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL AND public.tenant_session_scope_is_valid()) WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL AND public.tenant_session_scope_is_valid());
      DROP POLICY metrics_tenant_isolation ON public.metrics;
      CREATE POLICY metrics_tenant_isolation ON public.metrics TO app_runtime USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL AND public.tenant_session_scope_is_valid()) WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL AND public.tenant_session_scope_is_valid());
      DROP POLICY documents_tenant_isolation ON public.documents;
      CREATE POLICY documents_tenant_isolation ON public.documents TO app_runtime USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL AND public.tenant_session_scope_is_valid()) WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL AND public.tenant_session_scope_is_valid());
      DROP POLICY chunks_tenant_isolation ON public.chunks;
      CREATE POLICY chunks_tenant_isolation ON public.chunks TO app_runtime USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL AND public.tenant_session_scope_is_valid()) WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL AND public.tenant_session_scope_is_valid());
      DROP POLICY embeddings_tenant_isolation ON public.embeddings;
      CREATE POLICY embeddings_tenant_isolation ON public.embeddings TO app_runtime USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL AND public.tenant_session_scope_is_valid()) WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL AND public.tenant_session_scope_is_valid());
      DROP POLICY membership_roles_tenant_isolation ON public.membership_roles;
      CREATE POLICY membership_roles_tenant_isolation ON public.membership_roles TO app_runtime USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL AND public.tenant_session_scope_is_valid()) WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL AND public.tenant_session_scope_is_valid());
      DROP POLICY ingestion_runs_tenant_isolation ON public.ingestion_runs;
      CREATE POLICY ingestion_runs_tenant_isolation ON public.ingestion_runs TO app_runtime USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL AND public.tenant_session_scope_is_valid()) WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL AND public.tenant_session_scope_is_valid());
      DROP POLICY experiment_status_transitions_tenant_isolation ON public.experiment_status_transitions;
      CREATE POLICY experiment_status_transitions_tenant_isolation ON public.experiment_status_transitions TO app_runtime USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL AND public.tenant_session_scope_is_valid()) WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL AND public.tenant_session_scope_is_valid());
      CREATE OR REPLACE FUNCTION public.current_tenant_is_admin() RETURNS boolean
      LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
        SELECT public.tenant_session_scope_is_valid() AND EXISTS (
          SELECT 1
          FROM public.membership_roles mr
          JOIN public.roles r ON r.id = mr.role_id AND r.tenant_id = mr.tenant_id
          WHERE mr.user_id = NULLIF(current_setting('app.user_id', true), '')::uuid
            AND mr.tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            AND r.name = 'admin'
        )
      $$;
      DROP POLICY memberships_tenant_insert ON public.memberships;
      CREATE POLICY memberships_tenant_insert ON public.memberships FOR INSERT TO app_runtime WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL AND public.tenant_session_scope_is_valid());
      DROP POLICY memberships_tenant_update ON public.memberships;
      CREATE POLICY memberships_tenant_update ON public.memberships FOR UPDATE TO app_runtime USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL AND public.tenant_session_scope_is_valid()) WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL AND public.tenant_session_scope_is_valid());
      DROP POLICY memberships_tenant_delete ON public.memberships;
      CREATE POLICY memberships_tenant_delete ON public.memberships FOR DELETE TO app_runtime USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL AND public.tenant_session_scope_is_valid());
      DROP POLICY memberships_select_admin_tenant ON public.memberships;
      CREATE POLICY memberships_select_admin_tenant ON public.memberships FOR SELECT TO app_runtime USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND current_tenant_is_admin() AND public.tenant_session_scope_is_valid());
      DROP POLICY memberships_select_own ON public.memberships;
      CREATE POLICY memberships_select_own ON public.memberships FOR SELECT TO app_runtime USING (user_id=NULLIF(current_setting('app.user_id',true),'')::uuid AND public.tenant_session_scope_is_valid());
      DROP POLICY audit_events_tenant_admin_select ON public.audit_events;
      CREATE POLICY audit_events_tenant_admin_select ON public.audit_events FOR SELECT TO app_runtime USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND current_tenant_is_admin() AND public.tenant_session_scope_is_valid());
      DROP POLICY audit_events_definer_insert ON public.audit_events;
      CREATE POLICY audit_events_definer_insert ON public.audit_events FOR INSERT TO project_owner WITH CHECK (current_user = 'project_owner');
      DROP POLICY audit_events_definer_global_select ON public.audit_events;
      CREATE POLICY audit_events_definer_global_select ON public.audit_events FOR SELECT TO project_owner USING (tenant_id IS NULL AND current_user = 'project_owner');

      CREATE FUNCTION public.assistant_session_scope_is_valid() RETURNS boolean
      LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
        SELECT current_setting('app.account_scope',true) = 'tenant'
          AND current_setting('app.session_proof',true) ~ '^[0-9a-f]{64}$'
          AND current_setting('app.user_id',true) ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
          AND current_setting('app.tenant_id',true) ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
          AND EXISTS (SELECT 1 FROM public.sessions s JOIN public.users u ON u.id=s.user_id
             JOIN public.memberships m ON m.user_id=s.user_id AND m.tenant_id=s.tenant_id AND m.active
             WHERE s.token_hash=current_setting('app.session_proof',true) AND s.revoked_at IS NULL
               AND s.expires_at > now() AND s.account_scope = 'tenant' AND u.account_scope = 'tenant'
               AND s.user_id=NULLIF(current_setting('app.user_id',true),'')::uuid
               AND s.tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid)
      $$;
      CREATE OR REPLACE VIEW public.assistant_experiments WITH (security_barrier=true) AS
        SELECT id,name,status,created_at,updated_at FROM public.experiments
        WHERE tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND public.assistant_session_scope_is_valid();
      CREATE OR REPLACE VIEW public.assistant_results WITH (security_barrier=true) AS
        SELECT id,experiment_id,status,input_summary,output_summary,created_at FROM public.results
        WHERE tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND public.assistant_session_scope_is_valid();
      CREATE OR REPLACE VIEW public.assistant_metrics WITH (security_barrier=true) AS
        SELECT result_id,name,value_type,number_value,text_value,boolean_value,unit,step,recorded_at FROM public.metrics
        WHERE tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND public.assistant_session_scope_is_valid();
      REVOKE ALL ON TABLE public.sessions FROM assistant_reader;
      REVOKE ALL ON FUNCTION public.assistant_session_scope_is_valid() FROM PUBLIC;
      GRANT EXECUTE ON FUNCTION public.assistant_session_scope_is_valid() TO assistant_reader;
      REVOKE ALL ON TABLE public.assistant_experiments, public.assistant_results, public.assistant_metrics FROM PUBLIC;
      GRANT SELECT ON TABLE public.assistant_experiments TO assistant_reader;
      GRANT SELECT ON TABLE public.assistant_results TO assistant_reader;
      GRANT SELECT ON TABLE public.assistant_metrics TO assistant_reader;
      DO $$ DECLARE p regprocedure; BEGIN
        FOREACH p IN ARRAY ARRAY[
          'public.issue_tenant_session(uuid,integer,character varying,character varying,timestamp with time zone)'::regprocedure,
          'public.resolve_runtime_session(character varying)'::regprocedure,
          'public.tenant_session_scope_is_valid()'::regprocedure,
          'public.session_csrf_is_valid(character varying,character varying,character varying)'::regprocedure,
          'public.revoke_recovery_sessions(character varying)'::regprocedure,
          'public.revoke_own_session(character varying,character varying,character varying)'::regprocedure,
          'public.assistant_session_scope_is_valid()'::regprocedure
        ] LOOP
          IF has_function_privilege('public', p, 'EXECUTE') THEN
            RAISE EXCEPTION 'PUBLIC execute grant remains on %', p;
          END IF;
        END LOOP;
        IF NOT has_function_privilege('auth_runtime', 'public.issue_tenant_session(uuid,integer,character varying,character varying,timestamp with time zone)'::regprocedure, 'EXECUTE')
          OR has_function_privilege('app_runtime', 'public.issue_tenant_session(uuid,integer,character varying,character varying,timestamp with time zone)'::regprocedure, 'EXECUTE')
          OR NOT has_function_privilege('assistant_reader', 'public.assistant_session_scope_is_valid()'::regprocedure, 'EXECUTE')
          OR has_function_privilege('app_runtime', 'public.assistant_session_scope_is_valid()'::regprocedure, 'EXECUTE') THEN
          RAISE EXCEPTION 'session function ACL assertion failed';
        END IF;
      END $$;
      RESET ROLE;
    """)


def downgrade() -> None:
    op.execute("SET ROLE project_owner")
    op.execute("""
      REVOKE ALL ON FUNCTION public.assistant_session_scope_is_valid() FROM assistant_reader;
      DROP VIEW public.assistant_metrics,public.assistant_results,public.assistant_experiments;
      DROP FUNCTION public.assistant_session_scope_is_valid();
      DROP POLICY tenants_tenant_isolation ON public.tenants;
      CREATE POLICY tenants_tenant_isolation ON public.tenants USING (id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL) WITH CHECK (id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL);
      DROP POLICY roles_tenant_isolation ON public.roles; CREATE POLICY roles_tenant_isolation ON public.roles USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL) WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL);
      DROP POLICY role_permissions_tenant_isolation ON public.role_permissions; CREATE POLICY role_permissions_tenant_isolation ON public.role_permissions USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL) WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL);
      DROP POLICY experiments_tenant_isolation ON public.experiments; CREATE POLICY experiments_tenant_isolation ON public.experiments USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL) WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL);
      DROP POLICY results_tenant_isolation ON public.results; CREATE POLICY results_tenant_isolation ON public.results USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL) WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL);
      DROP POLICY metrics_tenant_isolation ON public.metrics; CREATE POLICY metrics_tenant_isolation ON public.metrics USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL) WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL);
      DROP POLICY documents_tenant_isolation ON public.documents; CREATE POLICY documents_tenant_isolation ON public.documents USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL) WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL);
      DROP POLICY chunks_tenant_isolation ON public.chunks; CREATE POLICY chunks_tenant_isolation ON public.chunks USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL) WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL);
      DROP POLICY embeddings_tenant_isolation ON public.embeddings; CREATE POLICY embeddings_tenant_isolation ON public.embeddings USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL) WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL);
      DROP POLICY membership_roles_tenant_isolation ON public.membership_roles; CREATE POLICY membership_roles_tenant_isolation ON public.membership_roles USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL) WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL);
      DROP POLICY ingestion_runs_tenant_isolation ON public.ingestion_runs; CREATE POLICY ingestion_runs_tenant_isolation ON public.ingestion_runs USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL) WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL);
      DROP POLICY experiment_status_transitions_tenant_isolation ON public.experiment_status_transitions; CREATE POLICY experiment_status_transitions_tenant_isolation ON public.experiment_status_transitions USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL) WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL);
      DROP POLICY IF EXISTS memberships_project_owner_audit_verified_membership_lookup ON public.memberships;
      DROP POLICY IF EXISTS tenants_project_owner_admin_tools ON public.tenants;
      DROP POLICY IF EXISTS memberships_project_owner_admin_tools ON public.memberships;
      DROP POLICY IF EXISTS roles_project_owner_admin_tools ON public.roles;
      DROP POLICY IF EXISTS role_permissions_project_owner_admin_tools ON public.role_permissions;
      DROP POLICY IF EXISTS membership_roles_project_owner_admin_tools ON public.membership_roles;
      DROP POLICY IF EXISTS experiments_project_owner_admin_tools ON public.experiments;
      DROP POLICY IF EXISTS results_project_owner_admin_tools ON public.results;
      DROP POLICY IF EXISTS metrics_project_owner_admin_tools ON public.metrics;
      DROP POLICY IF EXISTS documents_project_owner_admin_tools ON public.documents;
      DROP POLICY IF EXISTS chunks_project_owner_admin_tools ON public.chunks;
      DROP POLICY IF EXISTS embeddings_project_owner_admin_tools ON public.embeddings;
      DROP POLICY IF EXISTS membership_roles_project_owner_current_tenant_is_admin_lookup ON public.membership_roles;
      DROP POLICY IF EXISTS roles_project_owner_current_tenant_is_admin_lookup ON public.roles;
      DROP POLICY IF EXISTS experiments_project_owner_assistant_view_lookup ON public.experiments;
      DROP POLICY IF EXISTS results_project_owner_assistant_view_lookup ON public.results;
      DROP POLICY IF EXISTS metrics_project_owner_assistant_view_lookup ON public.metrics;
      DROP POLICY memberships_tenant_insert ON public.memberships; CREATE POLICY memberships_tenant_insert ON public.memberships FOR INSERT WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL);
      DROP POLICY memberships_tenant_update ON public.memberships; CREATE POLICY memberships_tenant_update ON public.memberships FOR UPDATE USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL) WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL);
      DROP POLICY memberships_tenant_delete ON public.memberships; CREATE POLICY memberships_tenant_delete ON public.memberships FOR DELETE USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL);
      DROP POLICY memberships_select_admin_tenant ON public.memberships; CREATE POLICY memberships_select_admin_tenant ON public.memberships FOR SELECT USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND current_tenant_is_admin());
      DROP POLICY memberships_select_own ON public.memberships; CREATE POLICY memberships_select_own ON public.memberships FOR SELECT USING (user_id=NULLIF(current_setting('app.user_id',true),'')::uuid);
      DROP POLICY audit_events_tenant_admin_select ON public.audit_events; CREATE POLICY audit_events_tenant_admin_select ON public.audit_events FOR SELECT USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND current_tenant_is_admin());
      DROP POLICY audit_events_definer_insert ON public.audit_events; CREATE POLICY audit_events_definer_insert ON public.audit_events FOR INSERT WITH CHECK (current_user = 'project_owner');
      DROP POLICY audit_events_definer_global_select ON public.audit_events; CREATE POLICY audit_events_definer_global_select ON public.audit_events FOR SELECT USING (tenant_id IS NULL AND current_user = 'project_owner');
      DROP FUNCTION IF EXISTS public.tenant_session_scope_is_valid();
      DROP FUNCTION IF EXISTS public.revoke_own_session(varchar,varchar,varchar);
      DROP FUNCTION IF EXISTS public.revoke_recovery_sessions(varchar);
      DROP FUNCTION IF EXISTS public.session_csrf_is_valid(varchar,varchar,varchar);
          DROP FUNCTION IF EXISTS public.resolve_runtime_session(varchar);
          DROP FUNCTION IF EXISTS public.register_tenant_bootstrap(uuid,uuid,uuid,uuid,uuid,varchar,varchar,varchar);
          DROP FUNCTION IF EXISTS public.issue_tenant_session(uuid,integer,varchar,varchar,timestamptz);
          DROP POLICY IF EXISTS membership_roles_session_issuer_registration ON public.membership_roles;
          DROP POLICY IF EXISTS role_permissions_session_issuer_registration ON public.role_permissions;
          DROP POLICY IF EXISTS permissions_session_issuer_registration ON public.permissions;
          DROP POLICY IF EXISTS roles_session_issuer_registration ON public.roles;
          DROP POLICY IF EXISTS memberships_session_issuer_registration ON public.memberships;
          DROP POLICY IF EXISTS tenants_session_issuer_registration ON public.tenants;
          DROP POLICY IF EXISTS users_session_issuer_registration ON public.users;
          DROP POLICY IF EXISTS membership_roles_session_issuer_registration ON public.membership_roles;
          DROP POLICY IF EXISTS role_permissions_session_issuer_registration ON public.role_permissions;
          DROP POLICY IF EXISTS permissions_session_issuer_registration ON public.permissions;
          DROP POLICY IF EXISTS roles_session_issuer_registration ON public.roles;
          DROP POLICY IF EXISTS memberships_session_issuer_registration ON public.memberships;
          DROP POLICY IF EXISTS tenants_session_issuer_registration ON public.tenants;
          DROP POLICY IF EXISTS users_session_issuer_registration ON public.users;
          DROP POLICY IF EXISTS audit_events_session_issuer_registration ON public.audit_events;
          DROP POLICY IF EXISTS sessions_session_issuer_lookup ON public.sessions;

      DROP POLICY IF EXISTS memberships_session_issuer_lookup ON public.memberships;
          REVOKE SELECT ON public.users, public.memberships, public.sessions, public.recovery_tokens FROM session_issuer_owner;
          REVOKE INSERT, UPDATE ON public.sessions FROM session_issuer_owner;
          REVOKE SELECT, INSERT ON public.users, public.tenants, public.memberships, public.roles, public.permissions, public.role_permissions, public.membership_roles FROM session_issuer_owner;
          REVOKE EXECUTE ON FUNCTION public.append_audit_event(uuid,uuid,varchar,varchar,varchar,jsonb) FROM session_issuer_owner;
          REVOKE SELECT, INSERT ON public.users, public.tenants, public.memberships, public.roles, public.permissions, public.role_permissions, public.membership_roles FROM session_issuer_owner;
          REVOKE EXECUTE ON FUNCTION public.append_audit_event(uuid,uuid,varchar,varchar,varchar,jsonb) FROM session_issuer_owner;

      ALTER TABLE users DROP COLUMN credential_version;
      GRANT CREATE ON SCHEMA public TO PUBLIC;
      CREATE OR REPLACE VIEW public.assistant_experiments WITH (security_barrier=true) AS SELECT id,name,status,created_at,updated_at FROM public.experiments WHERE tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL;
      CREATE OR REPLACE VIEW public.assistant_results WITH (security_barrier=true) AS SELECT id,experiment_id,status,input_summary,output_summary,created_at FROM public.results WHERE tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL;
      CREATE OR REPLACE VIEW public.assistant_metrics WITH (security_barrier=true) AS SELECT result_id,name,value_type,number_value,text_value,boolean_value,unit,step,recorded_at FROM public.metrics WHERE tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND NULLIF(current_setting('app.user_id',true),'') IS NOT NULL;
      REVOKE ALL ON TABLE public.assistant_experiments, public.assistant_results, public.assistant_metrics FROM PUBLIC;
      GRANT SELECT ON TABLE public.assistant_experiments TO assistant_reader;
      GRANT SELECT ON TABLE public.assistant_results TO assistant_reader;
      GRANT SELECT ON TABLE public.assistant_metrics TO assistant_reader;
      RESET ROLE;
    """)
