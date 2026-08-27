# pyright: reportMissingImports=false, reportArgumentType=false

import unittest
from contextlib import contextmanager
from uuid import uuid4


class RecordingSession:
    def __init__(self) -> None:
        self.executed: list[tuple[str, dict[str, str]]] = []
        self.committed = False

    @contextmanager
    def begin(self):
        try:
            yield self
            self.committed = True
        finally:
            pass

    def execute(self, statement, values: dict[str, str]) -> None:
        self.executed.append((str(statement), values))

    def close(self) -> None:
        pass


class TrustedTenantContextTests(unittest.TestCase):
    def test_verified_context_is_transaction_local(self) -> None:
        from app.core.transactions import trusted_tenant_transaction

        user_id, tenant_id = uuid4(), uuid4()
        session = RecordingSession()
        with trusted_tenant_transaction(lambda: session, user_id, tenant_id, lambda *_: True):
            pass

        self.assertTrue(session.committed)
        self.assertEqual(
            [values for _, values in session.executed],
            [{"user_id": str(user_id)}, {"tenant_id": str(tenant_id)}],
        )
        self.assertTrue(all("set_config" in statement for statement, _ in session.executed))
        self.assertTrue(all(", true)" in statement for statement, _ in session.executed))

    def test_missing_or_forged_context_fails_before_a_transaction_starts(self) -> None:
        from app.core.transactions import trusted_tenant_transaction

        session = RecordingSession()
        user_id, tenant_id = uuid4(), uuid4()
        with self.assertRaises(PermissionError):
            with trusted_tenant_transaction(lambda: session, user_id, tenant_id, lambda *_: False):
                pass
        with self.assertRaises(ValueError):
            with trusted_tenant_transaction(lambda: session, user_id, None, lambda *_: True):
                pass

        self.assertEqual(session.executed, [])
        self.assertFalse(session.committed)


if __name__ == "__main__":
    unittest.main()
