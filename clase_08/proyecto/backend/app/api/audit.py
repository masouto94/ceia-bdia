"""Administrator-only audit trail endpoint."""

from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.auth import _session, _tenant_context, db_session
from app.repositories.audit import AuditRepository

router = APIRouter(prefix="/api/audit-events", tags=["audit"])
_ACTIONS = {
    "auth.registration", "auth.login", "auth.logout", "auth.recovery.request", "auth.recovery.confirm", "security.csrf_denied",
    "membership.created", "membership.role_changed", "membership.activation_changed", "document.upload", "document.ingest.started",
    "document.ingest.reprocessed", "document.ingest.completed", "document.ingest.failed", "experiment.created", "experiment.renamed",
    "experiment.result_added", "experiment.archived", "experiment.restored", "experiment.status_transition",
}
_OUTCOMES = {"success", "denied", "failed", "rate_limited"}


class AuditQuery(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    page: int = Field(default=1, ge=1)
    per_page: int = 25
    from_at: datetime | None = Field(default=None, alias="from")
    to_at: datetime | None = Field(default=None, alias="to")
    actor_id: UUID | None = None
    action: str | None = None
    outcome: str | None = None
    search: str = Field(default="", max_length=120)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page

    @model_validator(mode="before")
    @classmethod
    def normalize_date_only_bounds(cls, values: object) -> object:
        if not isinstance(values, dict):
            return values
        normalized = dict(values)
        for key, offset in (("from", 0), ("to", 1)):
            value = normalized.get(key)
            if isinstance(value, str) and len(value) == 10:
                try:
                    day = date.fromisoformat(value) + timedelta(days=offset)
                except ValueError:
                    continue
                normalized[key] = datetime.combine(day, time.min, UTC)
        return normalized

    @model_validator(mode="after")
    def bounded(self) -> "AuditQuery":
        if self.per_page not in {10, 20, 25, 50, 100}:
            raise ValueError("invalid per_page")
        today = datetime.now(UTC).date()
        self.from_at = self.from_at or datetime.combine(today - timedelta(days=6), time.min, UTC)
        self.to_at = self.to_at or datetime.combine(today + timedelta(days=1), time.min, UTC)
        if self.from_at.tzinfo is None:
            self.from_at = self.from_at.replace(tzinfo=UTC)
        if self.to_at.tzinfo is None:
            self.to_at = self.to_at.replace(tzinfo=UTC)
        # All ranges are half-open. Date-only `to` is normalized to the next UTC midnight.
        if self.to_at <= self.from_at or self.to_at - self.from_at > timedelta(days=31):
            raise ValueError("invalid date range")
        if self.action is not None and self.action not in _ACTIONS:
            raise ValueError("invalid action")
        if self.outcome is not None and self.outcome not in _OUTCOMES:
            raise ValueError("invalid outcome")
        self.search = self.search.strip()
        return self


@router.get("")
def list_audit_events(query: Annotated[AuditQuery, Query()], session_token: Annotated[str | None, Cookie()] = None,
                      db: Session = Depends(db_session)) -> dict:
    state = _session(db, session_token)
    db.commit()
    tenant = _tenant_context(db, state, {"admin"})
    with db.begin():
        # pi-lens-ignore: python-sql-injection
        db.execute(text("SELECT set_config('app.session_proof', :proof, true), set_config('app.account_scope', 'tenant', true), set_config('app.user_id', :user, true), set_config('app.tenant_id', :tenant, true)"),
                   {"proof": state["session_digest"], "user": str(state["user_id"]), "tenant": str(tenant)})
        from_at, to_at = query.from_at, query.to_at
        if from_at is None or to_at is None:
            raise HTTPException(status_code=422, detail="invalid date range")
        items, total = AuditRepository(db).list(tenant, page=query.page, per_page=query.per_page,
            from_at=from_at, to_at=to_at, actor_id=query.actor_id, action=query.action,
            outcome=query.outcome, search=query.search)
    return {"items": items, "total": total, "page": query.page, "per_page": query.per_page,
            "pages": (total + query.per_page - 1) // query.per_page}
