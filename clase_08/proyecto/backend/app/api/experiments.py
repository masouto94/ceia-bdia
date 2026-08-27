"""Tenant-owned experiment, result, and metric routes."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.auth import _csrf, _session, _tenant_context, db_session
from app.api.experiment_schemas import ExperimentCreate, ExperimentUpdate, ResultCreate
from app.repositories.experiments import ExperimentRepository
from app.services.experiments import ExperimentService
from app.services.pagination import PageRequest

router = APIRouter(prefix="/api/experiments", tags=["experiments"])

ExperimentStatusFilter = Literal["draft", "running", "completed", "failed"]
ExperimentSort = Literal[
    "created_at:desc",
    "created_at:asc",
    "name:asc",
    "name:desc",
    "result_count:desc",
]


class ExperimentListQuery(BaseModel):
    page: int = 1
    per_page: int = 20
    search: str = Field(default="", max_length=120)
    status: ExperimentStatusFilter | None = None
    archived: bool = False
    sort: ExperimentSort = "created_at:desc"

    @field_validator("search")
    @classmethod
    def strip_search(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_pagination(self) -> "ExperimentListQuery":
        PageRequest(self.page, self.per_page)
        return self


def _trusted(db: Session, state: dict, roles: set[str]) -> UUID:
    db.commit()
    return _tenant_context(db, state, roles)


def _set_context(db: Session, state: dict, tenant: UUID) -> None:
    # pi-lens-ignore: python-sql-injection
    db.execute(text("SELECT set_config('app.session_proof', :proof, true), set_config('app.account_scope', 'tenant', true), set_config('app.user_id', :user, true), set_config('app.tenant_id', :tenant, true)"), {"proof": state["session_digest"], "user": str(state["user_id"]), "tenant": str(tenant)})


def _mutation(request: Request, db: Session, state: dict, csrf_header: str | None, csrf_cookie: str | None) -> UUID:
    _csrf(db, state, request, csrf_header, csrf_cookie)
    return _trusted(db, state, {"admin", "member"})


@router.get("")
def list_experiments(
    page: int = Query(1),
    per_page: int = Query(20),
    search: str = Query(default="", max_length=120),
    status: ExperimentStatusFilter | None = Query(default=None),
    archived: bool = Query(default=False),
    sort: ExperimentSort = Query(default="created_at:desc"),
    session_token: Annotated[str | None, Cookie()] = None,
    db: Session = Depends(db_session),
) -> dict:
    try:
        query = ExperimentListQuery(
            page=page,
            per_page=per_page,
            search=search,
            status=status,
            archived=archived,
            sort=sort,
        )
    except ValueError as exc:
        raise HTTPException(422, "Los datos de consulta no son válidos.") from exc
    state = _session(db, session_token)
    tenant = _trusted(db, state, {"admin", "member", "viewer"})
    with db.begin():
        _set_context(db, state, tenant)
        result = ExperimentRepository(db).list(tenant, query)
    return {"items": result.items, "total": result.total, "page": result.page, "per_page": result.per_page, "pages": result.pages}


@router.get("/{experiment_id}")
def get_experiment(experiment_id: UUID, session_token: Annotated[str | None, Cookie()] = None, db: Session = Depends(db_session)) -> dict:
    state = _session(db, session_token); tenant = _trusted(db, state, {"admin", "member", "viewer"})
    with db.begin():
        _set_context(db, state, tenant); item = ExperimentRepository(db).get(tenant, experiment_id)
    if not item: raise HTTPException(404, "No se encontró el experimento.")
    return item


@router.post("", status_code=status.HTTP_201_CREATED)
def create_experiment(payload: ExperimentCreate, request: Request, session_token: Annotated[str | None, Cookie()] = None, csrf_token: Annotated[str | None, Cookie()] = None, x_csrf_token: Annotated[str | None, Header()] = None, db: Session = Depends(db_session)) -> dict:
    state = _session(db, session_token); tenant = _mutation(request, db, state, x_csrf_token, csrf_token)
    with db.begin():
        _set_context(db, state, tenant); return ExperimentService(ExperimentRepository(db)).create(tenant, state["user_id"], payload)


@router.patch("/{experiment_id}")
def update_experiment(experiment_id: UUID, payload: ExperimentUpdate, request: Request, session_token: Annotated[str | None, Cookie()] = None, csrf_token: Annotated[str | None, Cookie()] = None, x_csrf_token: Annotated[str | None, Header()] = None, db: Session = Depends(db_session)) -> dict:
    state = _session(db, session_token); tenant = _mutation(request, db, state, x_csrf_token, csrf_token)
    try:
        with db.begin():
            _set_context(db, state, tenant); item = ExperimentService(ExperimentRepository(db)).update(tenant, state["user_id"], experiment_id, payload)
    except ValueError as exc:
        raise HTTPException(409, "La transición de estado no es válida.") from exc
    if not item: raise HTTPException(404, "No se encontró el experimento.")
    return item


@router.post("/{experiment_id}/results", status_code=status.HTTP_201_CREATED)
def append_result(experiment_id: UUID, payload: ResultCreate, request: Request, session_token: Annotated[str | None, Cookie()] = None, csrf_token: Annotated[str | None, Cookie()] = None, x_csrf_token: Annotated[str | None, Header()] = None, db: Session = Depends(db_session)) -> dict:
    state = _session(db, session_token); tenant = _mutation(request, db, state, x_csrf_token, csrf_token)
    try:
        with db.begin():
            _set_context(db, state, tenant); item = ExperimentService(ExperimentRepository(db)).append_result(tenant, state["user_id"], experiment_id, payload)
    except ValueError as exc:
        raise HTTPException(409, "El experimento debe estar en ejecución.") from exc
    if not item: raise HTTPException(404, "No se encontró el experimento.")
    return item
