"""Transaction-local trusted database context helpers."""

# pyright: reportMissingImports=false

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from contextlib import contextmanager
from typing import Protocol
from uuid import UUID

from sqlalchemy import text


class TransactionSession(Protocol):
    def begin(self) -> AbstractContextManager[object]: ...
    def close(self) -> None: ...
    def execute(self, statement, values: dict[str, str]) -> object: ...


MembershipVerifier = Callable[[UUID, UUID], bool]


@contextmanager
def trusted_tenant_transaction(
    session_factory: Callable[[], TransactionSession],
    user_id: UUID | None,
    tenant_id: UUID | None,
    verifies_membership: MembershipVerifier,
) -> Iterator[TransactionSession]:
    """Open a transaction only after server-side membership verification.

    PostgreSQL clears ``set_config(..., true)`` values when this transaction ends,
    so a returned pooled connection cannot retain either trusted identifier.
    """
    if user_id is None or tenant_id is None:
        raise ValueError("trusted user and tenant context are required")
    if not verifies_membership(user_id, tenant_id):
        raise PermissionError("user is not an active member of the selected tenant")

    session = session_factory()
    try:
        with session.begin():
            session.execute(
                text("SELECT set_config('app.user_id', :user_id, true)"),
                {"user_id": str(user_id)},
            )
            session.execute(
                text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            yield session
    finally:
        session.close()
