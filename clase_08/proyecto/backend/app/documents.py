"""Private document storage, bounded ingestion, and tenant-safe vector retrieval."""

# pyright: reportMissingImports=false

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import json
import logging
import math
from typing import Annotated, Callable, Literal
from urllib.error import HTTPError, URLError
from urllib.request import Request as URLRequest, urlopen
from uuid import UUID, uuid4

from fastapi import APIRouter, Cookie, Depends, File, Header, HTTPException, Query, Request, Response, UploadFile
from minio import Minio
from pydantic import BaseModel, Field, field_validator
from pypdf import PdfReader
from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Integer, String, bindparam, column, select, table, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.auth import _csrf, _session, _tenant_context, db_session
from app.core.config import settings
from app.audit import append_audit_event

router = APIRouter(prefix="/api/documents", tags=["documents"])
logger = logging.getLogger(__name__)
_ALLOWED = {".pdf": "application/pdf", ".txt": "text/plain", ".md": "text/markdown"}

_documents = table(
    "documents", column("id"), column("tenant_id"), column("name", String), column("ingestion_status", String)
)
_chunks = table(
    "chunks", column("id"), column("tenant_id"), column("document_id"), column("content", String),
    column("ordinal", Integer), column("active", Boolean)
)
_embeddings = table(
    "embeddings", column("tenant_id"), column("chunk_id"),
    column("embedding", Vector(settings.embedding_dimension))
)


DocumentStatus = Literal["pending", "processing", "ready", "failed"]
DocumentSort = Literal["name:asc", "name:desc", "status:asc", "status:desc"]


class DocumentListQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=10, ge=1, le=50)
    search: str | None = Field(default=None, max_length=200)
    status: DocumentStatus | None = None
    sort: DocumentSort = "name:asc"

    @field_validator("search", mode="before")
    @classmethod
    def trim_search(cls, value: object) -> object:
        return value.strip() or None if isinstance(value, str) else value


def _like_pattern(search: str | None) -> str | None:
    if search is None:
        return None
    return "%" + search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


_DOCUMENT_LIST_COUNT = text("""
    SELECT count(*) AS total
    FROM documents
    WHERE tenant_id = CAST(:tenant AS uuid)
      AND (CAST(:status AS varchar) IS NULL OR ingestion_status = CAST(:status AS varchar))
      AND (CAST(:search AS varchar) IS NULL OR name ILIKE CAST(:search AS varchar) ESCAPE '\\')
""")
_DOCUMENT_LIST_ITEMS = text("""
    SELECT id, name, content_type, size_bytes, ingestion_status
    FROM documents
    WHERE tenant_id = CAST(:tenant AS uuid)
      AND (CAST(:status AS varchar) IS NULL OR ingestion_status = CAST(:status AS varchar))
      AND (CAST(:search AS varchar) IS NULL OR name ILIKE CAST(:search AS varchar) ESCAPE '\\')
    ORDER BY
      CASE WHEN CAST(:sort AS varchar) = 'name:asc' THEN name END ASC,
      CASE WHEN CAST(:sort AS varchar) = 'name:desc' THEN name END DESC,
      CASE WHEN CAST(:sort AS varchar) = 'status:asc' THEN ingestion_status END ASC,
      CASE WHEN CAST(:sort AS varchar) = 'status:desc' THEN ingestion_status END DESC,
      id ASC
    LIMIT CAST(:limit AS integer) OFFSET CAST(:offset AS integer)
""")


def _document_list_statements(query: DocumentListQuery, tenant: UUID):
    filters = (
        bindparam("tenant", value=tenant),
        bindparam("status", value=query.status, type_=String()),
        bindparam("search", value=_like_pattern(query.search), type_=String()),
    )
    return (
        _DOCUMENT_LIST_COUNT.bindparams(*filters),
        _DOCUMENT_LIST_ITEMS.bindparams(
            *filters,
            bindparam("sort", value=query.sort, type_=String()),
            bindparam("limit", value=query.per_page, type_=Integer()),
            bindparam("offset", value=(query.page - 1) * query.per_page, type_=Integer()),
        ),
    )


_DOCUMENT_DETAIL = text("""
    SELECT id, name, content_type, size_bytes, ingestion_status
    FROM documents
    WHERE id = CAST(:document AS uuid) AND tenant_id = CAST(:tenant AS uuid)
""")
_DOCUMENT_ACTIVE_CHUNKS = text("""
    SELECT count(*) AS active_chunk_count
    FROM chunks
    WHERE tenant_id = CAST(:tenant AS uuid)
      AND document_id = CAST(:document AS uuid)
      AND active = true
""")
_DOCUMENT_LATEST_RUN = text("""
    SELECT status, chunk_count, created_at, error
    FROM ingestion_runs
    WHERE tenant_id = CAST(:tenant AS uuid) AND document_id = CAST(:document AS uuid)
    ORDER BY created_at DESC, id DESC
    LIMIT 1
""")


def _document_detail_statements(document_id: UUID, tenant: UUID):
    parameters = (
        bindparam("document", value=document_id),
        bindparam("tenant", value=tenant),
    )
    return tuple(statement.bindparams(*parameters) for statement in (
        _DOCUMENT_DETAIL, _DOCUMENT_ACTIVE_CHUNKS, _DOCUMENT_LATEST_RUN,
    ))


def _retrieval_statement(vector: list[float], tenant: UUID, limit: int):
    query_vector = bindparam("vector", value=vector, type_=Vector(settings.embedding_dimension))
    distance = _embeddings.c.embedding.cosine_distance(query_vector).label("distance")
    return (
        select(
            _chunks.c.id, _chunks.c.document_id, _chunks.c.content, _chunks.c.ordinal,
            _documents.c.name, distance,
        )
        .select_from(
            _embeddings.join(
                _chunks,
                (_chunks.c.id == _embeddings.c.chunk_id)
                & (_chunks.c.tenant_id == _embeddings.c.tenant_id),
            ).join(
                _documents,
                (_documents.c.id == _chunks.c.document_id)
                & (_documents.c.tenant_id == _chunks.c.tenant_id),
            )
        )
        .where(
            _embeddings.c.tenant_id == tenant,
            _chunks.c.tenant_id == tenant,
            _documents.c.tenant_id == tenant,
            _chunks.c.active.is_(True),
            _documents.c.ingestion_status == "ready",
        )
        .order_by(distance)
        .limit(limit)
    )


@dataclass(frozen=True)
class AuthorizedAsset:
    """Capability produced only after database authorization."""
    object_key: str
    tenant_id: str


class MinioObjectStore:
    def __init__(self, client: Minio, bucket: str): self.client, self.bucket = client, bucket

    @staticmethod
    def _key(asset: AuthorizedAsset) -> str:
        if not isinstance(asset, AuthorizedAsset): raise TypeError("authorized asset required")
        return asset.object_key

    def put(self, asset: AuthorizedAsset, data: bytes, content_type: str) -> None:
        self.client.put_object(self.bucket, self._key(asset), BytesIO(data), len(data), content_type=content_type)

    def get(self, asset: AuthorizedAsset) -> bytes:
        response = self.client.get_object(self.bucket, self._key(asset))
        try: return response.read()
        finally:
            response.close()
            if hasattr(response, "release_conn"): response.release_conn()


def _store() -> MinioObjectStore:
    client = Minio(settings.minio_endpoint, settings.minio_access_key, settings.minio_secret_key, secure=False)
    return MinioObjectStore(client, settings.minio_bucket)


class FixedEmbeddingProvider:
    """Deterministic normalized fixture provider; no request context crosses this seam."""
    def __init__(self, dimension: int, adapter: Callable[[str], list[float]] | None = None):
        self.dimension, self.adapter = dimension, adapter or self._local

    def _local(self, value: str) -> list[float]:
        raw = [(sha256(f"{index}:{value}".encode()).digest()[0] / 127.5) - 1.0 for index in range(self.dimension)]
        norm = sum(item * item for item in raw) ** 0.5
        return [item / norm for item in raw]

    def embed(self, value: str, intent: Literal["query", "passage"] = "query") -> list[float]:
        try: vector = self.adapter(value)
        except Exception as exc: raise RuntimeError("embedding provider unavailable") from exc
        if len(vector) != self.dimension or any(isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item) for item in vector):
            raise RuntimeError("embedding provider returned a malformed vector")
        # pi-lens-ignore: unchecked-throwing-call-python
        return [float(item) for item in vector]


class HTTPEmbeddingProvider:
    def __init__(self, url: str, dimension: int, model: str):
        self.url, self.dimension, self.model = url.rstrip("/"), dimension, model

    def embed(self, value: str, intent: Literal["query", "passage"] = "query") -> list[float]:
        request = URLRequest(f"{self.url}/embed", json.dumps({"texto": value, "tipo": intent}).encode(), {"Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(request, timeout=60) as response:
                if response.status != 200: raise RuntimeError("embedding provider request failed")
                payload = json.load(response)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError("embedding provider request failed") from exc
        if not isinstance(payload, dict) or payload.get("modelo") != self.model or payload.get("dimension") != self.dimension:
            raise RuntimeError("embedding provider returned incompatible metadata")
        vector = payload.get("vector")
        if not isinstance(vector, list) or len(vector) != self.dimension or any(isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item) for item in vector):
            raise RuntimeError("embedding provider returned a malformed vector")
        # pi-lens-ignore: unchecked-throwing-call-python
        return [float(item) for item in vector]


embedding_provider = HTTPEmbeddingProvider(settings.embeddings_api_url, settings.embedding_dimension, settings.modelo_embedding)


def extract_text(data: bytes, content_type: str) -> str:
    if content_type in {"text/plain", "text/markdown"}:
        try: value = data.decode("utf-8")
        except UnicodeDecodeError as exc: raise ValueError("document is not valid UTF-8") from exc
    elif content_type == "application/pdf":
        try: value = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(data)).pages)
        except Exception as exc: raise ValueError("PDF extraction failed") from exc
    else: raise ValueError("unsupported ingestible content type")
    value = value.strip()
    if not value or len(value) > 1_000_000: raise ValueError("extracted text is empty or too large")
    return value


def chunk_text(value: str, size: int = 1000, overlap: int = 100) -> list[str]:
    if size < 1 or overlap < 0 or overlap >= size: raise ValueError("invalid chunk bounds")
    chunks, start = [], 0
    while start < len(value):
        chunks.append(value[start:start + size])
        start += size - overlap
    if len(chunks) > 1200: raise ValueError("too many chunks")
    return chunks


def _set_context(db: Session, state: dict, tenant: UUID) -> None:
    # pi-lens-ignore: python-sql-injection
    db.execute(text("SELECT set_config('app.session_proof', :proof, true), set_config('app.account_scope', 'tenant', true), set_config('app.user_id', :user, true), set_config('app.tenant_id', :tenant, true)"), {"proof": state["session_digest"], "user": str(state["user_id"]), "tenant": str(tenant)})


def _authorize(db: Session, raw_session: str | None, roles: set[str]) -> tuple[dict, UUID]:
    state = _session(db, raw_session); db.commit()
    return state, _tenant_context(db, state, roles)


@router.get("")
def list_documents(
    query: Annotated[DocumentListQuery, Query()],
    session_token: Annotated[str | None, Cookie()] = None,
    db: Session = Depends(db_session),
) -> dict:
    state, tenant = _authorize(db, session_token, {"admin", "member", "viewer"})
    count, items = _document_list_statements(query, tenant)
    try:
        with db.begin():
            _set_context(db, state, tenant)
            total = int(db.execute(count).scalar_one())
            rows = db.execute(items).mappings().all()
    except SQLAlchemyError as exc:
        logger.exception("Document list database query failed", extra={"tenant_id": str(tenant)})
        raise HTTPException(503, "Document list is unavailable.") from exc
    return {
        "items": [
            {
                "id": str(row["id"]),
                "name": row["name"],
                "content_type": row["content_type"],
                "size_bytes": row["size_bytes"],
                "ingestion_status": row["ingestion_status"],
            }
            for row in rows
        ],
        "total": total,
        "page": query.page,
        "per_page": query.per_page,
        "pages": math.ceil(total / query.per_page),
    }


@router.get("/{document_id}")
def get_document(
    document_id: UUID,
    session_token: Annotated[str | None, Cookie()] = None,
    db: Session = Depends(db_session),
) -> dict:
    state, tenant = _authorize(db, session_token, {"admin", "member", "viewer"})
    document, chunks, latest_run = _document_detail_statements(document_id, tenant)
    try:
        with db.begin():
            _set_context(db, state, tenant)
            # pi-lens-ignore: python-sql-injection
            row = db.execute(document).mappings().first()
            if not row:
                raise HTTPException(404, "Document not found.")
            # pi-lens-ignore: python-sql-injection
            active_chunk_count = int(db.execute(chunks).scalar_one())
            # pi-lens-ignore: python-sql-injection
            latest = db.execute(latest_run).mappings().first()
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        logger.exception("Document detail database query failed", extra={"tenant_id": str(tenant)})
        raise HTTPException(503, "Document detail is unavailable.") from exc
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "content_type": row["content_type"],
        "size_bytes": row["size_bytes"],
        "ingestion_status": row["ingestion_status"],
        "active_chunk_count": active_chunk_count,
        "latest_run": None if latest is None else {
            "status": latest["status"],
            "chunk_count": latest["chunk_count"],
            "created_at": latest["created_at"],
            "error": latest["error"],
        },
    }


@router.post("", status_code=201)
async def upload_document(request: Request, file: Annotated[UploadFile, File()], session_token: Annotated[str | None, Cookie()] = None,
                          csrf_token: Annotated[str | None, Cookie()] = None, x_csrf_token: Annotated[str | None, Header()] = None,
                          db: Session = Depends(db_session)) -> dict:
    state = _session(db, session_token); _csrf(db, state, request, x_csrf_token, csrf_token); db.commit()
    tenant = _tenant_context(db, state, {"admin", "member"})
    suffix = "." + (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
    expected = _ALLOWED.get(suffix)
    if not expected or file.content_type != expected: raise HTTPException(415, "Only PDF, TXT, and MD uploads are accepted.")
    data = await file.read(settings.max_upload_bytes + 1)
    if not data or len(data) > settings.max_upload_bytes: raise HTTPException(413, "The upload is empty or exceeds the configured limit.")
    if expected == "application/pdf" and not data.startswith(b"%PDF-"): raise HTTPException(422, "The PDF signature is invalid.")
    if expected != "application/pdf":
        try: data.decode("utf-8")
        except UnicodeDecodeError as exc: raise HTTPException(422, "The text encoding is invalid.") from exc
    document_id, opaque = uuid4(), uuid4().hex
    asset = AuthorizedAsset(f"{tenant.hex}/{opaque}", str(tenant))
    try:
        with db.begin():
            _set_context(db, state, tenant)
            # pi-lens-ignore: python-sql-injection
            db.execute(text("INSERT INTO documents (id,tenant_id,created_by,name,object_key,content_type,size_bytes,sha256,ingestion_status) VALUES (:id,:tenant,:user,:name,:key,:type,:size,:digest,'pending')"),
{"id": document_id, "tenant": tenant, "user": state["user_id"], "name": file.filename, "key": asset.object_key, "type": expected, "size": len(data), "digest": sha256(data).hexdigest()})
            append_audit_event(db, "document.upload", "success", state["user_id"], tenant, f"document:{document_id}", {"content_type": expected, "size_bytes": len(data)})
            _store().put(asset, data, expected)
    except Exception as exc: raise HTTPException(503, "Private object storage is unavailable.") from exc
    return {"id": str(document_id), "name": file.filename, "content_type": expected, "size_bytes": len(data), "ingestion_status": "pending"}


@router.get("/{document_id}/download")
def download_document(document_id: UUID, session_token: Annotated[str | None, Cookie()] = None, db: Session = Depends(db_session)) -> Response:
    state, tenant = _authorize(db, session_token, {"admin", "member", "viewer"})
    with db.begin():
        _set_context(db, state, tenant)
        row = db.execute(text("SELECT object_key,content_type,name,sha256 FROM documents WHERE id=:id AND tenant_id=:tenant"), {"id": document_id, "tenant": tenant}).mappings().first()
    if not row: raise HTTPException(404, "Document not found.")
    try: data = _store().get(AuthorizedAsset(row["object_key"], str(tenant)))
    except Exception as exc: raise HTTPException(503, "Private object storage is unavailable.") from exc
    if sha256(data).hexdigest() != row["sha256"]: raise HTTPException(503, "Stored object integrity verification failed.")
    return Response(data, media_type=row["content_type"], headers={"Content-Disposition": f'attachment; filename="{row["name"]}"'})


@router.post("/{document_id}/ingest")
def ingest_document(document_id: UUID, request: Request, session_token: Annotated[str | None, Cookie()] = None,
                    csrf_token: Annotated[str | None, Cookie()] = None, x_csrf_token: Annotated[str | None, Header()] = None,
                    db: Session = Depends(db_session)) -> dict:
    state = _session(db, session_token); _csrf(db, state, request, x_csrf_token, csrf_token); db.commit()
    tenant = _tenant_context(db, state, {"admin", "member"})
    try:
        with db.begin():
            _set_context(db, state, tenant)
            row = db.execute(text("SELECT object_key,content_type,sha256,ingestion_status FROM documents WHERE id=:id AND tenant_id=:tenant FOR UPDATE"), {"id": document_id, "tenant": tenant}).mappings().first()
            if not row: raise HTTPException(404, "Document not found.")
            append_audit_event(db, "document.ingest.reprocessed" if row["ingestion_status"] == "ready" else "document.ingest.started", "success", state["user_id"], tenant, f"document:{document_id}", {})
            db.execute(text("UPDATE documents SET ingestion_status='processing' WHERE id=:id AND tenant_id=:tenant"), {"id": document_id, "tenant": tenant})
            data = _store().get(AuthorizedAsset(row["object_key"], str(tenant)))
            if sha256(data).hexdigest() != row["sha256"]: raise RuntimeError("stored object integrity mismatch")
            parts = chunk_text(extract_text(data, row["content_type"]))
            vectors = [embedding_provider.embed(part, "passage") for part in parts]
            db.execute(text("DELETE FROM chunks WHERE tenant_id=:tenant AND document_id=:document"), {"tenant": tenant, "document": document_id})
            for ordinal, (part, vector) in enumerate(zip(parts, vectors, strict=True)):
                chunk_id = uuid4()
                db.execute(text("INSERT INTO chunks (id,tenant_id,document_id,content,ordinal,active) VALUES (:id,:tenant,:document,:content,:ordinal,true)"), {"id": chunk_id, "tenant": tenant, "document": document_id, "content": part, "ordinal": ordinal})
                db.execute(text("INSERT INTO embeddings (id,tenant_id,chunk_id,embedding) VALUES (:id,:tenant,:chunk,CAST(:vector AS vector))"), {"id": uuid4(), "tenant": tenant, "chunk": chunk_id, "vector": str(vector)})
            db.execute(text("UPDATE documents SET ingestion_status='ready' WHERE id=:id AND tenant_id=:tenant"), {"id": document_id, "tenant": tenant})
            db.execute(text("INSERT INTO ingestion_runs (id,tenant_id,document_id,status,chunk_count) VALUES (:id,:tenant,:document,'ready',:count)"), {"id": uuid4(), "tenant": tenant, "document": document_id, "count": len(parts)})
    except HTTPException: raise
    except Exception as exc:
            logger.error(
                "Document ingestion failed (%s)",
                type(exc).__name__,
                extra={"document_id": str(document_id), "tenant_id": str(tenant)},
            )
            try:
                db.rollback()
                with db.begin():
                    _set_context(db, state, tenant)
                    db.execute(text("UPDATE documents SET ingestion_status='failed' WHERE id=:id AND tenant_id=:tenant"), {"id": document_id, "tenant": tenant})
                    db.execute(text("INSERT INTO ingestion_runs (id,tenant_id,document_id,status,error) VALUES (:id,:tenant,:document,'failed','Dependency or content failure')"), {"id": uuid4(), "tenant": tenant, "document": document_id})
            except Exception as cleanup_exc:
                try:
                    db.rollback()
                except Exception:
                    logger.exception(
                        "Failed to roll back after document ingestion cleanup failure",
                        extra={"document_id": str(document_id), "tenant_id": str(tenant)},
                    )
                logger.error(
                    "Failed to record document ingestion failure",
                    exc_info=cleanup_exc,
                    extra={"document_id": str(document_id), "tenant_id": str(tenant)},
                )
            raise HTTPException(503, "Document ingestion failed closed.") from exc

    return {"id": str(document_id), "ingestion_status": "ready", "chunk_count": len(parts)}


class RetrievalRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    limit: int = Field(default=5, ge=1, le=10)


@router.post("/retrieve")
def retrieve(payload: RetrievalRequest, session_token: Annotated[str | None, Cookie()] = None, db: Session = Depends(db_session)) -> dict:
    state, tenant = _authorize(db, session_token, {"admin", "member", "viewer"})
    try: vector = embedding_provider.embed(payload.query, "query")
    except RuntimeError as exc: raise HTTPException(503, "Embedding provider is unavailable.") from exc
    try:
        with db.begin():
            _set_context(db, state, tenant)
            rows = db.execute(_retrieval_statement(vector, tenant, payload.limit)).mappings().all()
    except SQLAlchemyError as exc:
        logger.exception("Document retrieval database query failed", extra={"tenant_id": str(tenant)})
        raise HTTPException(503, "Document retrieval is unavailable.") from exc
    try:
        citations = [
            {
                "chunk_id": str(row["id"]),
                "document_id": str(row["document_id"]),
                "document_name": row["name"],
                "ordinal": row["ordinal"],
                "content": row["content"],
                "distance": float(row["distance"]),
            }
            for row in rows
        ]
    except (TypeError, ValueError) as exc:
        logger.exception(
            "Document retrieval returned an invalid distance",
            extra={"tenant_id": str(tenant)},
        )
        raise HTTPException(503, "Document retrieval returned invalid data.") from exc
    return {"citations": citations}
