"""Small, fail-closed OpenRouter adapter for guarded SQL and evidence answers."""

from __future__ import annotations

import json
import re
from typing import Any

import requests

from app.assistant.sql import SqlGuard, SqlRejected

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_PLACEHOLDERS = {"", "changeme", "change-me", "replace-me", "your-api-key", "sk-or-v1-placeholder"}  # gitleaks:allow -- rejected examples, never credentials
_SENSITIVE_KEYS = {"tenant_id", "object_key", "session", "session_token", "authorization", "cookie", "error", "provider"}


class OpenRouterProviderError(RuntimeError):
    """Sanitized provider/configuration failure."""


class OpenRouterAssistantProvider:
    """OpenRouter chat-completions provider with no retries and bounded disclosure."""

    def __init__(self, api_key: str | None, model: str | None):
        self._api_key = (api_key or "").strip()
        self._model = (model or "").strip()

    def _configured(self) -> None:
        normalized = self._api_key.lower()
        placeholder = normalized in _PLACEHOLDERS or normalized.startswith("<") or any(
            marker in normalized for marker in ("placeholder", "change_me", "replace_me", "your_api_key", "your-openrouter")
        )
        if not self._model or placeholder:
            raise OpenRouterProviderError("assistant provider is not configured")

    def _complete(self, messages: list[dict[str, str]], max_tokens: int) -> str:
        self._configured()
        try:
            response = requests.post(
                OPENROUTER_URL,
                headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
                json={"model": self._model, "messages": messages, "max_tokens": max_tokens},
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise ValueError("missing content")
            return content.strip()
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
            raise OpenRouterProviderError("assistant provider request failed safely") from None

    def plan_sql(self, prompt: str) -> str:
        schema = "\n".join(
            f"- {relation}({', '.join(sorted(columns))})"
            for relation, columns in sorted(SqlGuard.RELATIONS.items())
        )
        system = f"""Generate PostgreSQL read-only SQL from this exact allow-list:
{schema}
Return exactly one bare SELECT and nothing else. No markdown, comments, semicolon, DDL, DML,
functions, joins, WHERE/HAVING filters, aliases, quoting, subqueries, expressions, or relations/columns
outside the allow-list. Only comma-separated columns, one FROM relation, and optional ORDER BY one
allowed column ASC or DESC are accepted."""
        candidate = self._complete(
            [{"role": "system", "content": system}, {"role": "user", "content": prompt[:1000]}], 180
        )
        try:
            return SqlGuard().validate(candidate)
        except SqlRejected:
            raise OpenRouterProviderError("assistant provider returned unsafe SQL") from None

    @staticmethod
    def _safe_text(value: Any, limit: int) -> str:
        text = str(value)
        sensitive = re.compile(r"tenant.?id|object.?key|session|authorization|cookie|internal error|provider", re.I)
        return "\n".join(line for line in text.splitlines() if not sensitive.search(line))[:limit]

    @staticmethod
    def _safe_value(value: Any) -> Any:
        if isinstance(value, dict):
            return {str(k): OpenRouterAssistantProvider._safe_value(v) for k, v in value.items()
                    if str(k).lower() not in _SENSITIVE_KEYS and not str(k).lower().endswith("_id")}
        if isinstance(value, list):
            return [OpenRouterAssistantProvider._safe_value(item) for item in value[:20]]
        return OpenRouterAssistantProvider._safe_text(value, 500) if value is not None else None

    def compose(self, prompt: str, citations: list[dict[str, Any]], rows: list[dict[str, Any]], relational_available: bool) -> str:
        excerpts = [
            {"number": i, "document": self._safe_text(item.get("document_name", ""), 120),
             "ordinal": item.get("ordinal"), "excerpt": self._safe_text(item.get("content", ""), 800)}
            for i, item in enumerate(citations[:5], 1)
        ]
        relational = self._safe_value(rows[:20]) if relational_available else []
        evidence = json.dumps({"document_excerpts": excerpts, "relational_rows": relational}, ensure_ascii=False)
        system = """Answer exclusively from the supplied bounded evidence. If it is insufficient, say so.
Cite document claims as [excerpt N]. Clearly label relational evidence separately and never present it
as a document citation. Do not reveal or infer tenant IDs, object keys, session/authentication context,
internal errors, provider details, or secrets. Keep the answer under 500 characters."""
        answer = self._complete([
            {"role": "system", "content": system},
            {"role": "user", "content": f"Question: {self._safe_text(prompt, 1000)}\nEvidence: {evidence}"},
        ], 220)
        return answer[:500]
