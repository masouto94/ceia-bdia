"""Add fixed platform aggregate read functions and persist missing platform audit events."""

from alembic import op

revision = "20260330_19"
down_revision = "20260330_18"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET ROLE project_owner")
    op.execute("""
      -- session_issuer_owner already owns issue_platform_session/revoke_own_session; redefine them
      -- in place so login/logout atomically append a fixed, actor-derived audit event. No new actor
      -- input is accepted: p_user/the matched session row are the only sources of identity here.
      GRANT CREATE ON SCHEMA public TO session_issuer_owner;
      SET ROLE session_issuer_owner;
      CREATE OR REPLACE FUNCTION public.issue_platform_session(p_user uuid, p_version integer, p_token varchar, p_csrf varchar, p_expires timestamptz)
      RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
      BEGIN
        IF p_token !~ '^[0-9a-f]{64}$' OR p_csrf !~ '^[0-9a-f]{64}$' OR p_expires <= now()
          OR NOT EXISTS (
            SELECT 1 FROM public.users u JOIN public.platform_admins pa ON pa.user_id=u.id
            WHERE u.id=p_user AND u.account_scope='platform' AND u.credential_version=p_version AND pa.enabled
          ) THEN RAISE EXCEPTION 'platform issuance rejected'; END IF;
        INSERT INTO public.sessions(id,user_id,token_hash,csrf_hash,tenant_id,account_scope,expires_at)
        VALUES(gen_random_uuid(),p_user,p_token,p_csrf,NULL,'platform',p_expires);
        INSERT INTO public.audit_events(id,actor_id,tenant_id,action,outcome,resource,metadata)
        VALUES(gen_random_uuid(),p_user,NULL,'platform.login','success',NULL,'{}'::jsonb);
      END $$;
      CREATE OR REPLACE FUNCTION public.revoke_own_session(p_token varchar, p_csrf varchar, p_scope varchar)
      RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
      DECLARE v_user uuid;
      BEGIN
        UPDATE public.sessions SET revoked_at=now()
          WHERE token_hash=p_token AND csrf_hash=p_csrf AND account_scope=p_scope
            AND revoked_at IS NULL AND expires_at > now()
          RETURNING user_id INTO v_user;
        IF NOT FOUND THEN RAISE EXCEPTION 'session revocation rejected'; END IF;
        IF p_scope = 'platform' THEN
          INSERT INTO public.audit_events(id,actor_id,tenant_id,action,outcome,resource,metadata)
          VALUES(gen_random_uuid(),v_user,NULL,'platform.logout','success',NULL,'{}'::jsonb);
        END IF;
      END $$;
      RESET ROLE;
      SET ROLE project_owner;
      REVOKE CREATE ON SCHEMA public FROM session_issuer_owner;
      CREATE POLICY audit_events_session_issuer_platform_lifecycle ON public.audit_events FOR INSERT TO session_issuer_owner
        WITH CHECK (
          tenant_id IS NULL AND actor_id IS NOT NULL AND outcome = 'success' AND resource IS NULL AND metadata = '{}'::jsonb
          AND action IN ('platform.login', 'platform.logout')
        );

      -- Bounded aggregate reads own by platform_read_owner. Base tables carry FORCE ROW LEVEL
      -- SECURITY restricted to app_runtime-only policies, so platform_read_owner needs its own
      -- read-only lookup policies; it never receives BYPASSRLS and never selects raw content columns.
      CREATE POLICY tenants_platform_read_lookup ON public.tenants FOR SELECT TO platform_read_owner USING (true);
      CREATE POLICY memberships_platform_read_lookup ON public.memberships FOR SELECT TO platform_read_owner USING (true);
      CREATE POLICY experiments_platform_read_lookup ON public.experiments FOR SELECT TO platform_read_owner USING (true);
      CREATE POLICY documents_platform_read_lookup ON public.documents FOR SELECT TO platform_read_owner USING (true);
      CREATE POLICY audit_events_platform_read_lookup ON public.audit_events FOR SELECT TO platform_read_owner USING (true);
      GRANT SELECT ON public.tenants, public.memberships, public.experiments, public.documents, public.audit_events TO platform_read_owner;
      GRANT SELECT ON public.platform_admins, public.sessions, public.users TO platform_read_owner;

      GRANT CREATE ON SCHEMA public TO platform_read_owner;
      SET ROLE platform_read_owner;
      -- Internal proof validator: never exposed to app_runtime, no actor/tenant/user is accepted
      -- from the caller besides the opaque digest, and it returns only the derived actor id.
      CREATE FUNCTION public.platform_read_actor(p_proof varchar) RETURNS uuid
      LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
        SELECT s.user_id FROM public.sessions s
        JOIN public.users u ON u.id = s.user_id
        JOIN public.platform_admins pa ON pa.user_id = u.id
        WHERE p_proof ~ '^[0-9a-f]{64}$' AND s.token_hash = p_proof AND s.revoked_at IS NULL AND s.expires_at > now()
          AND s.account_scope = 'platform' AND s.tenant_id IS NULL AND u.account_scope = 'platform' AND pa.enabled
      $$;
      CREATE FUNCTION public.platform_dashboard_summary(p_proof varchar)
      RETURNS TABLE(tenant_count bigint, active_tenant_count bigint, platform_admin_count bigint,
                    active_platform_admin_count bigint, experiment_count bigint, document_count bigint)
      LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
      BEGIN
        IF public.platform_read_actor(p_proof) IS NULL THEN RAISE EXCEPTION 'platform proof invalid'; END IF;
        RETURN QUERY SELECT
          (SELECT count(*) FROM public.tenants),
          (SELECT count(DISTINCT m.tenant_id) FROM public.memberships m WHERE m.active),
          (SELECT count(*) FROM public.platform_admins),
          (SELECT count(*) FROM public.platform_admins WHERE enabled),
          (SELECT count(*) FROM public.experiments),
          (SELECT count(*) FROM public.documents);
      END $$;
      CREATE FUNCTION public.platform_tenant_overview(p_proof varchar, p_search varchar, p_limit integer, p_offset integer)
      RETURNS TABLE(tenant_id uuid, tenant_name varchar, created_at timestamptz, active_member_count bigint,
                    experiment_count bigint, document_count bigint, last_activity_at timestamptz, total_count bigint)
      LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
      DECLARE
        v_limit integer := LEAST(GREATEST(COALESCE(p_limit,20),1),50);
        v_offset integer := GREATEST(COALESCE(p_offset,0),0);
        v_search varchar := NULLIF(btrim(COALESCE(p_search,'')),'');
      BEGIN
        IF public.platform_read_actor(p_proof) IS NULL THEN RAISE EXCEPTION 'platform proof invalid'; END IF;
        IF v_search IS NOT NULL AND char_length(v_search) > 120 THEN RAISE EXCEPTION 'invalid platform search'; END IF;
        RETURN QUERY
        WITH matched AS (
          SELECT t.id, t.name, t.created_at FROM public.tenants t
          WHERE v_search IS NULL OR t.name ILIKE '%' || v_search || '%'
        ), total AS (SELECT count(*) AS n FROM matched)
        SELECT m.id, m.name, m.created_at,
          (SELECT count(*) FROM public.memberships mb WHERE mb.tenant_id = m.id AND mb.active),
          (SELECT count(*) FROM public.experiments e WHERE e.tenant_id = m.id),
          (SELECT count(*) FROM public.documents d WHERE d.tenant_id = m.id),
          (SELECT max(a.created_at) FROM public.audit_events a WHERE a.tenant_id = m.id),
          total.n
        FROM matched m CROSS JOIN total
        ORDER BY m.created_at DESC, m.id
        LIMIT v_limit OFFSET v_offset;
      END $$;
      CREATE FUNCTION public.platform_tenant_detail(p_proof varchar, p_tenant uuid)
      RETURNS TABLE(tenant_id uuid, tenant_name varchar, created_at timestamptz, active_member_count bigint,
                    experiment_draft_count bigint, experiment_running_count bigint, experiment_completed_count bigint,
                    experiment_failed_count bigint, document_count bigint, last_activity_at timestamptz)
      LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
      BEGIN
        IF public.platform_read_actor(p_proof) IS NULL THEN RAISE EXCEPTION 'platform proof invalid'; END IF;
        IF p_tenant IS NULL THEN RAISE EXCEPTION 'invalid platform tenant'; END IF;
        RETURN QUERY
        SELECT t.id, t.name, t.created_at,
          (SELECT count(*) FROM public.memberships mb WHERE mb.tenant_id=t.id AND mb.active),
          (SELECT count(*) FROM public.experiments e WHERE e.tenant_id=t.id AND e.status='draft'),
          (SELECT count(*) FROM public.experiments e WHERE e.tenant_id=t.id AND e.status='running'),
          (SELECT count(*) FROM public.experiments e WHERE e.tenant_id=t.id AND e.status='completed'),
          (SELECT count(*) FROM public.experiments e WHERE e.tenant_id=t.id AND e.status='failed'),
          (SELECT count(*) FROM public.documents d WHERE d.tenant_id=t.id),
          (SELECT max(a.created_at) FROM public.audit_events a WHERE a.tenant_id=t.id)
        FROM public.tenants t WHERE t.id = p_tenant;
      END $$;
      RESET ROLE;
      SET ROLE project_owner;
      REVOKE CREATE ON SCHEMA public FROM platform_read_owner;
      SET ROLE platform_read_owner;
      REVOKE ALL ON FUNCTION public.platform_read_actor(varchar) FROM PUBLIC;
      REVOKE ALL ON FUNCTION public.platform_dashboard_summary(varchar) FROM PUBLIC;
      REVOKE ALL ON FUNCTION public.platform_tenant_overview(varchar,varchar,integer,integer) FROM PUBLIC;
      REVOKE ALL ON FUNCTION public.platform_tenant_detail(varchar,uuid) FROM PUBLIC;
      GRANT EXECUTE ON FUNCTION public.platform_dashboard_summary(varchar) TO app_runtime;
      GRANT EXECUTE ON FUNCTION public.platform_tenant_overview(varchar,varchar,integer,integer) TO app_runtime;
      GRANT EXECUTE ON FUNCTION public.platform_tenant_detail(varchar,uuid) TO app_runtime;
      RESET ROLE;
      SET ROLE project_owner;
      DO $$ BEGIN
        IF has_schema_privilege('session_issuer_owner','public','CREATE')
          OR has_schema_privilege('platform_read_owner','public','CREATE')
          OR has_function_privilege('app_runtime','public.platform_read_actor(varchar)'::regprocedure,'EXECUTE')
          OR NOT has_function_privilege('app_runtime','public.platform_dashboard_summary(varchar)'::regprocedure,'EXECUTE')
          OR (SELECT proowner FROM pg_proc WHERE oid='public.platform_dashboard_summary(varchar)'::regprocedure) <> 'platform_read_owner'::regrole
          OR EXISTS (
            SELECT 1 FROM unnest(ARRAY[
              'public.platform_read_actor(varchar)'::regprocedure,
              'public.platform_dashboard_summary(varchar)'::regprocedure,
              'public.platform_tenant_overview(varchar,varchar,integer,integer)'::regprocedure,
              'public.platform_tenant_detail(varchar,uuid)'::regprocedure
            ]) p CROSS JOIN LATERAL aclexplode((SELECT proacl FROM pg_proc WHERE oid = p)) a
            WHERE a.grantee = 0 AND a.privilege_type = 'EXECUTE'
          )
        THEN RAISE EXCEPTION 'platform read function ACL assertion failed';
        END IF;
      END $$;
      RESET ROLE;
    """)


def downgrade() -> None:
    op.execute("SET ROLE project_owner")
    op.execute("""
      DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM public.platform_admins) OR EXISTS (SELECT 1 FROM public.sessions WHERE account_scope='platform') THEN
          RAISE EXCEPTION 'post-use downgrade is disabled; disable platform authorization operationally';
        END IF;
      END $$;
      DROP FUNCTION IF EXISTS public.platform_tenant_detail(varchar,uuid);
      DROP FUNCTION IF EXISTS public.platform_tenant_overview(varchar,varchar,integer,integer);
      DROP FUNCTION IF EXISTS public.platform_dashboard_summary(varchar);
      DROP FUNCTION IF EXISTS public.platform_read_actor(varchar);
      DROP POLICY IF EXISTS audit_events_platform_read_lookup ON public.audit_events;
      DROP POLICY IF EXISTS documents_platform_read_lookup ON public.documents;
      DROP POLICY IF EXISTS experiments_platform_read_lookup ON public.experiments;
      DROP POLICY IF EXISTS memberships_platform_read_lookup ON public.memberships;
      DROP POLICY IF EXISTS tenants_platform_read_lookup ON public.tenants;
      REVOKE SELECT ON public.tenants, public.memberships, public.experiments, public.documents, public.audit_events FROM platform_read_owner;
      REVOKE SELECT ON public.platform_admins, public.sessions, public.users FROM platform_read_owner;
      DROP POLICY IF EXISTS audit_events_session_issuer_platform_lifecycle ON public.audit_events;
      GRANT CREATE ON SCHEMA public TO session_issuer_owner;
      SET ROLE session_issuer_owner;
      CREATE OR REPLACE FUNCTION public.issue_platform_session(p_user uuid, p_version integer, p_token varchar, p_csrf varchar, p_expires timestamptz)
      RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
      BEGIN
        IF p_token !~ '^[0-9a-f]{64}$' OR p_csrf !~ '^[0-9a-f]{64}$' OR p_expires <= now()
          OR NOT EXISTS (
            SELECT 1 FROM public.users u JOIN public.platform_admins pa ON pa.user_id=u.id
            WHERE u.id=p_user AND u.account_scope='platform' AND u.credential_version=p_version AND pa.enabled
          ) THEN RAISE EXCEPTION 'platform issuance rejected'; END IF;
        INSERT INTO public.sessions(id,user_id,token_hash,csrf_hash,tenant_id,account_scope,expires_at)
        VALUES(gen_random_uuid(),p_user,p_token,p_csrf,NULL,'platform',p_expires);
      END $$;
      CREATE OR REPLACE FUNCTION public.revoke_own_session(p_token varchar, p_csrf varchar, p_scope varchar)
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
      RESET ROLE;
    """)
