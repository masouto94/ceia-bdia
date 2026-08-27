"""Tenant-bound normalized audit read model."""

from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


AUDIT_EVENTS_CTE = """
WITH events AS (
  SELECT a.id, a.created_at AS occurred_at, a.actor_id,
    CASE a.action
      WHEN 'registration' THEN 'auth.registration' WHEN 'login' THEN 'auth.login'
      WHEN 'csrf' THEN 'security.csrf_denied' WHEN 'recovery_request' THEN 'auth.recovery.request'
      WHEN 'recovery_confirm' THEN 'auth.recovery.confirm' WHEN 'membership_change' THEN 'membership.role_changed'
      WHEN 'experiment_archived' THEN 'experiment.archived' WHEN 'experiment_restored' THEN 'experiment.restored'
      WHEN 'experiment_renamed' THEN 'experiment.renamed' ELSE a.action END AS action,
    CASE WHEN a.outcome = 'accepted' THEN 'success' ELSE a.outcome END AS outcome,
    a.resource, a.metadata AS detail, 'audit'::text AS source, 3 AS source_priority
  FROM audit_events a WHERE a.tenant_id = :tenant
  UNION ALL
  SELECT s.id, s.occurred_at, s.actor_id, 'experiment.status_transition', 'success',
    'experiment:' || s.experiment_id::text,
    jsonb_build_object('previous_status',s.previous_status,'next_status',s.next_status), 'experiment_status', 2
  FROM experiment_status_transitions s WHERE s.tenant_id = :tenant
  UNION ALL
  SELECT i.id, i.created_at, NULL::uuid,
    CASE WHEN i.status = 'failed' THEN 'document.ingest.failed' ELSE 'document.ingest.completed' END,
    CASE WHEN i.status = 'failed' THEN 'failed' ELSE 'success' END,
    'document:' || i.document_id::text, jsonb_build_object('chunk_count',i.chunk_count), 'ingestion', 1
  FROM ingestion_runs i WHERE i.tenant_id = :tenant
), filtered AS (
  SELECT e.*, u.email FROM events e
  LEFT JOIN memberships m ON m.tenant_id = :tenant AND m.user_id = e.actor_id
  LEFT JOIN users u ON u.id = m.user_id
  WHERE e.occurred_at >= :from_at AND e.occurred_at < :to_at
    AND (CAST(:actor_id AS uuid) IS NULL OR e.actor_id = :actor_id)
    AND (CAST(:action AS text) IS NULL OR e.action = :action)
    AND (CAST(:outcome AS text) IS NULL OR e.outcome = :outcome)
    AND (:search = '' OR e.action ILIKE :search ESCAPE '\\' OR COALESCE(e.resource,'') ILIKE :search ESCAPE '\\')
)
"""

AUDIT_EVENTS_SQL = AUDIT_EVENTS_CTE + """
SELECT id, occurred_at, actor_id, email, action, outcome, resource, detail, source, source_priority
FROM filtered
ORDER BY occurred_at DESC, source_priority DESC, id DESC
LIMIT :limit OFFSET :offset
"""

AUDIT_EVENTS_COUNT_SQL = AUDIT_EVENTS_CTE + "SELECT count(*) AS total FROM filtered"


def escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class AuditRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(self, tenant: UUID, *, page: int, per_page: int, from_at: datetime, to_at: datetime,
             actor_id: UUID | None, action: str | None, outcome: str | None, search: str) -> tuple[list[dict], int]:
        values = {
            "tenant": tenant, "from_at": from_at, "to_at": to_at, "actor_id": actor_id,
            "action": action, "outcome": outcome, "search": f"%{escape_like(search)}%" if search else "",
            "limit": per_page, "offset": (page - 1) * per_page,
        }
        # pi-lens-ignore: python-sql-injection
        rows = self.db.execute(text(AUDIT_EVENTS_SQL), values).mappings().all()
        # pi-lens-ignore: python-sql-injection
        total = cast(int, self.db.execute(text(AUDIT_EVENTS_COUNT_SQL), values).scalar_one())
        items = [{
            "id": str(row["id"]), "occurred_at": row["occurred_at"],
            "actor": None if row["actor_id"] is None or row["email"] is None else {"user_id": str(row["actor_id"]), "email": row["email"]},
            "action": row["action"], "outcome": row["outcome"], "resource": row["resource"],
            "detail": row["detail"], "source": row["source"],
        } for row in rows]
        return items, total
