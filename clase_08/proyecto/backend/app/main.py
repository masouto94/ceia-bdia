"""FastAPI application boundary for the generic student project."""

# pyright: reportMissingImports=false

from contextlib import asynccontextmanager
import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from app.api.assistant import router as assistant_router
from app.api.auth import router as identity_router
from app.api.experiments import router as experiments_router
from app.api.dashboard import router as dashboard_router
from app.api.audit import router as audit_router
from app.api.platform import router as platform_router
from app.documents import router as documents_router
from app.core.config import settings

logger = logging.getLogger(__name__)

_KNOWN_DETAILS = {
    "Se requiere autenticación.",
    "Falló la validación de seguridad de la solicitud.",
    "Primero seleccioná un espacio de trabajo.",
    "Tu rol no tiene permiso para realizar esta acción.",
    "El correo electrónico ya está registrado.",
    "El correo electrónico o la contraseña no son válidos.",
    "Se requiere una membresía activa en un espacio de trabajo.",
    "El código de recuperación no es válido o venció.",
    "El rol debe ser administración, integrante o consulta.",
    "La persona ya pertenece a otro espacio de trabajo.",
    "Los datos de paginación no son válidos.",
    "No se encontró el experimento.",
    "La transición de estado no es válida.",
    "El experimento debe estar en ejecución.",
    "Document not found.",
    "Only PDF, TXT, and MD uploads are accepted.",
    "The upload is empty or exceeds the configured limit.",
    "The PDF signature is invalid.",
    "The text encoding is invalid.",
    "Private object storage is unavailable.",
    "Stored object integrity verification failed.",
    "Document ingestion failed closed.",
    "Embedding provider is unavailable.",
    "El asistente no está disponible para esta consulta.",
    "Invalid platform credentials.",
    "Platform authentication required.",
    "Platform access denied.",
}
_STATUS_DETAILS = {
    400: "La solicitud no es válida.",
    401: "Se requiere autenticación.",
    403: "No tenés permiso para realizar esta acción.",
    404: "No se encontró el recurso solicitado.",
    405: "Método no permitido.",
    409: "No se pudo completar la solicitud por un conflicto.",
    422: "Los datos enviados no son válidos.",
    429: "Se realizaron demasiadas solicitudes. Intentá nuevamente más tarde.",
}
_INTERNAL_ERROR = "Ocurrió un error interno. Intentá nuevamente más tarde."


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Reserve startup/shutdown ownership for target-owned services."""
    yield


def _validation_message(error: dict[str, Any]) -> str:
    location = error.get("loc", ())
    field = location[-1] if isinstance(location, (list, tuple)) and location else ""
    error_type = str(error.get("type", ""))
    if error_type == "missing":
        return "Este campo es obligatorio."
    if field == "email":
        return "Ingresá un correo electrónico válido."
    if field == "password" or error_type == "string_too_short":
        return "La contraseña debe tener al menos 8 caracteres."
    return "Los datos enviados no son válidos."


def _status_detail(status_code: int) -> str:
    if status_code >= 500:
        return _INTERNAL_ERROR
    return _STATUS_DETAILS.get(status_code, "No se pudo completar la solicitud.")


app = FastAPI(
    title=settings.project_name,
    lifespan=lifespan,
    # pi-lens-ignore: generic-api-key
    openapi_url=None if settings.app_env == "production" else "/api/openapi.json",  # gitleaks:allow -- public route, not a credential
    docs_url=None if settings.app_env == "production" else "/api/docs",
    redoc_url=None,
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.backend_trusted_hosts)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Accept", "Content-Type", "X-CSRF-Token"],
)
app.include_router(identity_router)
app.include_router(platform_router)
app.include_router(experiments_router)
app.include_router(dashboard_router)
app.include_router(audit_router)
app.include_router(documents_router)
app.include_router(assistant_router)


@app.exception_handler(RequestValidationError)
async def request_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    detail = [
        {"loc": list(error.get("loc", ())), "type": str(error.get("type", "value_error")), "msg": _validation_message(error)}
        for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": detail})


@app.exception_handler(StarletteHTTPException)
async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, str) and exc.detail in _KNOWN_DETAILS else _status_detail(exc.status_code)
    return JSONResponse(status_code=exc.status_code, content={"detail": detail}, headers=exc.headers)


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled request error for %s", request.url.path, exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": _INTERNAL_ERROR})


@app.get("/health", tags=["operations"])
def health_check() -> dict[str, str]:
    """Return the Compose health contract without depending on future services."""
    return {"status": "ok", "service": "project-api"}
