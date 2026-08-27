"""Offline service contracts: model loading is replaced before module import."""
# pyright: reportMissingImports=false
import importlib
import sys
import types
import unittest
from unittest.mock import Mock


class FakeVector(list):
    def tolist(self): return list(self)


model = Mock()
model.get_sentence_embedding_dimension.return_value = 384
model.encode.return_value = FakeVector([0.0] * 384)
fake_library = types.ModuleType("sentence_transformers")
fake_library.SentenceTransformer = Mock(return_value=model)  # type: ignore[attr-defined]
sys.modules["sentence_transformers"] = fake_library
api = importlib.import_module("embeddings_api")


class EmbeddingServiceTests(unittest.TestCase):
    def test_health_and_singleton_model_dimension(self):
        self.assertEqual(api.salud(), {"ok": True, "modelo": "intfloat/multilingual-e5-small", "dimension": 384})
        fake_library.SentenceTransformer.assert_called_once_with("intfloat/multilingual-e5-small")  # type: ignore[attr-defined]

    def test_e5_intents_trim_and_normalize(self):
        for intent in ("query", "passage"):
            api.embed(api.SolicitudEmbedding(texto="  content  ", tipo=intent))
            model.encode.assert_called_with(f"{intent}: content", normalize_embeddings=True)

    def test_empty_and_non_finite_vectors_fail(self):
        from fastapi import HTTPException
        with self.assertRaises(HTTPException): api.embed(api.SolicitudEmbedding(texto="  "))
        model.encode.return_value = FakeVector([float("nan")] * 384)
        with self.assertRaises(HTTPException): api.embed(api.SolicitudEmbedding(texto="content"))


if __name__ == "__main__": unittest.main()
