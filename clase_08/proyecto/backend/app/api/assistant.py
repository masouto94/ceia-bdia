"""Authenticated HTTP boundary for tenant-safe assistant queries."""

# pyright: reportMissingImports=false

from typing import Annotated, Literal

from fastapi import APIRouter, Cookie, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.auth import _session, _tenant_context, db_session
from app.assistant.service import AssistantService, AssistantUnavailable, DocumentRetriever, TrustedAssistantContext

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


class AssistantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1, max_length=1000)
    mode: Literal["document", "relational", "combined", "auto"] = "auto"


def _service(db: Session) -> AssistantService:
    return AssistantService(DocumentRetriever(db))


@router.post("/query")
def query_assistant(payload: AssistantRequest, session_token: Annotated[str | None, Cookie()] = None,
                    db: Session = Depends(db_session)) -> dict:
    state = _session(db, session_token)
    db.commit()
    tenant = _tenant_context(db, state, {"admin", "member", "viewer"})
    # Authorization above proves an allowed role; use the least-privileged effective role downstream.
    context = TrustedAssistantContext(state["user_id"], tenant, "viewer", state["session_digest"])
    try:
        return _service(db).answer(payload.prompt, payload.mode, context)
    except PermissionError as exc:
        raise HTTPException(403, "Tu rol no tiene permiso para realizar esta acción.") from exc
    except AssistantUnavailable as exc:
        raise HTTPException(503, "El asistente no está disponible para esta consulta.") from exc
