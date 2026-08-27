"""Single safe application seam for immutable audit writes."""

import json
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


def append_audit_event(
    db: Session, action: str, outcome: str, actor: UUID | None = None,
    tenant: UUID | None = None, resource: str | None = None,
    metadata: dict[str, object] | None = None,
) -> None:
    """Delegate validation, identifiers, timestamps, and authorization to PostgreSQL."""
    # pi-lens-ignore: python-sql-injection
    db.execute(
        text("SELECT append_audit_event(:actor,:tenant,:action,:outcome,:resource,CAST(:metadata AS jsonb))"),
        {"actor": actor, "tenant": tenant, "action": action, "outcome": outcome,
         "resource": resource, "metadata": json.dumps(metadata or {})},
    )
