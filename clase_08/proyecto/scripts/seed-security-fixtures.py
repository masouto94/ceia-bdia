#!/usr/bin/env python3
"""Seed deterministic, tenant-isolated demo data without emitting secrets."""

from __future__ import annotations

import os
import math
import sys
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import Callable, Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from minio import Minio  # pyright: ignore[reportMissingImports] -- provided by the API runtime
from sqlalchemy import Column, MetaData, String, Table, create_engine, text  # pyright: ignore[reportMissingImports] -- provided by the API runtime
from sqlalchemy.dialects.postgresql import UUID, insert as pg_insert  # pyright: ignore[reportMissingImports] -- provided by the API runtime

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "backend"))

from app.core.config import AdminToolSettings  # noqa: E402  # pyright: ignore[reportMissingImports] -- backend path inserted above
  # pyright: ignore[reportMissingImports] -- backend path inserted above
from app.security.password import hash_password  # pyright: ignore[reportMissingImports] -- backend path inserted above

PREFIX = "https://example.test/gentle-ai/demo/"
ROLES = ("admin", "member", "viewer")
TENANTS = (("alpha", "Alpha Research Lab"), ("beta", "Beta Evaluation Lab"))
DASHBOARD_DAYS = 91
users_table = Table(
    "users", MetaData(),
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("email", String(320)),
    Column("password_hash", String(255)),
)
FIXTURE_EMAIL_VARIABLES = {
    "alpha": {
        "admin": "ALPHA_ADMIN_EMAIL",
        "member": "ALPHA_MEMBER_EMAIL",
        "viewer": "ALPHA_VIEWER_EMAIL",
    },
    "beta": {
        "admin": "BETA_ADMIN_EMAIL",
        "member": "BETA_MEMBER_EMAIL",
        "viewer": "BETA_VIEWER_EMAIL",
    },
}


def load_fixture_credentials() -> tuple[dict[str, dict[str, str]], str]:
    from email_validator import EmailNotValidError, validate_email  # pyright: ignore[reportMissingImports] -- provided by the API runtime

    email_variables = [
        (tenant, role, name)
        for tenant, roles in FIXTURE_EMAIL_VARIABLES.items()
        for role, name in roles.items()
    ]
    missing = [name for _, _, name in email_variables if not os.environ.get(name)]
    if not os.environ.get("FIXTURE_PASSWORD"):
        missing.append("FIXTURE_PASSWORD")
    if missing:
        raise SystemExit("Required fixture environment variables are missing: " + ", ".join(missing))

    emails: dict[str, dict[str, str]] = {tenant: {} for tenant in FIXTURE_EMAIL_VARIABLES}
    invalid: list[str] = []
    for tenant, role, name in email_variables:
        try:
            emails[tenant][role] = validate_email(
                os.environ[name].strip(), check_deliverability=False
            ).normalized
        except EmailNotValidError:
            invalid.append(name)
    if invalid:
        raise SystemExit("Invalid fixture email variables: " + ", ".join(invalid))

    normalized_emails = [emails[tenant][role] for tenant, role, _ in email_variables]
    duplicate_names = [
        name
        for tenant, role, name in email_variables
        if normalized_emails.count(emails[tenant][role]) > 1
    ]
    if duplicate_names:
        raise SystemExit("Fixture email variables must be distinct: " + ", ".join(duplicate_names))

    password = os.environ["FIXTURE_PASSWORD"]
    if len(password) < 8:
        raise SystemExit("FIXTURE_PASSWORD must contain at least 8 characters.")
    return emails, password


def fixture_id(value: str) -> UUID:
    return uuid5(NAMESPACE_URL, PREFIX + value)


class FixedEmbeddingProvider:
    """Deterministic normalized fixture provider; no request context crosses this seam."""

    def __init__(self, dimension: int, adapter: Callable[[str], list[float]] | None = None):
        self.dimension, self.adapter = dimension, adapter or self._local

    def _local(self, value: str) -> list[float]:
        raw = [(sha256(f"{index}:{value}".encode()).digest()[0] / 127.5) - 1.0 for index in range(self.dimension)]
        norm = sum(item * item for item in raw) ** 0.5
        return [item / norm for item in raw]

    def embed(self, value: str, intent: Literal["query", "passage"] = "query") -> list[float]:
        try:
            vector = self.adapter(value)
        except Exception as exc:
            raise RuntimeError("embedding provider unavailable") from exc
        if len(vector) != self.dimension or any(isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item) for item in vector):
            raise RuntimeError("embedding provider returned a malformed vector")
        return [float(item) for item in vector]


def seed_fixture_chunk_and_embedding(
    connection,
    tenant_id: UUID,
    document_id: UUID,
    chunk_id: UUID,
    embedding_id: UUID,
    content: str,
    embedding: str,
) -> None:
    """Replace only this fixture document's vector rows with deterministic IDs."""
    document_params = {"tenant": tenant_id, "document": document_id}
    connection.execute(
        text("""DELETE FROM embeddings USING chunks
            WHERE embeddings.tenant_id = :tenant
              AND chunks.tenant_id = :tenant
              AND chunks.document_id = :document
              AND embeddings.chunk_id = chunks.id"""),
        document_params,
    )
    connection.execute(
        text("DELETE FROM chunks WHERE tenant_id = :tenant AND document_id = :document"),
        document_params,
    )
    connection.execute(
        text("""INSERT INTO chunks(id,tenant_id,document_id,content,ordinal,active)
            VALUES (:id,:tenant,:document,:content,0,true)"""),
        document_params | {"id": chunk_id, "content": content},
    )
    connection.execute(
        text("""INSERT INTO embeddings(id,tenant_id,chunk_id,embedding)
            VALUES (:id,:tenant,:chunk,CAST(:embedding AS vector))"""),
        {"id": embedding_id, "tenant": tenant_id, "chunk": chunk_id, "embedding": embedding},
    )


def seed() -> None:
    fixture_emails, password = load_fixture_credentials()
    objects: list[tuple[str, bytes]] = []
    admin_settings = AdminToolSettings()
    engine = create_engine(admin_settings.migrator_database_url)
    embedder = FixedEmbeddingProvider(384)
    with engine.connect() as connection:
        for slug, tenant_name in TENANTS:
            tenant_id = fixture_id(f"tenant/{slug}")
            users = {role: fixture_id(f"tenant/{slug}/user/{role}") for role in ROLES}
            roles = {role: fixture_id(f"tenant/{slug}/role/{role}") for role in ROLES}
            experiment_id = fixture_id(f"tenant/{slug}/experiment")
            result_id = fixture_id(f"tenant/{slug}/result")
            document_id = fixture_id(f"tenant/{slug}/document")
            chunk_id = fixture_id(f"tenant/{slug}/chunk")
            content = f"{tenant_name} private retrieval fixture. Dataset policy: {slug}-only."
            data = content.encode()
            object_key = f"{tenant_id.hex}/demo-security-fixture.txt"
            objects.append((object_key, data))
            tenant_emails = fixture_emails[slug]

            with connection.begin():
                connection.execute(text("SET ROLE project_owner"))
                connection.execute(text("SELECT set_config('app.user_id', :value, true)"), {"value": str(users["admin"])})
                connection.execute(text("SELECT set_config('app.tenant_id', :value, true)"), {"value": str(tenant_id)})
                for role, user_id in users.items():
                    user_insert = pg_insert(users_table).values(
                        id=user_id,
                        email=tenant_emails[role],
                        password_hash=hash_password(password),
                    )
                    connection.execute(
                        user_insert.on_conflict_do_update(
                            index_elements=[users_table.c.id],
                            set_={
                                "email": user_insert.excluded.email,
                                "password_hash": user_insert.excluded.password_hash,
                            },
                        )
                    )
                # pi-lens-ignore: python-sql-injection
                connection.execute(text("INSERT INTO tenants(id,name) VALUES (:id,:name) ON CONFLICT DO NOTHING"), {"id": tenant_id, "name": tenant_name})
                # pi-lens-ignore: python-sql-injection
                connection.execute(text("INSERT INTO permissions(code) VALUES ('members:manage') ON CONFLICT DO NOTHING"))
                for role, user_id in users.items():
                    # pi-lens-ignore: python-sql-injection
                    connection.execute(text("INSERT INTO memberships(tenant_id,user_id) VALUES (:tenant,:user) ON CONFLICT DO NOTHING"), {"tenant": tenant_id, "user": user_id})
                    # pi-lens-ignore: python-sql-injection
                    connection.execute(text("INSERT INTO roles(id,tenant_id,name) VALUES (:id,:tenant,:name) ON CONFLICT DO NOTHING"), {"id": roles[role], "tenant": tenant_id, "name": role})
                    # pi-lens-ignore: python-sql-injection
                    connection.execute(text("INSERT INTO membership_roles(tenant_id,user_id,role_id) VALUES (:tenant,:user,:role) ON CONFLICT DO NOTHING"), {"tenant": tenant_id, "user": user_id, "role": roles[role]})
                # pi-lens-ignore: python-sql-injection
                connection.execute(text("INSERT INTO role_permissions(tenant_id,role_id,permission_code) VALUES (:tenant,:role,'members:manage') ON CONFLICT DO NOTHING"), {"tenant": tenant_id, "role": roles["admin"]})
                # pi-lens-ignore: python-sql-injection
                connection.execute(text("INSERT INTO experiments(id,tenant_id,creator_id,name,status) VALUES (:id,:tenant,:user,:name,'completed') ON CONFLICT DO NOTHING"), {"id": experiment_id, "tenant": tenant_id, "user": users["admin"], "name": f"{tenant_name} baseline"})
                for day in range(DASHBOARD_DAYS):
                    created_at = datetime.now(UTC) - timedelta(days=day)
                    dashboard_experiment = fixture_id(f"tenant/{slug}/dashboard/experiment/{day}")
                    dashboard_result = fixture_id(f"tenant/{slug}/dashboard/result/{day}")
                    dashboard_metric = fixture_id(f"tenant/{slug}/dashboard/metric/{day}")
                    experiment_status = ("completed", "running", "failed", "draft")[day % 4]
                    # pi-lens-ignore: python-sql-injection
                    connection.execute(text("""INSERT INTO experiments(id,tenant_id,creator_id,name,status,created_at,updated_at)
                        VALUES (:id,:tenant,:user,:name,:status,:created,:created) ON CONFLICT DO NOTHING"""), {"id": dashboard_experiment, "tenant": tenant_id, "user": users["admin"], "name": f"{tenant_name} dashboard {day + 1:03d}", "status": experiment_status, "created": created_at})
                    if experiment_status != "draft":
                        result_status = "failed" if experiment_status == "failed" else "completed"
                        # pi-lens-ignore: python-sql-injection
                        connection.execute(text("""INSERT INTO results(id,tenant_id,experiment_id,creator_id,status,input_summary,output_summary,created_at)
                            VALUES (:id,:tenant,:experiment,:user,:status,'dashboard input','dashboard output',:created) ON CONFLICT DO NOTHING"""), {"id": dashboard_result, "tenant": tenant_id, "experiment": dashboard_experiment, "user": users["member"], "status": result_status, "created": created_at})
                        # pi-lens-ignore: python-sql-injection
                        connection.execute(text("""INSERT INTO metrics(id,tenant_id,result_id,creator_id,name,value_type,number_value,step,recorded_at)
                            VALUES (:id,:tenant,:result,:user,'dashboard_score','number',:value,:step,:created) ON CONFLICT DO NOTHING"""), {"id": dashboard_metric, "tenant": tenant_id, "result": dashboard_result, "user": users["member"], "value": round(0.5 + day / 200, 3), "step": day, "created": created_at})
                # pi-lens-ignore: python-sql-injection
                connection.execute(text("INSERT INTO results(id,tenant_id,experiment_id,creator_id,status,input_summary,output_summary) VALUES (:id,:tenant,:experiment,:user,'completed','deterministic input','deterministic output') ON CONFLICT DO NOTHING"), {"id": result_id, "tenant": tenant_id, "experiment": experiment_id, "user": users["member"]})
                metric_values = (
                    ("number", {"number": 0.91}), ("text", {"text_value": "accepted"}),
                    ("boolean", {"boolean": True}), ("json", {"json_value": '{"fold": 1}'}),
                )
                for index, (kind, value) in enumerate(metric_values):
                    params = {"id": fixture_id(f"tenant/{slug}/metric/{kind}"), "tenant": tenant_id, "result": result_id,
                              "user": users["member"], "name": f"fixture_{kind}", "kind": kind,
                              "number": None, "text_value": None, "boolean": None, "json_value": None} | value
                    # pi-lens-ignore: python-sql-injection
                    connection.execute(text("""INSERT INTO metrics(id,tenant_id,result_id,creator_id,name,value_type,number_value,text_value,boolean_value,json_value,step)
                        VALUES (:id,:tenant,:result,:user,:name,:kind,:number,:text_value,:boolean,CAST(:json_value AS jsonb),:step) ON CONFLICT DO NOTHING"""), params | {"step": index})
                # pi-lens-ignore: python-sql-injection
                connection.execute(text("""INSERT INTO documents(id,tenant_id,created_by,name,object_key,ingestion_status,content_type,size_bytes,sha256)
                    VALUES (:id,:tenant,:user,'demo-security-fixture.txt',:key,'ready','text/plain',:size,:digest) ON CONFLICT DO NOTHING"""),
                    {"id": document_id, "tenant": tenant_id, "user": users["member"], "key": object_key, "size": len(data), "digest": sha256(data).hexdigest()})
                seed_fixture_chunk_and_embedding(
                    connection=connection,
                    tenant_id=tenant_id,
                    document_id=document_id,
                    chunk_id=chunk_id,
                    embedding_id=fixture_id(f"tenant/{slug}/embedding"),
                    content=content,
                    embedding=str(embedder.embed(content, "passage")),
                )

    client = Minio(os.environ["MINIO_ENDPOINT"], os.environ["MINIO_ACCESS_KEY"], os.environ["MINIO_SECRET_KEY"], secure=False)
    for object_key, data in objects:
        client.put_object(os.environ.get("MINIO_BUCKET", "student-assets"), object_key, BytesIO(data), len(data), content_type="text/plain")
    print("Seeded 2 tenants, 6 identities, and isolated relational/vector/object fixtures.")


if __name__ == "__main__":
    seed()
