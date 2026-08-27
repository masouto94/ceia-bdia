"""Focused contracts for private document ingestion and tenant-safe retrieval."""

import json
import os
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql import Select

os.environ.update({
    "RUNTIME_DATABASE_URL": "postgresql+psycopg://runtime:password@db/student_project",
    "AUTH_DATABASE_URL": "postgresql+psycopg://auth:password@db/student_project",
    "ASSISTANT_DATABASE_URL": "postgresql+psycopg://assistant:password@db/student_project",
    "MINIO_ACCESS_KEY": "local-user", "MINIO_SECRET_KEY": "local-password",
    "SMTP_FROM": "noreply@example.test", "SESSION_SECRET": "test-session-secret",
    "RECOVERY_TOKEN_SECRET": "test-recovery-secret",
})

from app.documents import (AuthorizedAsset, FixedEmbeddingProvider, HTTPEmbeddingProvider,
                           MinioObjectStore, RetrievalRequest, _retrieval_statement, chunk_text,
                           _document_detail_statements, extract_text, get_document, ingest_document, retrieve)


class DocumentContracts(unittest.TestCase):
    def test_document_detail_uses_tenant_bound_statements_and_returns_latest_run(self) -> None:
        tenant, document_id, user_id = uuid4(), uuid4(), uuid4()
        statements = _document_detail_statements(document_id, tenant)
        self.assertEqual(len(statements), 3)
        self.assertTrue(all("tenant" in str(statement) and "document" in str(statement) for statement in statements))
        db = MagicMock()
        document = MagicMock(); document.mappings.return_value.first.return_value = {"id": document_id, "name": "guide.md", "content_type": "text/markdown", "size_bytes": 12, "ingestion_status": "ready"}
        chunks = MagicMock(); chunks.scalar_one.return_value = 2
        latest = MagicMock(); latest.mappings.return_value.first.return_value = {"status": "ready", "chunk_count": 2, "created_at": "2026-03-30T10:00:00Z", "error": None}
        db.execute.side_effect = [document, chunks, latest]
        with (patch("app.documents._authorize", return_value=({"user_id": user_id}, tenant)), patch("app.documents._set_context")):
            response = get_document(document_id, db=db)
        self.assertEqual(response["active_chunk_count"], 2)
        self.assertEqual(response["latest_run"]["chunk_count"], 2)

    def test_private_store_requires_authorized_capability_and_preserves_bytes(self) -> None:
        client = Mock(); client.get_object.return_value = BytesIO(b"original")
        store = MinioObjectStore(client, "private")
        asset = AuthorizedAsset("tenant/opaque", "tenant")
        store.put(asset, b"original", "text/plain")
        self.assertEqual(store.get(asset), b"original")
        client.put_object.assert_called_once()
        with self.assertRaises(TypeError):
            store.get("tenant/opaque")  # type: ignore[arg-type]

    def test_extractors_and_chunks_are_bounded(self) -> None:
        self.assertEqual(extract_text(b"hello", "text/plain"), "hello")
        self.assertEqual(extract_text(b"# title", "text/markdown"), "# title")
        with self.assertRaises(ValueError): extract_text(b"\xff", "text/plain")
        with self.assertRaises(ValueError): extract_text(b"x", "application/json")
        chunks = chunk_text("alpha beta gamma delta", size=10, overlap=2)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(value) <= 10 for value in chunks))

    def test_embedding_dimension_and_malformed_provider_output_fail_closed(self) -> None:
        provider = FixedEmbeddingProvider(384)
        vector = provider.embed("same", "passage")
        self.assertEqual(len(vector), 384)
        self.assertAlmostEqual(sum(value * value for value in vector), 1.0)
        self.assertEqual(vector, provider.embed("same"))
        bad = FixedEmbeddingProvider(384, lambda _: [0.0])
        with self.assertRaises(RuntimeError): bad.embed("query")
        unavailable = FixedEmbeddingProvider(384, lambda _: (_ for _ in ()).throw(OSError("offline")))
        with self.assertRaises(RuntimeError): unavailable.embed("query")

    def test_http_embedding_contract_success_and_fail_closed(self) -> None:
        provider = HTTPEmbeddingProvider("http://embeddings-api:8000", 384, "model")
        response = MagicMock(status=200)
        response.__enter__.return_value = response
        response.read.return_value = json.dumps({"vector": [0.0] * 384, "dimension": 384, "modelo": "model"}).encode()
        with patch("app.documents.urlopen", return_value=response) as request:
            self.assertEqual(provider.embed("text", "passage"), [0.0] * 384)
        self.assertEqual(json.loads(request.call_args.args[0].data), {"texto": "text", "tipo": "passage"})
        self.assertEqual(request.call_args.kwargs["timeout"], 60)
        response.status = 503
        with patch("app.documents.urlopen", return_value=response), self.assertRaises(RuntimeError):
            provider.embed("secret")
        response.status = 200
        for payload in (b"not-json", json.dumps({"vector": [0.0], "dimension": 384, "modelo": "model"}).encode(),
                        json.dumps({"vector": [0.0] * 384, "dimension": 8, "modelo": "model"}).encode()):
            response.read.return_value = payload
            with self.subTest(payload=payload[:12]), patch("app.documents.urlopen", return_value=response), self.assertRaises(RuntimeError):
                provider.embed("secret")
        for failure in (TimeoutError("slow"), OSError("non-2xx")):
            with patch("app.documents.urlopen", side_effect=failure), self.assertRaises(RuntimeError) as raised:
                provider.embed("secret")
            self.assertNotIn("secret", str(raised.exception))

    def test_ingestion_and_retrieval_use_explicit_e5_intents(self) -> None:
        source = Path("app/documents.py").read_text()
        self.assertIn('embedding_provider.embed(part, "passage")', source)
        self.assertIn('embedding_provider.embed(payload.query, "query")', source)

    def test_ingestion_cleanup_failure_is_logged_without_replacing_primary_error(self) -> None:
        tenant = uuid4()
        primary_error = RuntimeError("primary ingestion failure")
        cleanup_error = RuntimeError("cleanup persistence failure")
        rollback_error = RuntimeError("cleanup rollback failure")
        db = MagicMock()
        db.execute.side_effect = [primary_error, cleanup_error]
        db.rollback.side_effect = [None, rollback_error]

        with (patch("app.documents._session", return_value={"user_id": uuid4()}),
              patch("app.documents._csrf"),
              patch("app.documents._tenant_context", return_value=tenant),
              patch("app.documents._set_context"),
              patch("app.documents.logger.error") as log_error,
              patch("app.documents.logger.exception") as log_exception):
            with self.assertRaises(HTTPException) as raised:
                ingest_document(uuid4(), Mock(), db=db)

        self.assertEqual(raised.exception.status_code, 503)
        self.assertIs(raised.exception.__cause__, primary_error)
        self.assertIs(log_error.call_args.kwargs["exc_info"], cleanup_error)
        log_exception.assert_called_once()

    def test_ingestion_embedding_failure_happens_before_chunk_replacement(self) -> None:
        tenant, document_id = uuid4(), uuid4()
        db = MagicMock()
        row = MagicMock()
        row.mappings.return_value.first.return_value = {
            "object_key": "opaque-key",
            "content_type": "text/plain",
            "sha256": "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824",
        }

        def execute(statement, *_args, **_kwargs):
            return row if "SELECT object_key" in str(statement) else MagicMock()

        db.execute.side_effect = execute
        with (patch("app.documents._session", return_value={"user_id": uuid4()}),
              patch("app.documents._csrf"),
              patch("app.documents._tenant_context", return_value=tenant),
              patch("app.documents._set_context"),
              patch("app.documents._store") as store,
              patch("app.documents.embedding_provider.embed", side_effect=RuntimeError("offline"))):
            store.return_value.get.return_value = b"hello"
            with self.assertRaises(HTTPException) as raised:
                ingest_document(document_id, Mock(), db=db)

        self.assertEqual(raised.exception.status_code, 503)
        statements = [str(call.args[0]) for call in db.execute.call_args_list]
        self.assertNotIn("DELETE FROM chunks", "\n".join(statements))

    def test_retrieval_database_failure_is_logged_and_returns_safe_service_error(self) -> None:
        tenant = uuid4()
        database_error = SQLAlchemyError("secret database details")
        db = MagicMock()
        db.execute.side_effect = database_error

        with (patch("app.documents._authorize", return_value=({"user_id": uuid4()}, tenant)),
              patch("app.documents._set_context"),
              patch("app.documents.embedding_provider.embed", return_value=[0.0] * 384) as embed,
              patch("app.documents.logger.exception") as log_exception):
            with self.assertRaises(HTTPException) as raised:
                retrieve(RetrievalRequest(query="bounded query"), db=db)

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(raised.exception.detail, "Document retrieval is unavailable.")
        self.assertNotIn("secret database details", raised.exception.detail)
        self.assertIs(raised.exception.__cause__, database_error)
        embed.assert_called_once_with("bounded query", "query")
        log_exception.assert_called_once_with(
            "Document retrieval database query failed",
            extra={"tenant_id": str(tenant)},
        )

    def test_retrieval_distance_conversion_fails_closed_and_keeps_valid_citations(self) -> None:
        tenant = uuid4()
        row = {
            "id": uuid4(),
            "document_id": uuid4(),
            "name": "retrieved.txt",
            "ordinal": 0,
            "content": "retrieved content",
        }

        for invalid_distance in ("not-a-number", None):
            with self.subTest(distance=invalid_distance):
                db = MagicMock()
                db.execute.return_value.mappings.return_value.all.return_value = [{**row, "distance": invalid_distance}]
                with (patch("app.documents._authorize", return_value=({"user_id": uuid4()}, tenant)),
                      patch("app.documents._set_context"),
                      patch("app.documents.embedding_provider.embed", return_value=[0.0] * 384)):
                    with self.assertRaises(HTTPException) as raised:
                        retrieve(RetrievalRequest(query="bounded query"), db=db)
                self.assertEqual((raised.exception.status_code, raised.exception.detail), (503, "Document retrieval returned invalid data."))

        db = MagicMock()
        db.execute.return_value.mappings.return_value.all.return_value = [{**row, "distance": "0.125"}]
        with (patch("app.documents._authorize", return_value=({"user_id": uuid4()}, tenant)),
              patch("app.documents._set_context"),
              patch("app.documents.embedding_provider.embed", return_value=[0.0] * 384)):
            response = retrieve(RetrievalRequest(query="bounded query"), db=db)
        self.assertEqual(response["citations"][0]["distance"], 0.125)

    def test_retrieval_statement_uses_structured_bounded_tenant_query(self) -> None:
        tenant = uuid4()
        statement = _retrieval_statement([0.0] * 384, tenant, 7)

        self.assertIsInstance(statement, Select)
        compiled = statement.compile(dialect=postgresql.dialect())
        sql = str(compiled)
        self.assertNotIn("LIMIT :limit", sql)
        self.assertIn("LIMIT %(param_1)s", sql)
        self.assertEqual(compiled.params["param_1"], 7)
        self.assertEqual(sql.count("tenant_id ="), 5)  # Three tenant filters plus two tenant-safe joins.
        self.assertIn("ORDER BY distance", sql)
        self.assertIn("<=>", sql)

    def test_migration_has_vector_rls_tenant_fks_and_active_chunks(self) -> None:
        migration = Path("migrations/versions/20260330_08_documents_rag.py").read_text()
        for marker in ("vector(8)", "FORCE ROW LEVEL SECURITY", "ingestion_runs_tenant_isolation",
                       "FOREIGN KEY (tenant_id, document_id)", "active boolean", "object_key"):
            self.assertIn(marker, migration)
        forward = Path("migrations/versions/20260330_10_e5_embeddings.py").read_text()
        for marker in ("DELETE FROM embeddings", "active=false", "ingestion_status='pending'", "vector(384)", "embeddings_cosine_idx"):
            self.assertIn(marker, forward)
        self.assertNotIn("pad", forward.lower())


if __name__ == "__main__":
    unittest.main()
