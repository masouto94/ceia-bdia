"""Identity HTTP boundary: opaque sessions, recovery, tenants, and fixed roles."""

# pyright: reportMissingImports=false

from datetime import UTC, datetime, timedelta
import json
import logging
from secrets import token_urlsafe
from typing import Annotated, Generator
from uuid import UUID, uuid4

from fastapi import APIRouter, Cookie, Depends, HTTPException, Header, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.audit import append_audit_event
from app.providers.mail import send_recovery
from app.security.password import hash_password, verify_password
from app.security.tokens import TokenCodec

router = APIRouter(prefix="/api", tags=["identity"])
logger = logging.getLogger(__name__)
_SESSION_COOKIE = "session_token"
_CSRF_COOKIE = "csrf_token"
_ROLES = {"admin", "member", "viewer"}


class RegisterPayload(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)
    tenant_name: str = Field(min_length=1, max_length=120)


class LoginPayload(BaseModel):
    email: EmailStr
    password: str


class RecoveryRequest(BaseModel):
    email: EmailStr


class RecoveryConfirm(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=256)


class MemberCreate(BaseModel):
    email: EmailStr
    role: str


class MemberUpdate(BaseModel):
    """Optional, bounded membership state changes for tenant administrators."""

    model_config = ConfigDict(extra="forbid")

    role: str | None = None
    active: bool | None = None

    @field_validator("role")
    @classmethod
    def role_is_allowed(cls, value: str | None) -> str | None:
        if value is not None and value not in _ROLES:
            raise ValueError("El rol debe ser admin, member o viewer.")
        return value


class MemberListParams(BaseModel):
    """Allowlisted query parameters for the tenant member directory."""

    model_config = ConfigDict(extra="forbid")

    page: int = 1
    per_page: int = 10
    search: str = ""
    role: str = ""
    status: str = ""
    sort: str = "email:asc"

    @field_validator("page")
    @classmethod
    def page_is_positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("El parámetro page debe ser mayor o igual a 1.")
        return value

    @field_validator("per_page")
    @classmethod
    def per_page_is_allowed(cls, value: int) -> int:
        if value not in {10, 20, 30, 40, 50}:
            raise ValueError("El parámetro per_page debe ser 10, 20, 30, 40 o 50.")
        return value

    @field_validator("role")
    @classmethod
    def role_is_allowed(cls, value: str) -> str:
        if value and value not in _ROLES:
            raise ValueError("El parámetro role debe ser admin, member o viewer.")
        return value

    @field_validator("status")
    @classmethod
    def status_is_allowed(cls, value: str) -> str:
        if value and value not in {"active", "inactive"}:
            raise ValueError("El parámetro status debe ser active o inactive.")
        return value

    @field_validator("sort")
    @classmethod
    def sort_is_allowed(cls, value: str) -> str:
        if value not in {f"{field}:{direction}" for field in ("email", "role", "status", "created_at") for direction in ("asc", "desc")}:
            raise ValueError("El parámetro sort no es válido.")
        return value


def _member_list_sql(params: MemberListParams) -> tuple[str, dict[str, object]]:
    """Build a parameterized tenant-scoped query from fixed SQL fragments only."""

    filters = ["m.tenant_id = :tenant"]
    values: dict[str, object] = {"limit": params.per_page, "offset": (params.page - 1) * params.per_page}
    if params.search:
        filters.append("u.email ILIKE :search")
        values["search"] = f"%{params.search.lower()}%"
    if params.role:
        filters.append("r.name = :role")
        values["role"] = params.role
    if params.status:
        filters.append("m.active = :active")
        values["active"] = params.status == "active"

    field, direction = params.sort.split(":", 1)
    order_columns = {
        "email": "u.email",
        "role": "r.name",
        "status": "m.active",
        "created_at": "u.created_at",
    }
    order = "DESC" if direction == "desc" else "ASC"
    where_clause = " AND ".join(filters)
    sql = f"""
        SELECT u.id AS user_id, u.email, r.name AS role, m.active, u.password_setup_required
        FROM memberships m
        JOIN users u ON u.id = m.user_id
        JOIN membership_roles mr ON mr.tenant_id = m.tenant_id AND mr.user_id = m.user_id
        JOIN roles r ON r.id = mr.role_id AND r.tenant_id = m.tenant_id
        WHERE {where_clause}
        ORDER BY {order_columns[field]} {order}, u.email ASC, u.id ASC
        LIMIT :limit OFFSET :offset
    """
    return sql, values


def _member_list_count_sql(params: MemberListParams) -> tuple[str, dict[str, object]]:
    sql, values = _member_list_sql(params)
    where_clause = sql.split("WHERE", 1)[1].split("ORDER BY", 1)[0]
    return f"""
        SELECT count(*)
        FROM memberships m
        JOIN users u ON u.id = m.user_id
        JOIN membership_roles mr ON mr.tenant_id = m.tenant_id AND mr.user_id = m.user_id
        JOIN roles r ON r.id = mr.role_id AND r.tenant_id = m.tenant_id
        WHERE {where_clause}
    """, {key: value for key, value in values.items() if key not in {"limit", "offset"}}


def db_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _codec() -> TokenCodec:
    return TokenCodec(settings.session_secret)


def _recovery_codec() -> TokenCodec:
    return TokenCodec(settings.recovery_token_secret)


def _now() -> datetime:
    return datetime.now(UTC)


def _audit(db: Session, action: str, outcome: str, actor: UUID | None = None, tenant: UUID | None = None, resource: str | None = None, metadata: dict[str, object] | None = None) -> None:
    """Compatibility seam for existing identity call sites; storage validates all values."""
    actions = {
        "registration": "auth.registration", "login": "auth.login", "logout": "auth.logout",
        "recovery_request": "auth.recovery.request", "recovery_confirm": "auth.recovery.confirm",
        "csrf": "security.csrf_denied",
    }
    append_audit_event(db, actions.get(action, action), "success" if outcome == "accepted" else outcome, actor, tenant, resource, metadata or {})


def _recovery_resource(email: str) -> str:
    return _recovery_codec().digest(email.lower())


def _session(db: Session, raw: str | None) -> dict:
    if not raw:
        raise HTTPException(status_code=401, detail="Se requiere autenticación.")
    digest = _codec().digest(raw)
    row = db.execute(
        text("SELECT * FROM public.resolve_runtime_session(:proof)"), {"proof": digest}
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=401, detail="Se requiere autenticación.")
    state = dict(row)
    state["session_digest"] = digest
    return state


def _csrf(db: Session, state: dict, request: Request, header: str | None, cookie: str | None) -> None:
    origin = request.headers.get("origin")
    csrf_digest = _codec().digest(header or "")
    valid = bool(db.execute(
        text("SELECT public.session_csrf_is_valid(:proof,:csrf,:scope)"),
        {"proof": state["session_digest"], "csrf": csrf_digest, "scope": state["account_scope"]},
    ).scalar_one())
    if origin not in settings.backend_cors_origins or not header or header != cookie or not valid:
        if state.get("account_scope") == 'platform':
            db.execute(text("SELECT public.append_platform_denial()"))
        else:
            if state.get("tenant_id"):
                # pi-lens-ignore: python-sql-injection
                db.execute(text("SELECT set_config('app.user_id', :user, true), set_config('app.tenant_id', :tenant, true)"), {"user": str(state["user_id"]), "tenant": str(state["tenant_id"])})
            _audit(db, "csrf", "denied", state["user_id"], state.get("tenant_id"))
        db.commit()
        raise HTTPException(status_code=403, detail="Falló la validación de seguridad de la solicitud.")


def _set_tenant_context(db: Session, state: dict, tenant: UUID) -> None:
    """Set the complete proof-bound context for one transaction."""
    db.execute(
        text("SELECT set_config('app.session_proof', :proof, true), set_config('app.account_scope', 'tenant', true), set_config('app.user_id', :user, true), set_config('app.tenant_id', :tenant, true)"),
        {"proof": state["session_digest"], "user": str(state["user_id"]), "tenant": str(tenant)},
    )


def _tenant_context(db: Session, state: dict, allowed: set[str]) -> UUID:
    if state.get("account_scope") != 'tenant':
        raise HTTPException(status_code=403, detail="No tenés permiso para realizar esta acción.")
    tenant = state.get("tenant_id")
    if not tenant:
        raise HTTPException(status_code=409, detail="Primero seleccioná un espacio de trabajo.")
    with db.begin():
        _set_tenant_context(db, state, tenant)
        role = db.execute(text("SELECT r.name FROM membership_roles mr JOIN roles r ON r.id=mr.role_id WHERE mr.user_id=:user AND mr.tenant_id=:tenant"), {"user": state["user_id"], "tenant": tenant}).scalar_one_or_none()
    if role not in allowed:
        raise HTTPException(status_code=403, detail="Tu rol no tiene permiso para realizar esta acción.")
    return tenant


def _issue_session(response: Response, user_id: UUID, credential_version: int, issuer) -> None:
    """Mint cookies only after the isolated database issuer commits."""
    token, csrf = _codec().issue(), _codec().issue()
    issuer(user_id, credential_version, _codec().digest(token), _codec().digest(csrf))
    response.set_cookie(_SESSION_COOKIE, token, httponly=True, samesite="lax", secure=settings.app_env == "production", max_age=settings.session_ttl_minutes * 60)
    response.set_cookie(_CSRF_COOKIE, csrf, httponly=False, samesite="lax", secure=settings.app_env == "production", max_age=settings.session_ttl_minutes * 60)


def _mint_tenant_session(response: Response, user_id: UUID, credential_version: int) -> None:
    from app.security.session_issuer import SessionIssueUnavailable, issue_tenant_session

    try:
        _issue_session(response, user_id, credential_version, issue_tenant_session)
    except SessionIssueUnavailable as exc:
        raise HTTPException(status_code=503, detail="No se pudo iniciar la sesión.") from exc


@router.post("/auth/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterPayload, response: Response) -> dict:
    from app.security.session_issuer import SessionIssueUnavailable, register_tenant_bootstrap

    user_id, tenant_id = uuid4(), uuid4()
    role_ids = {name: uuid4() for name in _ROLES}
    try:
        register_tenant_bootstrap(
            user_id, tenant_id, role_ids, payload.email.lower(), hash_password(payload.password), payload.tenant_name.strip(),
        )
    except SessionIssueUnavailable as exc:
        raise HTTPException(status_code=409, detail="El correo electrónico ya está registrado.") from exc
    _mint_tenant_session(response, user_id, 1)
    return {"user_id": str(user_id), "tenant_id": str(tenant_id), "role": "admin"}


@router.post("/auth/login")
def login(payload: LoginPayload, response: Response, db: Session = Depends(db_session)) -> dict:
    user = db.execute(text("SELECT id,password_hash,credential_version FROM users WHERE email=:email"), {"email": payload.email.lower()}).mappings().first()
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="El correo electrónico o la contraseña no son válidos.")
    db.commit()
    with db.begin():
        db.execute(text("SELECT set_config('app.user_id', :value, true)"), {"value": str(user["id"])})
        tenant_id = db.execute(text("SELECT sole_active_membership_tenant(:user)"), {"user": user["id"]}).scalar_one()
        if not tenant_id: raise HTTPException(status_code=403, detail="Se requiere una membresía activa en un espacio de trabajo.")
        db.execute(text("SELECT set_config('app.tenant_id', :value, true)"), {"value": str(tenant_id)})
        _audit(db, "login", "success", user["id"], tenant_id)
    # pi-lens-ignore: unchecked-throwing-call-python
    _mint_tenant_session(response, user["id"], int(user.get("credential_version", 1)))
    return {"authenticated": True}


@router.get("/auth/session")
def session_status(session_token: Annotated[str | None, Cookie()] = None, db: Session = Depends(db_session)) -> dict:
    state = _session(db, session_token)
    db.commit()
    tenant_id = state.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=409, detail="Se requiere una membresía activa en un espacio de trabajo.")
    with db.begin():
        _set_tenant_context(db, state, tenant_id)
        role = db.execute(text("SELECT r.name FROM membership_roles mr JOIN roles r ON r.id=mr.role_id WHERE mr.user_id=:user AND mr.tenant_id=:tenant"), {"user": state["user_id"], "tenant": tenant_id}).scalar_one_or_none()
        capabilities = list(db.execute(text("SELECT rp.permission_code FROM membership_roles mr JOIN role_permissions rp ON rp.tenant_id=mr.tenant_id AND rp.role_id=mr.role_id WHERE mr.user_id=:user AND mr.tenant_id=:tenant ORDER BY rp.permission_code LIMIT 20"), {"user": state["user_id"], "tenant": tenant_id}).scalars())
        tenant_name = db.execute(text("SELECT name FROM tenants WHERE id=:tenant"), {"tenant": tenant_id}).scalar_one()
    if not role:
        raise HTTPException(status_code=403, detail="Se requiere una membresía activa en un espacio de trabajo.")
    return {"user_id": str(state["user_id"]), "tenant_id": str(tenant_id), "tenant_name": tenant_name, "role": role, "capabilities": capabilities}


@router.post("/auth/logout")
def logout(request: Request, response: Response, session_token: Annotated[str | None, Cookie()] = None, csrf_token: Annotated[str | None, Cookie()] = None, x_csrf_token: Annotated[str | None, Header()] = None, db: Session = Depends(db_session)) -> dict:
    state = _session(db, session_token); _csrf(db, state, request, x_csrf_token, csrf_token)
    db.execute(text("SELECT public.revoke_own_session(:token,:csrf,:scope)"), {"token": state["session_digest"], "csrf": _codec().digest(x_csrf_token or ""), "scope": state["account_scope"]})
    db.execute(text("SELECT set_config('app.user_id', :user, true), set_config('app.tenant_id', :tenant, true)"), {"user": str(state["user_id"]), "tenant": str(state["tenant_id"])})
    _audit(db, "logout", "success", state["user_id"], state.get("tenant_id"))
    db.commit()
    response.delete_cookie(_SESSION_COOKIE); response.delete_cookie(_CSRF_COOKIE)
    return {"logged_out": True}


@router.post("/auth/recovery/request", status_code=status.HTTP_202_ACCEPTED)
def recovery_request(payload: RecoveryRequest, db: Session = Depends(db_session)) -> dict:
    resource = _recovery_resource(payload.email)
    token: str | None = None
    count = db.execute(text("SELECT recovery_request_count(:resource)"), {"resource": resource}).scalar_one()
    user = db.execute(text("SELECT id,email FROM users WHERE email=:email"), {"email": payload.email.lower()}).mappings().first() if count < settings.recovery_requests_per_hour else None
    _audit(db, "recovery_request", "accepted" if count < settings.recovery_requests_per_hour else "rate_limited", resource=resource)
    if user:
        token = _recovery_codec().issue()
        db.execute(text("INSERT INTO recovery_tokens (id,user_id,token_hash,expires_at) VALUES (:id,:user,:hash,:expires)"), {"id": uuid4(), "user": user["id"], "hash": _recovery_codec().digest(token), "expires": _now() + timedelta(minutes=settings.recovery_token_ttl_minutes)})
    db.commit()
    if user and token:
        try:
            send_recovery(user["email"], token)
        except OSError as exc:
            logger.warning("Recovery email delivery failed", extra={"error_type": type(exc).__name__})
    return {"message": "Si la cuenta existe, se enviaron las instrucciones de recuperación."}


@router.post("/auth/recovery/confirm")
def recovery_confirm(payload: RecoveryConfirm, db: Session = Depends(db_session)) -> dict:
    with db.begin():
        row = db.execute(text("UPDATE recovery_tokens SET used_at=now() WHERE token_hash=:hash AND used_at IS NULL AND expires_at > now() RETURNING user_id"), {"hash": _recovery_codec().digest(payload.token)}).mappings().first()
        if not row:
            raise HTTPException(status_code=400, detail="El código de recuperación no es válido o venció.")
        db.execute(text("UPDATE users SET password_hash=:password,password_setup_required=false WHERE id=:id"), {"password": hash_password(payload.password), "id": row["user_id"]})
        db.execute(text("SELECT public.revoke_recovery_sessions(:proof)"), {"proof": _recovery_codec().digest(payload.token)})
        tenant_id = db.execute(text("SELECT sole_active_membership_tenant(:user)"), {"user": row["user_id"]}).scalar_one()
        if tenant_id:
            db.execute(text("SELECT set_config('app.user_id', :user, true), set_config('app.tenant_id', :tenant, true)"), {"user": str(row["user_id"]), "tenant": str(tenant_id)})
            _audit(db, "recovery_confirm", "success", row["user_id"], tenant_id)
    return {"password_updated": True}


@router.get("/members")
def list_members(
    params: Annotated[MemberListParams, Query()],
    session_token: Annotated[str | None, Cookie()] = None,
    db: Session = Depends(db_session),
) -> dict:
    """Return the current admin's tenant directory without a client tenant selector."""

    state = _session(db, session_token)
    db.commit()
    tenant = _tenant_context(db, state, {"admin"})
    list_sql, values = _member_list_sql(params)
    count_sql, count_values = _member_list_count_sql(params)
    values["tenant"] = tenant
    count_values["tenant"] = tenant
    with db.begin():
        _set_tenant_context(db, state, tenant)
        total = db.execute(text(count_sql), count_values).scalar_one()
        rows = db.execute(text(list_sql), values).mappings().all()
    return {
        "items": [
            {
                "user_id": str(row["user_id"]),
                "email": row["email"],
                "role": row["role"],
                "status": "active" if row["active"] else "inactive",
                "password_setup_required": row["password_setup_required"],
            }
            for row in rows
        ],
        "total": total,
        "page": params.page,
        "per_page": params.per_page,
        "pages": (total + params.per_page - 1) // params.per_page,
    }


@router.post("/members", status_code=status.HTTP_201_CREATED)
def create_or_attach_member(payload: MemberCreate, request: Request, session_token: Annotated[str | None, Cookie()] = None, csrf_token: Annotated[str | None, Cookie()] = None, x_csrf_token: Annotated[str | None, Header()] = None, db: Session = Depends(db_session)) -> dict:
    if payload.role not in _ROLES:
        raise HTTPException(status_code=422, detail="El rol debe ser administración, integrante o consulta.")
    state = _session(db, session_token); _csrf(db, state, request, x_csrf_token, csrf_token); db.commit(); tenant = _tenant_context(db, state, {"admin"})
    with db.begin():
        _set_tenant_context(db, state, tenant)
        user = db.execute(text("SELECT id FROM users WHERE email=:email"), {"email": payload.email.lower()}).mappings().first()
        if not user:
            user = {"id": uuid4()}; db.execute(text("INSERT INTO users (id,email,password_hash,password_setup_required) VALUES (:id,:email,:password,true)"), {"id": user["id"], "email": payload.email.lower(), "password": hash_password(token_urlsafe(32))})

        role_id = None
        if user:
            db.execute(text("SELECT set_config('app.user_id', :value, true)"), {"value": str(user["id"])})
            existing_tenant = db.execute(text("SELECT sole_active_membership_tenant(:user)"), {"user": user["id"]}).scalar_one()
            db.execute(text("SELECT set_config('app.user_id', :value, true)"), {"value": str(state["user_id"])})
            if existing_tenant and existing_tenant != tenant:
                raise HTTPException(status_code=409, detail="La persona ya pertenece a otro espacio de trabajo.")
            role_id = db.execute(text("SELECT id FROM roles WHERE tenant_id=:tenant AND name=:role"), {"tenant": tenant, "role": payload.role}).scalar_one_or_none()
        if not role_id:
            role_id = uuid4(); db.execute(text("INSERT INTO roles (id,tenant_id,name) VALUES (:id,:tenant,:role)"), {"id": role_id, "tenant": tenant, "role": payload.role})
        db.execute(text("INSERT INTO memberships (tenant_id,user_id) VALUES (:tenant,:user) ON CONFLICT DO NOTHING"), {"tenant": tenant, "user": user["id"]})
        db.execute(text("INSERT INTO membership_roles (tenant_id,user_id,role_id) VALUES (:tenant,:user,:role) ON CONFLICT (tenant_id,user_id) DO UPDATE SET role_id=EXCLUDED.role_id"), {"tenant": tenant, "user": user["id"], "role": role_id})
        _audit(
            db, "membership.created", "success", state["user_id"], tenant,
            f"membership:{user['id']}", {"role": payload.role, "active": True},
        )
        return {"user_id": str(user["id"]), "role": payload.role}


@router.patch("/members/{membership_id}")
def update_member(
    membership_id: UUID,
    payload: MemberUpdate,
    request: Request,
    session_token: Annotated[str | None, Cookie()] = None,
    csrf_token: Annotated[str | None, Cookie()] = None,
    x_csrf_token: Annotated[str | None, Header()] = None,
    db: Session = Depends(db_session),
) -> dict:
    """Change a member role or active state without allowing cross-tenant access."""

    if not payload.model_fields_set:
        raise HTTPException(status_code=422, detail="Se requiere al menos un cambio de membresía.")
    state = _session(db, session_token)
    _csrf(db, state, request, x_csrf_token, csrf_token)
    db.commit()
    tenant = _tenant_context(db, state, {"admin"})

    with db.begin():
        _set_tenant_context(db, state, tenant)
        # Serialize admin-count transitions per tenant. The migration trigger uses the
        # same transaction-scoped lock to protect concurrent writers outside this route.
        db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(CAST(:tenant AS text), 0))"), {"tenant": str(tenant)})
        current = db.execute(
            text("""
                SELECT m.user_id, m.active, r.name AS role
                FROM memberships m
                JOIN membership_roles mr ON mr.tenant_id = m.tenant_id AND mr.user_id = m.user_id
                JOIN roles r ON r.id = mr.role_id AND r.tenant_id = m.tenant_id
                WHERE m.tenant_id = :tenant AND m.user_id = :user
                FOR UPDATE OF m
            """),
            {"tenant": tenant, "user": membership_id},
        ).mappings().first()
        if not current:
            raise HTTPException(status_code=404, detail="No se encontró la membresía.")

        next_role = payload.role if payload.role is not None else current["role"]
        next_active = payload.active if payload.active is not None else current["active"]
        if next_role == current["role"] and next_active == current["active"]:
            raise HTTPException(status_code=409, detail="La membresía ya tiene esos valores.")
        if state["user_id"] == membership_id and current["active"] and not next_active:
            raise HTTPException(status_code=409, detail="No podés desactivar tu propia membresía.")
        removes_last_admin = current["active"] and current["role"] == "admin" and (not next_active or next_role != "admin")
        if removes_last_admin:
            active_admins = db.execute(
                text("""
                    SELECT count(*)
                    FROM memberships m
                    JOIN membership_roles mr ON mr.tenant_id = m.tenant_id AND mr.user_id = m.user_id
                    JOIN roles r ON r.id = mr.role_id AND r.tenant_id = m.tenant_id
                    WHERE m.tenant_id = :tenant AND m.active AND r.name = 'admin'
                """),
                {"tenant": tenant},
            ).scalar_one()
            if active_admins <= 1:
                raise HTTPException(status_code=409, detail="El espacio de trabajo debe conservar una persona administradora activa.")

        if payload.role is not None and payload.role != current["role"]:
            role_id = db.execute(text("SELECT id FROM roles WHERE tenant_id=:tenant AND name=:role"), {"tenant": tenant, "role": payload.role}).scalar_one()
            db.execute(text("UPDATE membership_roles SET role_id=:role WHERE tenant_id=:tenant AND user_id=:user"), {"role": role_id, "tenant": tenant, "user": membership_id})
        if payload.active is not None and payload.active != current["active"]:
            db.execute(text("UPDATE memberships SET active=:active WHERE tenant_id=:tenant AND user_id=:user"), {"active": payload.active, "tenant": tenant, "user": membership_id})
        resource = f"membership:{membership_id}"
        if payload.role is not None and payload.role != current["role"]:
            _audit(
                db, "membership.role_changed", "success", state["user_id"], tenant, resource,
                {"previous_role": current["role"], "role": next_role},
            )
        if payload.active is not None and payload.active != current["active"]:
            _audit(
                db, "membership.activation_changed", "success", state["user_id"], tenant, resource,
                {"previous_active": current["active"], "active": next_active},
            )
    return {"membership_id": str(membership_id), "user_id": str(membership_id), "role": next_role, "active": next_active}
