"""Target-owned SQLAlchemy metadata for the tenant-safe MVP foundation."""

# pyright: reportMissingImports=false

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, MetaData, Numeric, String, Table, Text, UniqueConstraint, create_engine
from sqlalchemy.orm import sessionmaker
from pgvector.sqlalchemy import VECTOR

from app.core.config import settings

runtime_engine = create_engine(settings.runtime_database_url, pool_pre_ping=True)
auth_engine = create_engine(settings.auth_database_url, echo=False, hide_parameters=True, pool_pre_ping=True, pool_size=2, max_overflow=0, pool_reset_on_return="rollback")
assistant_engine = create_engine(settings.assistant_database_url, echo=False, hide_parameters=True, pool_pre_ping=True, pool_size=2, max_overflow=0, pool_reset_on_return="rollback")
SessionLocal = sessionmaker(bind=runtime_engine, expire_on_commit=False)
AuthSessionLocal = sessionmaker(bind=auth_engine, expire_on_commit=False)
AssistantSessionLocal = sessionmaker(bind=assistant_engine, expire_on_commit=False)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

metadata = MetaData()

users = Table(
    "users", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("email", String(320), nullable=False, unique=True),
    Column("password_hash", String(255), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)
tenants = Table(
    "tenants", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("name", String(120), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)
memberships = Table(
    "memberships", metadata,
    Column("tenant_id", UUID(as_uuid=True), ForeignKey("tenants.id"), primary_key=True),
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True),
    Column("active", Boolean, nullable=False, server_default="true"),
)
Index("memberships_one_active_user", memberships.c.user_id, unique=True, postgresql_where=memberships.c.active)
roles = Table(
    "roles", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("tenant_id", UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False),
    Column("name", String(32), nullable=False),
    UniqueConstraint("tenant_id", "name"),
)
permissions = Table(
    "permissions", metadata,
    Column("code", String(64), primary_key=True),
)
role_permissions = Table(
    "role_permissions", metadata,
    Column("tenant_id", UUID(as_uuid=True), ForeignKey("tenants.id"), primary_key=True),
    Column("role_id", UUID(as_uuid=True), ForeignKey("roles.id"), primary_key=True),
    Column("permission_code", String(64), ForeignKey("permissions.code"), primary_key=True),
)
experiments = Table(
    "experiments", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("tenant_id", UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False),
    Column("creator_id", UUID(as_uuid=True), ForeignKey("users.id"), nullable=False),
    Column("name", String(200), nullable=False), Column("status", String(16), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("tenant_id", "id"),
)
results = Table(
    "results", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("tenant_id", UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False),
    Column("experiment_id", UUID(as_uuid=True), nullable=False),
    Column("creator_id", UUID(as_uuid=True), ForeignKey("users.id"), nullable=False),
    Column("status", String(16), nullable=False), Column("input_summary", Text), Column("output_summary", Text),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("tenant_id", "id"), ForeignKeyConstraint(("tenant_id", "experiment_id"), ("experiments.tenant_id", "experiments.id")),
)
metrics = Table(
    "metrics", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("tenant_id", UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False),
    Column("result_id", UUID(as_uuid=True), nullable=False), Column("creator_id", UUID(as_uuid=True), ForeignKey("users.id"), nullable=False),
    Column("name", String(120), nullable=False), Column("value_type", String(16), nullable=False),
    Column("number_value", Numeric), Column("text_value", Text), Column("boolean_value", Boolean), Column("json_value", JSONB),
    Column("unit", String(40)), Column("step", Integer), Column("recorded_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    ForeignKeyConstraint(("tenant_id", "result_id"), ("results.tenant_id", "results.id")), CheckConstraint("step IS NULL OR step >= 0"),
)
documents = Table(
    "documents", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("tenant_id", UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False),
    Column("created_by", UUID(as_uuid=True), ForeignKey("users.id"), nullable=False),
    Column("name", String(255), nullable=False), Column("object_key", String(255), nullable=False),
    Column("content_type", String(32), nullable=False), Column("size_bytes", Integer, nullable=False), Column("sha256", String(64), nullable=False),
    Column("ingestion_status", String(16), nullable=False), UniqueConstraint("tenant_id", "id"), UniqueConstraint("tenant_id", "object_key"),
)
chunks = Table(
    "chunks", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("tenant_id", UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False),
    Column("document_id", UUID(as_uuid=True), nullable=False),
    Column("content", Text, nullable=False), Column("ordinal", Integer, nullable=False), Column("active", Boolean, nullable=False, server_default="false"),
    UniqueConstraint("tenant_id", "id"), ForeignKeyConstraint(("tenant_id", "document_id"), ("documents.tenant_id", "documents.id")),
)
embeddings = Table(
    "embeddings", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("tenant_id", UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False),
    Column("chunk_id", UUID(as_uuid=True), nullable=False),
    Column("embedding", VECTOR(384), nullable=False),
    ForeignKeyConstraint(("tenant_id", "chunk_id"), ("chunks.tenant_id", "chunks.id")), UniqueConstraint("tenant_id", "chunk_id"),
)
ingestion_runs = Table(
    "ingestion_runs", metadata, Column("id", UUID(as_uuid=True), primary_key=True),
    Column("tenant_id", UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False), Column("document_id", UUID(as_uuid=True), nullable=False),
    Column("status", String(16), nullable=False), Column("chunk_count", Integer, nullable=False), Column("error", String(240)),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    ForeignKeyConstraint(("tenant_id", "document_id"), ("documents.tenant_id", "documents.id")),
)
sessions = Table("sessions", metadata, Column("id", UUID(as_uuid=True), primary_key=True), Column("user_id", UUID(as_uuid=True), ForeignKey("users.id"), nullable=False), Column("token_hash", String(64), nullable=False, unique=True), Column("csrf_hash", String(64), nullable=False), Column("tenant_id", UUID(as_uuid=True), ForeignKey("tenants.id")), Column("expires_at", DateTime(timezone=True), nullable=False), Column("revoked_at", DateTime(timezone=True)))
recovery_tokens = Table("recovery_tokens", metadata, Column("id", UUID(as_uuid=True), primary_key=True), Column("user_id", UUID(as_uuid=True), ForeignKey("users.id"), nullable=False), Column("token_hash", String(64), nullable=False, unique=True), Column("expires_at", DateTime(timezone=True), nullable=False), Column("used_at", DateTime(timezone=True)))
membership_roles = Table("membership_roles", metadata, Column("tenant_id", UUID(as_uuid=True), ForeignKey("tenants.id"), primary_key=True), Column("user_id", UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True), Column("role_id", UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False))
audit_events = Table("audit_events", metadata, Column("id", UUID(as_uuid=True), primary_key=True), Column("actor_id", UUID(as_uuid=True), ForeignKey("users.id")), Column("tenant_id", UUID(as_uuid=True), ForeignKey("tenants.id")), Column("action", String(64), nullable=False), Column("outcome", String(16), nullable=False), Column("resource", String(120)), Column("metadata", JSONB, nullable=False, server_default="'{}'::jsonb"), Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()))
