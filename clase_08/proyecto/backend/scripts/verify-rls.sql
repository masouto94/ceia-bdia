-- Run as app_runtime after the Python integration fixture has created two tenants.
BEGIN;
SELECT count(*) AS rows_without_context FROM tenants;
SELECT set_config('app.user_id', :'user_id', true);
SELECT set_config('app.tenant_id', :'tenant_id', true);
SELECT count(*) AS visible_tenants FROM tenants;
COMMIT;

-- A new transaction must not inherit the pooled connection's prior local context.
BEGIN;
SELECT count(*) AS rows_after_context_reset FROM tenants;
ROLLBACK;

SELECT rolname, rolbypassrls
FROM pg_roles
WHERE rolname IN ('project_owner', 'project_migrator', 'app_runtime', 'assistant_reader')
ORDER BY rolname;
