"""Add isolated platform session issuance and lifecycle support, not aggregates."""

from alembic import op

revision = "20260330_18"
down_revision = "20260330_17"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET ROLE project_owner")
    op.execute("""
      GRANT CREATE ON SCHEMA public TO session_issuer_owner;
      SET ROLE session_issuer_owner;
      CREATE FUNCTION public.issue_platform_session(p_user uuid, p_version integer, p_token varchar, p_csrf varchar, p_expires timestamptz)
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
      CREATE OR REPLACE FUNCTION public.session_csrf_is_valid(p_token varchar, p_csrf varchar, p_scope varchar)
      RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
        SELECT p_token ~ '^[0-9a-f]{64}$' AND p_csrf ~ '^[0-9a-f]{64}$' AND p_scope IN ('tenant','platform')
          AND EXISTS (SELECT 1 FROM public.sessions s WHERE s.token_hash=p_token AND s.csrf_hash=p_csrf
            AND s.account_scope=p_scope AND s.revoked_at IS NULL AND s.expires_at > now())
      $$;
      CREATE FUNCTION public.resolve_platform_session(p_token varchar)
      RETURNS TABLE(user_id uuid, account_scope varchar) LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
        SELECT s.user_id, s.account_scope FROM public.sessions s
        JOIN public.users u ON u.id=s.user_id JOIN public.platform_admins pa ON pa.user_id=u.id
        WHERE p_token ~ '^[0-9a-f]{64}$' AND s.token_hash=p_token AND s.revoked_at IS NULL AND s.expires_at > now()
          AND s.account_scope='platform' AND s.tenant_id IS NULL AND u.account_scope='platform' AND pa.enabled
      $$;
      CREATE FUNCTION public.append_platform_denial() RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
      BEGIN
        INSERT INTO public.audit_events(id,actor_id,tenant_id,action,outcome,resource,metadata)
        VALUES(gen_random_uuid(),NULL,NULL,'platform.route_denied','denied','platform','{}'::jsonb);
      END $$;
      RESET ROLE;
      SET ROLE project_owner;
      REVOKE CREATE ON SCHEMA public FROM session_issuer_owner;
      CREATE POLICY audit_events_session_issuer_platform_denial ON public.audit_events FOR INSERT TO session_issuer_owner
        WITH CHECK (actor_id IS NULL AND tenant_id IS NULL AND action='platform.route_denied' AND outcome='denied' AND resource='platform' AND metadata='{}'::jsonb);
      SET ROLE session_issuer_owner;
      REVOKE ALL ON FUNCTION public.issue_platform_session(uuid,integer,varchar,varchar,timestamptz) FROM PUBLIC;
      REVOKE ALL ON FUNCTION public.resolve_platform_session(varchar) FROM PUBLIC;
      REVOKE ALL ON FUNCTION public.append_platform_denial() FROM PUBLIC;
      GRANT EXECUTE ON FUNCTION public.issue_platform_session(uuid,integer,varchar,varchar,timestamptz) TO auth_runtime;
      GRANT EXECUTE ON FUNCTION public.resolve_platform_session(varchar) TO app_runtime;
      GRANT EXECUTE ON FUNCTION public.append_platform_denial() TO app_runtime;
      RESET ROLE;
      SET ROLE project_owner;
      CREATE POLICY platform_admins_session_issuer_lookup ON public.platform_admins FOR SELECT TO session_issuer_owner USING (true);
      GRANT SELECT ON public.platform_admins TO session_issuer_owner;
      GRANT SELECT ON public.platform_admins TO app_runtime;
      DO $$ BEGIN
        IF has_schema_privilege('session_issuer_owner','public','CREATE')
          OR EXISTS (SELECT 1 FROM pg_proc p CROSS JOIN LATERAL aclexplode(p.proacl) a
            WHERE p.oid='public.issue_platform_session(uuid,integer,varchar,varchar,timestamptz)'::regprocedure
              AND a.grantee=0 AND a.privilege_type='EXECUTE')
          OR has_function_privilege('app_runtime','public.issue_platform_session(uuid,integer,varchar,varchar,timestamptz)'::regprocedure,'EXECUTE') THEN
          RAISE EXCEPTION 'platform lifecycle ACL assertion failed';
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
      DROP POLICY IF EXISTS audit_events_session_issuer_platform_denial ON public.audit_events;
      DROP POLICY IF EXISTS platform_admins_session_issuer_lookup ON public.platform_admins;
      REVOKE SELECT ON public.platform_admins FROM session_issuer_owner;
      REVOKE SELECT ON public.platform_admins FROM app_runtime;
      DROP FUNCTION IF EXISTS public.append_platform_denial();
      DROP FUNCTION IF EXISTS public.resolve_platform_session(varchar);
      DROP FUNCTION IF EXISTS public.issue_platform_session(uuid,integer,varchar,varchar,timestamptz);
      RESET ROLE;
    """)
