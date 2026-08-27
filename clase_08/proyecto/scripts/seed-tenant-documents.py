#!/usr/bin/env python3
"""Seed deterministic demo documents (shared class summaries + per-tenant training reports)
into the alpha/beta fixture tenants, with real embeddings from the embeddings-api service.

Idempotent and safe to re-run: chunks/embeddings for a given document are always replaced;
run after scripts/seed-security-fixtures.py, since it reuses the same tenant/user fixture IDs.
"""

from __future__ import annotations

import json
import os
import sys
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from urllib.request import Request as URLRequest, urlopen
from uuid import NAMESPACE_URL, UUID, uuid5

from minio import Minio  # pyright: ignore[reportMissingImports] -- provided by the API runtime
from sqlalchemy import create_engine, text  # pyright: ignore[reportMissingImports] -- provided by the API runtime

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "backend"))

from app.core.config import AdminToolSettings  # noqa: E402  # pyright: ignore[reportMissingImports] -- backend path inserted above

PREFIX = "https://example.test/gentle-ai/demo/"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "documents"
EMBEDDINGS_API_URL = os.environ.get("EMBEDDINGS_API_URL", "http://embeddings-api:8000")
EMBEDDING_MODEL = os.environ.get("MODELO_EMBEDDING", "intfloat/multilingual-e5-small")
EMBEDDING_DIMENSION = 384
TENANTS = ("alpha", "beta")


def fixture_id(value: str) -> UUID:
    return uuid5(NAMESPACE_URL, PREFIX + value)


def chunk_text(value: str, size: int = 1000, overlap: int = 100) -> list[str]:
    chunks, start = [], 0
    while start < len(value):
        piece = value[start:start + size]
        if piece.strip():
            chunks.append(piece)
        start += size - overlap
    return chunks


def embed(value: str, intent: str) -> list[float]:
    request = URLRequest(
        f"{EMBEDDINGS_API_URL.rstrip('/')}/embed",
        json.dumps({"texto": value, "tipo": intent}).encode(),
        {"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=60) as response:
        payload = json.load(response)
    vector = payload["vector"]
    if len(vector) != EMBEDDING_DIMENSION:
        raise SystemExit(f"Unexpected embedding dimension: {len(vector)}")
    return [float(item) for item in vector]


def documents_for_tenant(slug: str) -> list[Path]:
    shared = sorted((FIXTURES_DIR / "shared").glob("*.md"))
    own = sorted((FIXTURES_DIR / slug).glob("*.md"))
    return shared + own


def seed() -> None:
    admin_settings = AdminToolSettings()
    engine = create_engine(admin_settings.migrator_database_url)
    objects: list[tuple[str, bytes]] = []

    with engine.connect() as connection:
        for slug in TENANTS:
            tenant_id = fixture_id(f"tenant/{slug}")
            creator_id = fixture_id(f"tenant/{slug}/user/admin")

            with connection.begin():
                connection.execute(text("SET ROLE project_owner"))
                connection.execute(text("SELECT set_config('app.user_id', :value, true)"), {"value": str(creator_id)})
                connection.execute(text("SELECT set_config('app.tenant_id', :value, true)"), {"value": str(tenant_id)})

                for path in documents_for_tenant(slug):
                    data = path.read_bytes()
                    document_id = fixture_id(f"tenant/{slug}/document/{path.name}")
                    object_key = f"{tenant_id.hex}/{path.name}"
                    objects.append((object_key, data))

                    connection.execute(
                        text("""
                            INSERT INTO documents(id,tenant_id,created_by,name,object_key,ingestion_status,content_type,size_bytes,sha256)
                            VALUES (:id,:tenant,:user,:name,:key,'ready','text/markdown',:size,:digest)
                            ON CONFLICT (id) DO UPDATE SET
                                object_key = EXCLUDED.object_key,
                                ingestion_status = 'ready',
                                size_bytes = EXCLUDED.size_bytes,
                                sha256 = EXCLUDED.sha256
                        """),
                        {"id": document_id, "tenant": tenant_id, "user": creator_id, "name": path.name,
                         "key": object_key, "size": len(data), "digest": sha256(data).hexdigest()},
                    )
                    connection.execute(
                        text("""DELETE FROM embeddings USING chunks
                            WHERE embeddings.tenant_id = :tenant AND chunks.tenant_id = :tenant
                              AND chunks.document_id = :document AND embeddings.chunk_id = chunks.id"""),
                        {"tenant": tenant_id, "document": document_id},
                    )
                    connection.execute(
                        text("DELETE FROM chunks WHERE tenant_id = :tenant AND document_id = :document"),
                        {"tenant": tenant_id, "document": document_id},
                    )
                    parts = chunk_text(data.decode("utf-8"))
                    for ordinal, part in enumerate(parts):
                        chunk_id = fixture_id(f"tenant/{slug}/document/{path.name}/chunk/{ordinal}")
                        connection.execute(
                            text("""INSERT INTO chunks(id,tenant_id,document_id,content,ordinal,active)
                                VALUES (:id,:tenant,:document,:content,:ordinal,true)"""),
                            {"id": chunk_id, "tenant": tenant_id, "document": document_id, "content": part, "ordinal": ordinal},
                        )
                        vector = embed(part, "passage")
                        connection.execute(
                            text("""INSERT INTO embeddings(id,tenant_id,chunk_id,embedding)
                                VALUES (:id,:tenant,:chunk,CAST(:embedding AS vector))"""),
                            {"id": fixture_id(f"tenant/{slug}/document/{path.name}/embedding/{ordinal}"),
                             "tenant": tenant_id, "chunk": chunk_id, "embedding": str(vector)},
                        )
    client = Minio(os.environ["MINIO_ENDPOINT"], os.environ["MINIO_ACCESS_KEY"], os.environ["MINIO_SECRET_KEY"], secure=False)
    bucket = os.environ.get("MINIO_BUCKET", "student-assets")
    for object_key, data in objects:
        client.put_object(bucket, object_key, BytesIO(data), len(data), content_type="text/markdown")
    print(f"Seeded {len(objects)} demo documents (shared class summaries + per-tenant training reports) across {len(TENANTS)} tenants.")


if __name__ == "__main__":
    seed()
