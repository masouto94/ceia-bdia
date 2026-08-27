"""Focused experiment policy, schema, pagination, and migration checks."""

import unittest
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

_ENVIRONMENT = {
    "RUNTIME_DATABASE_URL": "postgresql+psycopg://runtime:password@db/student_project",
        "AUTH_DATABASE_URL": "postgresql+psycopg://auth:password@db/student_project",
    "ASSISTANT_DATABASE_URL": "postgresql+psycopg://assistant:password@db/student_project",
    "MINIO_ACCESS_KEY": "local-user", "MINIO_SECRET_KEY": "local-password",
    "SMTP_FROM": "noreply@example.test", "SESSION_SECRET": "test-session-secret",
    "RECOVERY_TOKEN_SECRET": "test-recovery-secret",
}


class ExperimentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.environment = patch.dict("os.environ", _ENVIRONMENT, clear=False); cls.environment.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.environment.stop()

    def test_lifecycle_allows_only_forward_terminal_transitions(self) -> None:
        from app.domain.experiments import require_transition
        for current, target in (("draft", "running"), ("running", "completed"), ("running", "failed")):
            require_transition(current, target)
        for current, target in (("draft", "completed"), ("completed", "running"), ("failed", "running")):
            with self.assertRaises(ValueError): require_transition(current, target)

    def test_rename_archive_contract_rejects_empty_patch_and_supports_active_archive_filter(self) -> None:
        from pydantic import ValidationError

        from app.api.experiment_schemas import ExperimentUpdate
        from app.api.experiments import ExperimentListQuery

        update = ExperimentUpdate(name="  renamed experiment  ")
        self.assertEqual(update.name, "renamed experiment")
        self.assertTrue(ExperimentUpdate(archived=True).archived)
        self.assertFalse(ExperimentUpdate(archived=False).archived)
        for payload in ({}, {"name": "   "}, {"name": "x" * 201}):
            with self.assertRaises(ValidationError):
                ExperimentUpdate.model_validate(payload)
        self.assertEqual(ExperimentListQuery().archived, False)
        self.assertTrue(ExperimentListQuery(archived=True).archived)

    def test_archive_restore_are_audited_and_preserve_lifecycle_data(self) -> None:
        from uuid import uuid4

        from app.api.experiment_schemas import ExperimentUpdate
        from app.services.experiments import ExperimentService

        tenant, experiment, actor = uuid4(), uuid4(), uuid4()

        class Repository:
            def __init__(self, current: dict[str, Any]) -> None:
                self.current = current
                self.archive_calls: list[tuple[object, ...]] = []
                self.audit_calls: list[tuple[object, ...]] = []

            def get(self, _tenant, _experiment):
                return self.current

            def update(self, *_args):
                raise AssertionError("archive must not change lifecycle data")

            def set_archived(self, *args):
                self.archive_calls.append(args)
                return {**self.current, "archived_at": None if args[2] is False else "now"}

            def append_audit_event(self, *args):
                self.audit_calls.append(args)

        archived = Repository({"id": experiment, "status": "completed", "results": [{"id": uuid4()}], "status_history": [{"id": uuid4()}], "archived_at": None})
        item = ExperimentService(cast(Any, archived)).update(tenant, actor, experiment, ExperimentUpdate(archived=True))
        self.assertIsNotNone(item)
        self.assertEqual(archived.archive_calls, [(tenant, experiment, True, actor)])
        self.assertEqual(archived.audit_calls, [(tenant, actor, experiment, "experiment.archived", False, True)])
        self.assertEqual(len(archived.current["results"]), 1)
        self.assertEqual(len(archived.current["status_history"]), 1)

        restored = Repository({"id": experiment, "status": "failed", "archived_at": "yesterday"})
        ExperimentService(cast(Any, restored)).update(tenant, actor, experiment, ExperimentUpdate(archived=False))
        self.assertEqual(restored.archive_calls, [(tenant, experiment, False, actor)])
        self.assertEqual(restored.audit_calls, [(tenant, actor, experiment, "experiment.restored", True, False)])

    def test_running_or_archived_experiments_reject_forbidden_mutations(self) -> None:
        from uuid import uuid4

        from app.api.experiment_schemas import ExperimentUpdate, ResultCreate
        from app.services.experiments import ExperimentService

        tenant, experiment, actor = uuid4(), uuid4(), uuid4()

        class Repository:
            def __init__(self, current: dict[str, Any]) -> None:
                self.current = current

            def get(self, _tenant, _experiment):
                return self.current

        with self.assertRaisesRegex(ValueError, "running"):
            ExperimentService(cast(Any, Repository({"status": "running", "archived_at": None}))).update(tenant, actor, experiment, ExperimentUpdate(archived=True))
        with self.assertRaisesRegex(ValueError, "archived"):
            ExperimentService(cast(Any, Repository({"status": "completed", "archived_at": "yesterday"}))).update(tenant, actor, experiment, ExperimentUpdate(status="completed"))
        with self.assertRaisesRegex(ValueError, "archived"):
            ExperimentService(cast(Any, Repository({"status": "running", "archived_at": "yesterday"}))).append_result(tenant, actor, experiment, ResultCreate(status="completed"))
        with self.assertRaisesRegex(ValueError, "unchanged"):
            ExperimentService(cast(Any, Repository({"status": "completed", "name": "same", "archived_at": None}))).update(tenant, actor, experiment, ExperimentUpdate(name="same"))

    def test_archive_migration_and_repository_are_tenant_scoped_and_auditable(self) -> None:
        source = Path("migrations/versions/20260330_13_experiment_archive.py").read_text()
        for invariant in (
            'down_revision = "20260330_12"',
            "archived_at timestamptz",
            "archived_by uuid",
            "FOREIGN KEY (tenant_id,archived_by) REFERENCES memberships(tenant_id,user_id)",
            "experiments_tenant_archived_idx",
            "results_reject_archived_experiment",
        ):
            self.assertIn(invariant, source)
        repository = Path("app/repositories/experiments.py").read_text()
        self.assertIn("e.archived_at IS NULL", repository)
        self.assertIn("e.archived_at IS NOT NULL", repository)
        self.assertIn("record_audit_event", repository)

    def test_status_transition_reason_is_trimmed_bounded_and_requires_status(self) -> None:
        from pydantic import ValidationError

        from app.api.experiment_schemas import ExperimentUpdate

        self.assertEqual(
            ExperimentUpdate(status="running", reason="  started by scheduler  ").reason,
            "started by scheduler",
        )
        with self.assertRaises(ValidationError):
            ExperimentUpdate(reason="why")
        with self.assertRaises(ValidationError):
            ExperimentUpdate(status="running", reason="x" * 1001)
        with self.assertRaises(ValidationError):
            ExperimentUpdate.model_validate({"status": "running", "reason": 1})

    def test_status_transitions_append_history_with_the_authenticated_actor(self) -> None:
        from uuid import uuid4

        from app.api.experiment_schemas import ExperimentUpdate
        from app.services.experiments import ExperimentService

        tenant, experiment, actor = uuid4(), uuid4(), uuid4()

        class Repository:
            def __init__(self) -> None:
                self.update_calls: list[tuple[object, ...]] = []
                self.history_calls: list[tuple[object, ...]] = []

            def get(self, _tenant, _experiment):
                return {"status": "draft"}

            def update(self, *args):
                self.update_calls.append(args)
                return {"status": "running"}

            def append_status_transition(self, *args):
                self.history_calls.append(args)

            def append_audit_event(self, *_args):
                pass

        repository = Repository()
        item = ExperimentService(cast(Any, repository)).update(
            tenant, actor, experiment, ExperimentUpdate(status="running", reason="  begin  ")
        )
        self.assertEqual(item, {"status": "running"})
        self.assertEqual(repository.history_calls, [(tenant, experiment, "draft", "running", actor, "begin")])

        ExperimentService(cast(Any, repository)).update(tenant, actor, experiment, ExperimentUpdate(name="renamed"))
        self.assertEqual(len(repository.history_calls), 1)

    def test_detail_history_is_ordered_without_changing_list_contracts(self) -> None:
        source = Path("app/repositories/experiments.py").read_text()
        self.assertIn('item["status_history"]', source)
        self.assertIn("ORDER BY occurred_at,id", source)
        self.assertEqual(source.count("experiment_status_transitions"), 2)

    def test_result_terminal_closure_is_validated_and_preserves_backward_compatibility(self) -> None:
        from pydantic import ValidationError

        from app.api.experiment_schemas import ResultCreate

        self.assertIsNone(ResultCreate(status="completed").terminal_status)
        closure = ResultCreate(
            status="failed",
            terminal_status="completed",
            transition_reason="  training budget exhausted  ",
        )
        self.assertEqual(closure.status, "failed")
        self.assertEqual(closure.terminal_status, "completed")
        self.assertEqual(closure.transition_reason, "training budget exhausted")
        for payload in (
            {"status": "completed", "transition_reason": "why"},
            {"status": "completed", "terminal_status": "running"},
            {"status": "completed", "terminal_status": "failed", "transition_reason": "x" * 1001},
        ):
            with self.assertRaises(ValidationError):
                ResultCreate.model_validate(payload)

    def test_terminal_result_closure_appends_history_with_authenticated_actor(self) -> None:
        from uuid import uuid4

        from app.api.experiment_schemas import ResultCreate
        from app.services.experiments import ExperimentService

        tenant, experiment, actor = uuid4(), uuid4(), uuid4()

        class Repository:
            def __init__(self) -> None:
                self.update_calls: list[tuple[object, ...]] = []
                self.history_calls: list[tuple[object, ...]] = []

            def get(self, _tenant, _experiment):
                return {"id": experiment, "status": "running"}

            def append_result(self, *_args):
                return {"id": uuid4(), "status": "failed", "metrics": []}

            def update(self, *args):
                self.update_calls.append(args)
                return {"id": experiment, "status": "completed"}

            def append_status_transition(self, *args):
                self.history_calls.append(args)

        repository = Repository()
        closed = ExperimentService(cast(Any, repository)).append_result(
            tenant,
            actor,
            experiment,
            ResultCreate(
                status="failed",
                terminal_status="completed",
                transition_reason="  manual review  ",
            ),
        )
        assert closed is not None
        self.assertEqual(closed["experiment"], {"id": experiment, "status": "completed"})
        self.assertEqual(repository.update_calls, [(tenant, experiment, None, "completed")])
        self.assertEqual(
            repository.history_calls,
            [(tenant, experiment, "running", "completed", actor, "manual review")],
        )

        repository = Repository()
        result = ExperimentService(cast(Any, repository)).append_result(
            tenant, actor, experiment, ResultCreate(status="completed")
        )
        assert result is not None
        self.assertNotIn("experiment", result)
        self.assertEqual(repository.update_calls, [])
        self.assertEqual(repository.history_calls, [])

    def test_metrics_require_the_declared_value_type(self) -> None:
        from pydantic import ValidationError
        from app.api.experiment_schemas import MetricCreate, MetricType
        for kind, value in (("number", 1.5), ("text", "ok"), ("boolean", True), ("json", {"fold": 1})):
            self.assertEqual(MetricCreate(name="score", type=cast(MetricType, kind), value=value).value, value)
        with self.assertRaises(ValidationError): MetricCreate(name="score", type="number", value=True)

    def test_pagination_is_bounded(self) -> None:
        from app.services.pagination import Page, PageRequest
        self.assertEqual(PageRequest(2, 20).offset, 20)
        self.assertEqual(Page([], 21, 1, 20).pages, 2)
        for values in ((0, 20), (1, 200)):
            with self.assertRaises(ValueError): PageRequest(*values)

    def test_migration_enforces_tenant_fks_and_append_only_history(self) -> None:
        source = Path("migrations/versions/20260330_07_experiments.py").read_text()
        for invariant in ("results_tenant_experiment_fk", "metrics_tenant_result_fk", "metrics_typed_value_check", "results_append_only", "metrics_append_only", "REVOKE UPDATE, DELETE"):
            self.assertIn(invariant, source)
        self.assertIn('down_revision = "20260330_06"', source)

    def test_status_history_migration_uses_tenant_fks_rls_and_append_only_guards(self) -> None:
        source = Path("migrations/versions/20260330_11_experiment_status_history.py").read_text()
        for invariant in (
            "experiment_status_transitions",
            "FOREIGN KEY (tenant_id,experiment_id) REFERENCES experiments(tenant_id,id)",
            "ENABLE ROW LEVEL SECURITY",
            "FORCE ROW LEVEL SECURITY",
            "experiment_status_transitions_tenant_isolation",
            "experiment_status_transitions_append_only",
            "REVOKE UPDATE, DELETE ON experiment_status_transitions FROM app_runtime",
        ):
            self.assertIn(invariant, source)
        self.assertIn('down_revision = "20260330_10"', source)

    def test_experiment_routes_expose_no_historical_mutation(self) -> None:
        from app.main import app
        methods = {(getattr(route, "path", ""), method) for route in app.routes for method in getattr(route, "methods", set())}
        self.assertIn(("/api/experiments", "GET"), methods)
        self.assertIn(("/api/experiments/{experiment_id}/results", "POST"), methods)
        self.assertNotIn(("/api/experiments/{experiment_id}/results/{result_id}", "PATCH"), methods)

    def test_experiment_query_helpers_validate_and_escape_literal_search(self) -> None:
        from pydantic import ValidationError

        from app.api.experiments import ExperimentListQuery
        from app.repositories.experiments import escape_like

        query = ExperimentListQuery(
            page=2,
            per_page=20,
            search="  100%_ready\\  ",
            status="running",
            sort="result_count:desc",
        )
        self.assertEqual(query.search, "100%_ready\\")
        self.assertEqual(query.status, "running")
        self.assertEqual(query.sort, "result_count:desc")
        self.assertEqual(escape_like(query.search), r"100\%\_ready\\")
        invalid_payloads: tuple[dict[str, object], ...] = (
            {"status": "unknown"},
            {"status": ""},
            {"sort": "name:drop"},
        )
        for payload in invalid_payloads:
            with self.assertRaises(ValidationError):
                ExperimentListQuery.model_validate(cast(object, payload))


if __name__ == "__main__":
    unittest.main()
