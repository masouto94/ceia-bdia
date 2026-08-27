"""Strict read-only SQL validation and bounded assistant execution."""

# pyright: reportMissingImports=false

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, ClassVar, Protocol
from uuid import UUID

from sqlalchemy import column, select, table, text
from sqlalchemy.sql import Select

from app.core.config import settings
from app.core.database import AssistantSessionLocal


class SqlRejected(ValueError):
    """Raised before database access when generated SQL is outside the allow-list."""


class SqlExecutionError(RuntimeError):
    """Safe failure for database or result-bound errors."""


@dataclass(frozen=True)
class SqlResult:
    query: str
    rows: list[dict[str, Any]]
    serialized_bytes: int


class SqlGuard:
    """Accept only a deliberately small SELECT grammar over curated views."""

    RELATIONS: ClassVar = {
        "public.assistant_experiments": {"id", "name", "status", "created_at", "updated_at"},
        "public.assistant_results": {"id", "experiment_id", "status", "input_summary", "output_summary", "created_at"},
        "public.assistant_metrics": {"result_id", "name", "value_type", "number_value", "text_value", "boolean_value", "unit", "step", "recorded_at"},
    }
    TABLES: ClassVar = {
        relation: table(
            relation.removeprefix("public."),
            *(column(name) for name in columns),
            schema="public",
        )
        for relation, columns in RELATIONS.items()
    }
    _QUERY: ClassVar[re.Pattern[str]] = re.compile(
        r"SELECT\s+(?P<columns>[a-z_][a-z0-9_]*(?:\s*,\s*[a-z_][a-z0-9_]*)*)"
        r"\s+FROM\s+(?P<relation>public\.assistant_[a-z_][a-z0-9_]*)"
        r"(?:\s+ORDER\s+BY\s+(?P<order>[a-z_][a-z0-9_]*)(?:\s+(?P<direction>ASC|DESC))?)?",
        re.IGNORECASE,
    )

    def _parse(self, query: str) -> tuple[str, list[str], str, str, str]:
        candidate = query.strip()
        if not candidate or len(candidate) > 4096 or not candidate.isascii():
            raise SqlRejected("query is empty or exceeds the safe lexical boundary")
        if any(marker in candidate for marker in (";", "--", "/*", "*/", "#", "'", '"', "$")):
            raise SqlRejected("comments, quoting, and multiple statements are not allowed")
        match = self._QUERY.fullmatch(candidate)
        if match is None:
            raise SqlRejected("only one simple allow-listed SELECT is accepted")
        relation = match.group("relation").lower()
        allowed = self.RELATIONS.get(relation)
        columns = [name.strip().lower() for name in match.group("columns").split(",")]
        order = (match.group("order") or "").lower()
        if allowed is None or not set(columns).issubset(allowed) or (order and order not in allowed):
            raise SqlRejected("relation or column is not allow-listed")
        direction = (match.group("direction") or "").upper()
        ordering = f" ORDER BY {order}{f' {direction}' if direction else ''}" if order else ""
        canonical = f"SELECT {', '.join(columns)} FROM {relation}{ordering}"
        return canonical, columns, relation, order, direction

    def validate(self, query: str) -> str:
        """Return the canonical provenance string after complete lexical validation."""
        return self._parse(query)[0]

    def build_select(self, query: str, limit: int) -> tuple[str, Select]:
        """Build executable SQL only by selecting objects from the fixed allow-list."""
        canonical, columns, relation, order, direction = self._parse(query)
        relation_table = self.TABLES[relation]
        statement = select(*(relation_table.c[name] for name in columns)).select_from(relation_table)
        if order:
            order_column = relation_table.c[order]
            statement = statement.order_by(order_column.desc() if direction == "DESC" else order_column.asc())
        return canonical, statement.limit(limit)


class AssistantProofContext(Protocol):
    @property
    def user_id(self) -> UUID: ...

    @property
    def tenant_id(self) -> UUID: ...

    @property
    def session_digest(self) -> str: ...


class SqlExecutor:
    """Execute guarded SQL with trusted context and hard resource limits."""

    def __init__(self, session_factory: Callable[[], Any] = AssistantSessionLocal, guard: SqlGuard | None = None):
        self._session_factory = session_factory
        self._guard = guard or SqlGuard()

    def execute(
        self,
        query: str,
        *,
        context: AssistantProofContext,
    ) -> SqlResult:
        # Callers pass the opaque trusted authority as context=context.
        guarded, statement = self._guard.build_select(query, settings.sql_max_rows + 1)
        if not re.fullmatch(r"[0-9a-f]{64}", context.session_digest):
            raise PermissionError("trusted session proof is required")
        session = None
        try:
            session = self._session_factory()
            with session.begin():
                session.execute(text("SET TRANSACTION READ ONLY"))
                session.execute(text("SELECT set_config('statement_timeout', :timeout, true)"), {"timeout": f"{settings.sql_statement_timeout_ms}ms"})
                session.execute(text("SELECT set_config('app.session_proof', :value, true)"), {"value": context.session_digest})
                session.execute(text("SELECT set_config('app.account_scope', 'tenant', true)"))
                session.execute(text("SELECT set_config('app.user_id', :value, true)"), {"value": str(context.user_id)})
                session.execute(text("SELECT set_config('app.tenant_id', :value, true)"), {"value": str(context.tenant_id)})
                result = session.execute(statement)
                rows = [dict(row) for row in result.mappings().all()]
                if len(rows) > settings.sql_max_rows:
                    raise SqlExecutionError("assistant query exceeded the row limit")
                size = len(json.dumps(rows, default=str, separators=(",", ":")).encode())
                if size > settings.sql_max_result_bytes:
                    raise SqlExecutionError("assistant query exceeded the result size limit")
                return SqlResult(guarded, rows, size)
        except SqlExecutionError:
            raise
        except Exception as exc:
            raise SqlExecutionError("assistant query could not be completed safely") from exc
        finally:
            if session is not None:
                session.close()
