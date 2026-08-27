-- Run only through the short-lived db-role-reconcile control path.
\set ON_ERROR_STOP on
\getenv bootstrap_password POSTGRES_PASSWORD
\getenv project_migrator_password PROJECT_MIGRATOR_PASSWORD
\getenv app_runtime_password APP_RUNTIME_PASSWORD
\getenv auth_runtime_password AUTH_RUNTIME_PASSWORD
\getenv assistant_reader_password ASSISTANT_READER_PASSWORD
SELECT CASE WHEN
  :'bootstrap_password' <> '' AND :'project_migrator_password' <> '' AND
  :'app_runtime_password' <> '' AND :'auth_runtime_password' <> '' AND
  :'assistant_reader_password' <> '' AND
  :'bootstrap_password' IS DISTINCT FROM :'project_migrator_password' AND
  :'bootstrap_password' IS DISTINCT FROM :'app_runtime_password' AND
  :'bootstrap_password' IS DISTINCT FROM :'auth_runtime_password' AND
  :'bootstrap_password' IS DISTINCT FROM :'assistant_reader_password' AND
  :'project_migrator_password' IS DISTINCT FROM :'app_runtime_password' AND
  :'project_migrator_password' IS DISTINCT FROM :'auth_runtime_password' AND
  :'project_migrator_password' IS DISTINCT FROM :'assistant_reader_password' AND
  :'app_runtime_password' IS DISTINCT FROM :'auth_runtime_password' AND
  :'app_runtime_password' IS DISTINCT FROM :'assistant_reader_password' AND
  :'auth_runtime_password' IS DISTINCT FROM :'assistant_reader_password'
  THEN 'true' ELSE (1 / 0)::text END AS credentials_valid \gset
BEGIN;
SELECT pg_advisory_xact_lock(hashtext('student-project-role-reconcile'));
DO $$
DECLARE role_name text;
BEGIN
  FOREACH role_name IN ARRAY ARRAY['project_owner','project_migrator','app_runtime','auth_runtime','assistant_reader','session_issuer_owner','platform_read_owner']
  LOOP
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
      EXECUTE format('CREATE ROLE %I NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT', role_name);
    END IF;
  END LOOP;
END $$;
ALTER ROLE project_owner NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT;
ALTER ROLE session_issuer_owner NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT;
ALTER ROLE platform_read_owner NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT;
ALTER ROLE project_migrator LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT;
ALTER ROLE app_runtime LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT;
ALTER ROLE auth_runtime LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT;
ALTER ROLE assistant_reader LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT;
SELECT format('ALTER ROLE project_migrator PASSWORD %L', :'project_migrator_password'); \gexec
SELECT format('ALTER ROLE app_runtime PASSWORD %L', :'app_runtime_password'); \gexec
SELECT format('ALTER ROLE auth_runtime PASSWORD %L', :'auth_runtime_password'); \gexec
SELECT format('ALTER ROLE assistant_reader PASSWORD %L', :'assistant_reader_password'); \gexec
REVOKE project_owner, session_issuer_owner, platform_read_owner FROM app_runtime, auth_runtime, assistant_reader;
GRANT USAGE, CREATE ON SCHEMA public TO project_migrator;
GRANT project_owner TO project_migrator WITH ADMIN FALSE, INHERIT FALSE, SET TRUE;
GRANT session_issuer_owner TO project_owner WITH ADMIN FALSE, INHERIT FALSE, SET TRUE;
GRANT platform_read_owner TO project_owner WITH ADMIN FALSE, INHERIT FALSE, SET TRUE;
DO $$ BEGIN
  IF has_schema_privilege('session_issuer_owner', 'public', 'CREATE') OR has_schema_privilege('platform_read_owner', 'public', 'CREATE') THEN
    RAISE EXCEPTION 'function owners retain CREATE';
  END IF;
END $$;
COMMIT;
