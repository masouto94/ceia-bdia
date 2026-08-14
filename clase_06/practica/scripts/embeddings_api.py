#!/usr/bin/env python3
"""
Microservicio HTTP que calcula embeddings con el mismo modelo local usado
para cargar la base (scripts/cargar_documentos.py). Existe para que la
interfaz web (Next.js) pueda pedir el vector de una pregunta sin tener que
correr sentence-transformers en Node.

El modelo se carga una única vez al arrancar el proceso, no en cada request
— importante para que la demo en clase responda rápido.

Endpoint:
    POST /embed
    body: {"texto": "...", "tipo": "query" | "passage"}
    respuesta: {"vector": [...], "dimension": 384, "modelo": "..."}

    GET /salud
    respuesta: {"ok": true, "modelo": "...", "dimension": 384}

Uso local (sin Docker):
    uvicorn embeddings_api:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generar_volumen import MODELO_EMBEDDING, prefijo_consulta, prefijo_pasaje  # noqa: E402

MODELO_NOMBRE = os.environ.get("MODELO_EMBEDDING", MODELO_EMBEDDING)

app = FastAPI(title="Embeddings API - Clase 6", version="1.0")

print(f"[embeddings_api] Cargando modelo: {MODELO_NOMBRE}", flush=True)
_modelo = SentenceTransformer(MODELO_NOMBRE)
_dimension = _modelo.get_sentence_embedding_dimension()
print(f"[embeddings_api] Modelo listo (dimensión {_dimension})", flush=True)


class SolicitudEmbedding(BaseModel):
    texto: str
    tipo: Literal["query", "passage"] = "query"


@app.get("/salud")
def salud():
    return {"ok": True, "modelo": MODELO_NOMBRE, "dimension": _dimension}


@app.post("/embed")
def embed(solicitud: SolicitudEmbedding):
    texto = solicitud.texto.strip()
    if not texto:
        raise HTTPException(status_code=400, detail="El campo 'texto' no puede estar vacío.")

    prefijo = prefijo_consulta(MODELO_NOMBRE) if solicitud.tipo == "query" else prefijo_pasaje(MODELO_NOMBRE)
    vector = _modelo.encode(prefijo + texto, normalize_embeddings=True)

    return {
        "vector": vector.tolist(),
        "dimension": _dimension,
        "modelo": MODELO_NOMBRE,
    }
