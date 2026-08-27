"""Target-owned E5 embedding service adapted from the Clase 7 practice."""
# pyright: reportMissingImports=false
from __future__ import annotations

import math
import os
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

MODELO_NOMBRE = os.environ.get("MODELO_EMBEDDING", "intfloat/multilingual-e5-small")
app = FastAPI(title="Embeddings API", version="1.0")
_modelo = SentenceTransformer(MODELO_NOMBRE)
_dimension = _modelo.get_sentence_embedding_dimension()


class SolicitudEmbedding(BaseModel):
    texto: str
    tipo: Literal["query", "passage"] = "query"


@app.get("/salud")
def salud() -> dict:
    return {"ok": True, "modelo": MODELO_NOMBRE, "dimension": _dimension}


@app.post("/embed")
def embed(solicitud: SolicitudEmbedding) -> dict:
    texto = solicitud.texto.strip()
    if not texto:
        raise HTTPException(400, "El campo 'texto' no puede estar vacío.")
    prefix = f"{solicitud.tipo}: " if "e5" in MODELO_NOMBRE.lower() else ""
    encoded = _modelo.encode(prefix + texto, normalize_embeddings=True)
    try:
        vector = [float(value) for value in encoded.tolist()]
    except (TypeError, ValueError, AttributeError) as exc:
        raise HTTPException(503, "El modelo devolvió un vector inválido.") from exc
    if len(vector) != _dimension or not all(math.isfinite(value) for value in vector):
        raise HTTPException(503, "El modelo devolvió un vector inválido.")
    return {"vector": vector, "dimension": _dimension, "modelo": MODELO_NOMBRE}
