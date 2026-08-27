"""RED contracts for proof-bound tenant and assistant reads."""

import unittest
from pathlib import Path


class SessionProofRlsTests(unittest.TestCase):
    def test_migration_replaces_guc_only_authority_with_active_session_proof(self) -> None:
        migration = Path("migrations/versions/20260330_17_session_proof_rls.py").read_text(encoding="utf-8")
        self.assertIn("assistant_session_scope_is_valid", migration)
        self.assertIn("app.session_proof", migration)
        self.assertIn("token_hash", migration)
        self.assertIn("revoked_at IS NULL", migration)
        self.assertIn("expires_at > now()", migration)
        self.assertIn("account_scope = 'tenant'", migration)
        self.assertIn("CREATE OR REPLACE VIEW public.assistant_experiments", migration)
        self.assertIn("REVOKE ALL ON TABLE public.sessions FROM assistant_reader", migration)

    def test_issuer_ownership_transfer_removes_public_schema_create_before_assertion(self) -> None:
        migration = Path("migrations/versions/20260330_17_session_proof_rls.py").read_text(encoding="utf-8")
        revoke_public = "REVOKE CREATE ON SCHEMA public FROM PUBLIC"
        grant_owner = "GRANT CREATE ON SCHEMA public TO session_issuer_owner"
        self.assertIn(revoke_public, migration)
        self.assertLess(migration.index(revoke_public), migration.index(grant_owner))
        self.assertIn("aclexplode(n.nspacl)", migration)
        self.assertIn("a.grantee IN (0, 'session_issuer_owner'::regrole)", migration)
        self.assertIn("RESET ROLE;\n      SET ROLE project_owner;\n      REVOKE CREATE ON SCHEMA public FROM session_issuer_owner;", migration)

    def test_downgrade_drops_proof_bound_views_before_their_validator(self) -> None:
        migration = Path("migrations/versions/20260330_17_session_proof_rls.py").read_text(encoding="utf-8")
        views = "DROP VIEW public.assistant_metrics,public.assistant_results,public.assistant_experiments"
        validator = "DROP FUNCTION public.assistant_session_scope_is_valid()"
        self.assertIn(views, migration)
        self.assertLess(migration.rindex(views), migration.rindex(validator))
        self.assertIn("DROP POLICY IF EXISTS memberships_session_issuer_lookup", migration)

    def test_downgrade_is_compatible_with_the_pre_resolver_revision_shape(self) -> None:
        migration = Path("migrations/versions/20260330_17_session_proof_rls.py").read_text(encoding="utf-8")
        self.assertIn("DROP FUNCTION IF EXISTS public.resolve_runtime_session(varchar)", migration)
        self.assertIn("DROP FUNCTION IF EXISTS public.session_csrf_is_valid(varchar,varchar,varchar)", migration)

    def test_runtime_resolver_is_definer_owned_and_returns_only_runtime_context(self) -> None:
        migration = Path("migrations/versions/20260330_17_session_proof_rls.py").read_text(encoding="utf-8")
        self.assertIn("CREATE FUNCTION public.resolve_runtime_session(p_token varchar)", migration)
        self.assertIn("RETURNS TABLE(user_id uuid, tenant_id uuid, account_scope varchar)", migration)
        self.assertIn("SECURITY DEFINER SET search_path = pg_catalog, public", migration)
        self.assertIn("GRANT EXECUTE ON FUNCTION public.resolve_runtime_session(varchar) TO app_runtime", migration)
        self.assertIn("REVOKE ALL ON FUNCTION public.resolve_runtime_session(varchar) FROM PUBLIC", migration)
        resolver = migration[migration.index("CREATE FUNCTION public.resolve_runtime_session"):migration.index("CREATE FUNCTION public.session_csrf_is_valid")]
        self.assertIn("s.token_hash=p_token", resolver)
        self.assertIn("s.revoked_at IS NULL", resolver)
        self.assertIn("s.expires_at > now()", resolver)
        self.assertIn("s.account_scope = 'tenant'", resolver)
        self.assertNotIn("csrf_hash", resolver)
        self.assertNotIn("RETURN s.id", resolver)

    def test_every_runtime_tenant_policy_requires_the_session_proof_validator(self) -> None:
        migration = Path("migrations/versions/20260330_17_session_proof_rls.py").read_text(encoding="utf-8")
        expected = {
            "tenants_tenant_isolation", "memberships_tenant_insert", "memberships_tenant_update",
            "memberships_tenant_delete", "memberships_select_admin_tenant", "roles_tenant_isolation",
            "role_permissions_tenant_isolation", "experiments_tenant_isolation", "results_tenant_isolation",
            "metrics_tenant_isolation", "documents_tenant_isolation", "chunks_tenant_isolation",
            "embeddings_tenant_isolation", "membership_roles_tenant_isolation",
            "ingestion_runs_tenant_isolation", "experiment_status_transitions_tenant_isolation",
            "audit_events_tenant_admin_select",
        }
        self.assertIn("CREATE FUNCTION public.tenant_session_scope_is_valid()", migration)
        self.assertIn("ALTER FUNCTION public.tenant_session_scope_is_valid() OWNER TO session_issuer_owner", migration)
        self.assertIn("REVOKE ALL ON FUNCTION public.tenant_session_scope_is_valid() FROM PUBLIC", migration)
        self.assertIn("GRANT EXECUTE ON FUNCTION public.tenant_session_scope_is_valid() TO app_runtime", migration)
        for policy in expected:
            with self.subTest(policy=policy):
                start = migration.index(f"CREATE POLICY {policy}")
                end = migration.find("CREATE POLICY ", start + 1)
                definition = migration[start:end if end != -1 else None]
                self.assertIn("public.tenant_session_scope_is_valid()", definition)

    def test_migration_revokes_public_issue_execution_and_regrants_curated_view_access(self) -> None:
        migration = Path("migrations/versions/20260330_17_session_proof_rls.py").read_text(encoding="utf-8")
        issue = "public.issue_tenant_session(uuid,integer,varchar,varchar,timestamptz)"
        self.assertIn(f"REVOKE ALL ON FUNCTION {issue} FROM PUBLIC", migration)
        self.assertIn(f"GRANT EXECUTE ON FUNCTION {issue} TO auth_runtime", migration)
        for view in ("assistant_experiments", "assistant_results", "assistant_metrics"):
            self.assertIn(f"GRANT SELECT ON TABLE public.{view} TO assistant_reader", migration)
        self.assertIn("has_function_privilege('public', p, 'EXECUTE')", migration)

    def test_every_recreated_runtime_policy_is_app_runtime_only_and_proof_bound(self) -> None:
        migration = Path("migrations/versions/20260330_17_session_proof_rls.py").read_text(encoding="utf-8")
        policy_names = (
            "tenants_tenant_isolation", "roles_tenant_isolation", "role_permissions_tenant_isolation",
            "experiments_tenant_isolation", "results_tenant_isolation", "metrics_tenant_isolation",
            "documents_tenant_isolation", "chunks_tenant_isolation", "embeddings_tenant_isolation",
            "membership_roles_tenant_isolation", "ingestion_runs_tenant_isolation",
            "experiment_status_transitions_tenant_isolation", "memberships_tenant_insert",
            "memberships_tenant_update", "memberships_tenant_delete", "memberships_select_admin_tenant",
            "audit_events_tenant_admin_select",
        )
        for name in policy_names:
            with self.subTest(policy=name):
                start = migration.index(f"CREATE POLICY {name}")
                end = migration.find("CREATE POLICY ", start + 1)
                definition = migration[start:end if end != -1 else None]
                self.assertIn("TO app_runtime", definition)
                self.assertIn("public.tenant_session_scope_is_valid()", definition)
        self.assertIn("FOR INSERT TO app_runtime", migration)
        self.assertIn("FOR UPDATE TO app_runtime", migration)
        self.assertIn("FOR DELETE TO app_runtime", migration)
        self.assertIn("FOR SELECT TO app_runtime", migration)
        self.assertIn("DROP POLICY memberships_select_own ON public.memberships", migration)
        self.assertIn("CREATE POLICY memberships_select_own ON public.memberships FOR SELECT TO app_runtime", migration)
        self.assertIn("DROP POLICY audit_events_definer_insert ON public.audit_events", migration)
        self.assertIn("CREATE POLICY audit_events_definer_insert ON public.audit_events FOR INSERT TO project_owner", migration)
        self.assertIn("CREATE POLICY audit_events_definer_global_select ON public.audit_events FOR SELECT TO project_owner", migration)

    def test_downgrade_restores_the_original_chunks_policy_without_a_uuid_text_comparison(self) -> None:
        migration = Path("migrations/versions/20260330_17_session_proof_rls.py").read_text(encoding="utf-8")
        downgrade = migration[migration.index("def downgrade"):]
        policy = downgrade[downgrade.index("CREATE POLICY chunks_tenant_isolation"):downgrade.index("DROP POLICY embeddings_tenant_isolation")]
        self.assertIn("tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid", policy)
        self.assertNotIn("tenant_id=NULLIF(current_setting('app.user_id',true),'')", policy)
        self.assertIn("DROP FUNCTION IF EXISTS public.tenant_session_scope_is_valid()", downgrade)

    def test_audit_verified_membership_definer_has_only_its_forced_rls_lookup_policy(self) -> None:
        migration = Path("migrations/versions/20260330_17_session_proof_rls.py").read_text(encoding="utf-8")
        upgrade = migration[migration.index("def upgrade"):migration.index("def downgrade")]
        downgrade = migration[migration.index("def downgrade"):]
        policy = "memberships_project_owner_audit_verified_membership_lookup"
        create = f"CREATE POLICY {policy} ON public.memberships FOR SELECT TO project_owner USING (true)"
        self.assertIn("ALTER TABLE public.memberships FORCE ROW LEVEL SECURITY", upgrade)
        self.assertIn(create, upgrade)
        self.assertEqual(upgrade.count("ON public.memberships FOR SELECT TO project_owner"), 1)
        self.assertNotIn("TO app_runtime USING (true)", upgrade)
        self.assertNotIn("TO auth_runtime USING (true)", upgrade)
        self.assertNotIn("TO assistant_reader USING (true)", upgrade)
        self.assertIn(f"DROP POLICY IF EXISTS {policy} ON public.memberships", downgrade)

    def test_current_tenant_admin_definer_has_exact_forced_rls_lookup_policies(self) -> None:
        migration = Path("migrations/versions/20260330_17_session_proof_rls.py").read_text(encoding="utf-8")
        upgrade = migration[migration.index("def upgrade"):migration.index("def downgrade")]
        downgrade = migration[migration.index("def downgrade"):]
        policies = (
            "membership_roles_project_owner_current_tenant_is_admin_lookup",
            "roles_project_owner_current_tenant_is_admin_lookup",
        )
        for table, policy in zip(("membership_roles", "roles"), policies, strict=True):
            with self.subTest(table=table):
                self.assertIn(f"CREATE POLICY {policy} ON public.{table} FOR SELECT TO project_owner USING (true)", upgrade)
                self.assertIn(f"DROP POLICY IF EXISTS {policy} ON public.{table}", downgrade)
        self.assertEqual(upgrade.count("ON public.membership_roles FOR SELECT TO project_owner"), 1)
        self.assertEqual(upgrade.count("ON public.roles FOR SELECT TO project_owner"), 1)
        self.assertIn("CREATE OR REPLACE FUNCTION public.current_tenant_is_admin()", upgrade)
        function = upgrade[upgrade.index("CREATE OR REPLACE FUNCTION public.current_tenant_is_admin()"):upgrade.index("DROP POLICY memberships_tenant_insert")]
        self.assertIn("public.tenant_session_scope_is_valid()", function)
        self.assertIn("GRANT EXECUTE ON FUNCTION public.tenant_session_scope_is_valid() TO project_owner", upgrade)
        for role in ("app_runtime", "auth_runtime", "assistant_reader"):
            self.assertNotIn(f"ON public.membership_roles FOR SELECT TO {role} USING (true)", upgrade)
            self.assertNotIn(f"ON public.roles FOR SELECT TO {role} USING (true)", upgrade)

    def test_assistant_view_owner_has_exact_forced_rls_support_policies_only(self) -> None:
        migration = Path("migrations/versions/20260330_17_session_proof_rls.py").read_text(encoding="utf-8")
        upgrade = migration[migration.index("def upgrade"):migration.index("def downgrade")]
        downgrade = migration[migration.index("def downgrade"):]
        support = (
            ("experiments", "experiments_project_owner_assistant_view_lookup"),
            ("results", "results_project_owner_assistant_view_lookup"),
            ("metrics", "metrics_project_owner_assistant_view_lookup"),
        )
        for table, policy in support:
            with self.subTest(table=table):
                self.assertIn(
                    f"CREATE POLICY {policy} ON public.{table} FOR SELECT TO project_owner USING (true)",
                    upgrade,
                )
                self.assertIn(f"DROP POLICY IF EXISTS {policy} ON public.{table}", downgrade)
        self.assertEqual(upgrade.count("FOR SELECT TO project_owner USING (true)"), 6)
        for table in ("documents", "chunks", "embeddings", "sessions"):
            self.assertNotIn(f"ON public.{table} FOR SELECT TO project_owner USING (true)", upgrade)
        for role in ("app_runtime", "auth_runtime", "assistant_reader"):
            self.assertNotIn(f"FOR SELECT TO {role} USING (true)", upgrade)

    def test_admin_tools_project_owner_has_exact_force_rls_fixture_write_policies(self) -> None:
        migration = Path("migrations/versions/20260330_17_session_proof_rls.py").read_text(encoding="utf-8")
        upgrade = migration[migration.index("def upgrade"):migration.index("def downgrade")]
        downgrade = migration[migration.index("def downgrade"):]
        fixture_tables = (
            "tenants", "memberships", "roles", "role_permissions", "membership_roles",
            "experiments", "results", "metrics", "documents", "chunks", "embeddings",
        )
        for table in fixture_tables:
            with self.subTest(table=table):
                policy = f"{table}_project_owner_admin_tools"
                self.assertIn(
                    f"CREATE POLICY {policy} ON public.{table} FOR ALL TO project_owner USING (true) WITH CHECK (true)",
                    upgrade,
                )
                self.assertIn(f"DROP POLICY IF EXISTS {policy} ON public.{table}", downgrade)
        self.assertNotIn("CREATE POLICY users_project_owner_admin_tools", upgrade)
        self.assertNotIn("CREATE POLICY permissions_project_owner_admin_tools", upgrade)
        for role in ("PUBLIC", "app_runtime", "auth_runtime", "assistant_reader"):
            self.assertNotIn(f"TO {role} USING (true) WITH CHECK (true)", upgrade)

    def test_assistant_uses_digest_context_and_transaction_local_bound_settings(self) -> None:
        service = Path("app/assistant/service.py").read_text(encoding="utf-8")
        sql = Path("app/assistant/sql.py").read_text(encoding="utf-8")
        api = Path("app/api/assistant.py").read_text(encoding="utf-8")
        self.assertIn("session_digest", service)
        self.assertIn("repr=False", service)
        self.assertIn("context=context", sql)
        self.assertNotIn("verifies_membership", sql)
        self.assertIn("app.session_proof", sql)
        self.assertIn("app.account_scope", sql)
        self.assertIn("set_config", sql)
        self.assertIn("state[\"session_digest\"]", api)


if __name__ == "__main__":
    unittest.main()
