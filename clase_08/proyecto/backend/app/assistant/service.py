"""Bounded assistant orchestration over trusted tenant-scoped retrieval seams."""

# pyright: reportMissingImports=false

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from app.assistant.openrouter import OpenRouterAssistantProvider
from app.assistant.sql import SqlExecutionError, SqlExecutor, SqlRejected
from app.core.config import settings
from app.documents import _retrieval_statement, _set_context, embedding_provider

Mode = Literal["document", "relational", "combined", "auto"]


class AssistantUnavailable(RuntimeError):
    """No safe assistant result can be produced."""


@dataclass(frozen=True)
class TrustedAssistantContext:
    """Opaque-session-derived authority; providers never receive this value."""

    user_id: UUID
    tenant_id: UUID
    role: str
    session_digest: str = field(repr=False)


class AssistantProvider(Protocol):
    def plan_sql(self, prompt: str) -> str: ...
    def compose(self, prompt: str, citations: list[dict[str, Any]], rows: list[dict[str, Any]], relational_available: bool) -> str: ...


class LocalAssistantProvider:
    """Explicit deterministic test double; never the runtime default."""

    def plan_sql(self, prompt: str) -> str:
        lowered = prompt.lower()
        if "metric" in lowered:
            return "SELECT name, value_type, number_value, text_value, unit FROM public.assistant_metrics ORDER BY recorded_at DESC"
        if "result" in lowered:
            return "SELECT status, input_summary, output_summary FROM public.assistant_results ORDER BY created_at DESC"
        return "SELECT name, status FROM public.assistant_experiments ORDER BY created_at DESC"

    def compose(self, prompt: str, citations: list[dict[str, Any]], rows: list[dict[str, Any]], relational_available: bool) -> str:
        sources = []
        if citations:
            sources.append(f"{len(citations)} document excerpt(s)")
        if relational_available:
            sources.append(f"{len(rows)} relational row(s)")
        return ("Safe evidence found: " + " and ".join(sources) + ".")[:500]


class DocumentRetriever:
    def __init__(self, db: Session):
        self._db = db

    def retrieve(self, prompt: str, context: TrustedAssistantContext, limit: int = 5) -> list[dict[str, Any]]:
        vector = embedding_provider.embed(prompt)
        with self._db.begin():
            _set_context(self._db, {"user_id": context.user_id, "session_digest": context.session_digest}, context.tenant_id)
            rows = self._db.execute(_retrieval_statement(vector, context.tenant_id, limit)).mappings().all()
        return [
            {
                "chunk_id": str(row["id"]), "document_id": str(row["document_id"]),
                "document_name": row["name"], "ordinal": row["ordinal"],
                "content": str(row["content"])[:1000],
            }
            for row in rows
        ]


class AssistantService:
    def __init__(self, documents: DocumentRetriever, sql: SqlExecutor | None = None,
                 provider: AssistantProvider | None = None):
            self.documents, self.sql = documents, sql or SqlExecutor()
            self.provider = provider or OpenRouterAssistantProvider(
                settings.openrouter_api_key, settings.openrouter_model
            )

    def answer(self, prompt: str, mode: Mode, context: TrustedAssistantContext) -> dict[str, Any]:
        if context.role not in {"admin", "member", "viewer"}:
            raise PermissionError("assistant capability is required")
        resolved: Mode = "combined" if mode == "auto" else mode
        citations: list[dict[str, Any]] = []
        rows: list[dict[str, Any]] = []
        provenance: dict[str, Any] | None = None
        unavailable: list[str] = []

        if resolved in {"document", "combined"}:
            try:
                citations = self.documents.retrieve(prompt, context)
                if not citations:
                    unavailable.append("document")
            except Exception:
                unavailable.append("document")
        if resolved in {"relational", "combined"}:
            try:
                result = self.sql.execute(
                    self.provider.plan_sql(prompt),
                    context=context,  # pyright: ignore[reportArgumentType] -- frozen dataclass satisfies the read-only proof protocol
                )
                rows = result.rows
                provenance = {"query": result.query, "row_count": len(rows)}
            except (SqlRejected, SqlExecutionError, PermissionError, RuntimeError):
                unavailable.append("relational")

        expected = {"document"} if resolved == "document" else {"relational"} if resolved == "relational" else {"document", "relational"}
        if expected.issubset(unavailable):
            raise AssistantUnavailable("no safe assistant evidence is available")
        try:
            answer = self.provider.compose(prompt, citations, rows, provenance is not None)
        except Exception as exc:
            raise AssistantUnavailable("provider could not produce a safe answer") from exc
        if not answer:
            raise AssistantUnavailable("provider returned no safe answer")
        return {
            "requested_mode": mode, "resolved_mode": resolved,
            "status": "partial" if unavailable else "complete", "answer": answer[:500],
            "citations": citations, "relational": {"rows": rows, "sql_provenance": provenance} if provenance else None,
            "unavailable": unavailable,
        }
