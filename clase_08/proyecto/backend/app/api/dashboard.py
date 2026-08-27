# pyright: reportMissingImports=false
"""Read-only tenant dashboard endpoint."""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.auth import _session, _tenant_context, db_session
from app.api.dashboard_schemas import DashboardQuery
from app.repositories.dashboard import DashboardRepository

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
def get_dashboard(
    from_date: Annotated[date, Query(alias="from")],
    to_date: Annotated[date, Query(alias="to")],
    search: str = Query(default="", max_length=120),
    status: Literal["", "draft", "running", "completed", "failed"] = Query(default=""),
    sort: Literal["created_at:desc", "created_at:asc", "name:asc", "name:desc", "result_count:desc"] = Query(default="created_at:desc"),
    page: int = Query(default=1),
    per_page: int = Query(default=10),
    session_token: Annotated[str | None, Cookie()] = None,
    db: Session = Depends(db_session),
) -> dict:
    try:
        query = DashboardQuery(from_date=from_date, to_date=to_date, search=search, status=status, sort=sort, page=page, per_page=per_page)
    except ValueError as exc:
        raise HTTPException(422, "Los datos enviados no son válidos.") from exc
    state = _session(db, session_token)
    db.commit()
    tenant = _tenant_context(db, state, {"admin", "member", "viewer"})
    with db.begin():
        # pi-lens-ignore: python-sql-injection
        db.execute(text("SELECT set_config('app.session_proof', :proof, true), set_config('app.account_scope', 'tenant', true), set_config('app.user_id', :user, true), set_config('app.tenant_id', :tenant, true)"), {"proof": state["session_digest"], "user": str(state["user_id"]), "tenant": str(tenant)})
        return DashboardRepository(db).overview(tenant, query.from_date, query.to_date, query.search, query.status, query.sort, query.page, query.per_page)
