"""Isolated platform authentication surface; aggregate reads are deliberately absent."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.auth import _codec, _csrf, db_session
from app.security.password import verify_password
from app.security.session_issuer import SessionIssueUnavailable, issue_platform_session

router = APIRouter(prefix="/api/platform", tags=["platform"])
_SESSION_COOKIE = "platform_session_token"
_CSRF_COOKIE = "platform_csrf_token"
_GENERIC_LOGIN_FAILURE = "Invalid platform credentials."
_PLATFORM_DENIAL_ACTION = "platform.route_denied"
_MAX_PAGE_SIZE = 50


class LoginPayload(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


def _deny(db: Session) -> None:
    """Record only a fixed actorless event; never accept caller metadata."""
    db.execute(text("SELECT public.append_platform_denial()"))
    db.commit()


def _platform_session(db: Session, raw: str | None) -> dict:
    if not raw:
        raise HTTPException(status_code=401, detail="Platform authentication required.")
    digest = _codec().digest(raw)
    state = db.execute(
        text("SELECT * FROM public.resolve_platform_session(:proof)"), {"proof": digest}
    ).mappings().first()
    if not state or state["account_scope"] != 'platform':
        _deny(db)
        raise HTTPException(status_code=403, detail="Platform access denied.")
    result = dict(state)
    result["session_digest"] = digest
    return result


@router.post("/login")
def login(payload: LoginPayload, response: Response, db: Session = Depends(db_session)) -> dict:
    user = db.execute(text("""
        SELECT u.id, u.password_hash, u.credential_version
        FROM public.users u JOIN public.platform_admins p ON p.user_id=u.id
        WHERE u.email=:email AND u.account_scope='platform' AND p.enabled
    """), {"email": payload.email.lower()}).mappings().first()
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail=_GENERIC_LOGIN_FAILURE)
    token, csrf = _codec().issue(), _codec().issue()
    try:
        issue_platform_session(user["id"], int(user["credential_version"]), _codec().digest(token), _codec().digest(csrf))
    except SessionIssueUnavailable as exc:
        raise HTTPException(status_code=401, detail=_GENERIC_LOGIN_FAILURE) from exc
    response.set_cookie(_SESSION_COOKIE, token, httponly=True, samesite="lax")
    response.set_cookie(_CSRF_COOKIE, csrf, httponly=False, samesite="lax")
    return {"authenticated": True}


@router.post("/logout")
def logout(request: Request, response: Response, platform_session_token: Annotated[str | None, Cookie()] = None,
           platform_csrf_token: Annotated[str | None, Cookie()] = None,
           x_csrf_token: Annotated[str | None, Header()] = None, db: Session = Depends(db_session)) -> dict:
    state = _platform_session(db, platform_session_token)
    _csrf(db, state, request, x_csrf_token, platform_csrf_token)
    db.execute(text("SELECT public.revoke_own_session(:token,:csrf,:scope)"), {
        "token": state["session_digest"], "csrf": _codec().digest(x_csrf_token or ""), "scope": 'platform',
    })
    db.commit()
    response.delete_cookie(_SESSION_COOKIE)
    response.delete_cookie(_CSRF_COOKIE)
    return {"logged_out": True}


@router.get("/summary")
def summary(platform_session_token: Annotated[str | None, Cookie()] = None, db: Session = Depends(db_session)) -> dict:
    """Fixed platform-wide aggregate counts only; no tenant content or identifiers beyond counts."""
    state = _platform_session(db, platform_session_token)
    row = db.execute(
        text("SELECT * FROM public.platform_dashboard_summary(:proof)"), {"proof": state["session_digest"]}
    ).mappings().first()
    db.commit()
    if not row:
        raise HTTPException(status_code=403, detail="Platform access denied.")
    return dict(row)


@router.get("/tenant-overview")
def tenant_overview(
    search: Annotated[str, Query(max_length=120)] = "",
    limit: Annotated[int, Query(ge=1, le=_MAX_PAGE_SIZE)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    platform_session_token: Annotated[str | None, Cookie()] = None,
    db: Session = Depends(db_session),
) -> dict:
    """Bounded, searchable tenant aggregate listing; never returns content, members, or documents."""
    state = _platform_session(db, platform_session_token)
    rows = db.execute(
        text("SELECT * FROM public.platform_tenant_overview(:proof,:search,:limit,:offset)"),
        {"proof": state["session_digest"], "search": search, "limit": limit, "offset": offset},
    ).mappings().all()
    db.commit()
    total = int(rows[0]["total_count"]) if rows else 0
    items = [{key: value for key, value in dict(row).items() if key != "total_count"} for row in rows]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/tenant-overview/{tenant_id}")
def tenant_overview_detail(
    tenant_id: UUID, platform_session_token: Annotated[str | None, Cookie()] = None, db: Session = Depends(db_session),
) -> dict:
    """Single-tenant aggregate/status counts only; no experiment, document, or member content."""
    state = _platform_session(db, platform_session_token)
    row = db.execute(
        text("SELECT * FROM public.platform_tenant_detail(:proof,:tenant)"),
        {"proof": state["session_digest"], "tenant": tenant_id},
    ).mappings().first()
    db.commit()
    if not row:
        raise HTTPException(status_code=404, detail="Tenant not found.")
    return dict(row)
