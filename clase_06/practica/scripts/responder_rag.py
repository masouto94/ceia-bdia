#!/usr/bin/env python3
"""
Demuestra el ciclo completo de RAG: recuperación con pgvector + generación
con un LLM externo vía OpenRouter (https://openrouter.ai).

Esto es una EXTENSIÓN fuera del alcance del mockup de Clase 6: el mockup se
detiene en la recuperación ("la generación del texto ocurre después de la
recuperación" — Sección 6, slide 41). Este script muestra dónde termina la
responsabilidad de la base de datos y dónde empieza la del LLM: PostgreSQL
recupera los fragmentos más relevantes; el LLM sólo redacta una respuesta
a partir de ese contexto, sin acceso directo a la base.

Requiere una API key de OpenRouter (gratis para crear cuenta, el uso del
modelo puede tener costo según cuál elijas): https://openrouter.ai/keys

Uso:
    python3 responder_rag.py --consulta-id CON-01
    python3 responder_rag.py --pregunta "¿Por qué se demoran los registros?"
    python3 responder_rag.py --consulta-id CON-05 --top-k 3 --modelo openai/gpt-4o-mini

Variables de entorno:
    OPENROUTER_API_KEY   (obligatoria)
    OPENROUTER_MODEL     (opcional; ver catálogo en https://openrouter.ai/models)
    POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
    MODELO_EMBEDDING     (debe ser el mismo modelo usado al cargar los datos)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import psycopg2
import requests
from sentence_transformers import SentenceTransformer

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generar_volumen import MODELO_EMBEDDING, prefijo_consulta  # noqa: E402

MODELO_EMBEDDING_POR_DEFECTO = MODELO_EMBEDDING
MODELO_LLM_POR_DEFECTO = "openai/gpt-4o-mini"  # cambiar según catálogo de OpenRouter
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

PROMPT_SISTEMA = """Sos un asistente que responde preguntas sobre la plataforma de \
experimentos de IA de la organización, usando EXCLUSIVAMENTE el contexto que se te \
provee a continuación. No inventes información que no esté en el contexto. Si el \
contexto no alcanza para responder, decilo explícitamente en vez de adivinar. \
Cuando cites un dato, indicá entre corchetes el número de fragmento del que sale, \
por ejemplo [fragmento 3]."""


def conectar_bd():
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=os.environ.get("POSTGRES_PORT", "5432"),
        dbname=os.environ.get("POSTGRES_DB", "bdia_vectorial"),
        user=os.environ.get("POSTGRES_USER", "bdia_user"),
        password=os.environ.get("POSTGRES_PASSWORD", ""),
    )


def formatear_vector(valores) -> str:
    return "[" + ",".join(f"{v:.8f}" for v in valores) + "]"


def obtener_pregunta(args) -> str:
    if args.pregunta:
        return args.pregunta
    if args.consulta_id:
        with args.consultas.open(encoding="utf-8") as f:
            consultas = json.load(f)
        for q in consultas:
            if q["consulta_id"] == args.consulta_id:
                return q["consulta"]
        raise SystemExit(f"No existe {args.consulta_id} en {args.consultas}")
    raise SystemExit("Usar --pregunta \"...\" o --consulta-id CON-xx")


def recuperar_fragmentos(cur, vector_str: str, top_k: int) -> list[dict]:
    cur.execute(
        """
        SELECT f.id, f.contenido, f.pagina, d.titulo, d.categoria,
               f.embedding <=> %s::vector AS distancia
        FROM fragmentos f
        JOIN documentos d ON d.id = f.documento_id
        WHERE d.activo = TRUE
        ORDER BY distancia
        LIMIT %s;
        """,
        (vector_str, top_k),
    )
    columnas = ["id", "contenido", "pagina", "titulo", "categoria", "distancia"]
    return [dict(zip(columnas, fila)) for fila in cur.fetchall()]


def armar_contexto(fragmentos: list[dict]) -> str:
    bloques = []
    for i, frag in enumerate(fragmentos, start=1):
        bloques.append(
            f"[fragmento {i}] (documento: \"{frag['titulo']}\", categoría: {frag['categoria']})\n"
            f"{frag['contenido']}"
        )
    return "\n\n".join(bloques)


def llamar_openrouter(pregunta: str, contexto: str, modelo: str, api_key: str) -> dict:
    respuesta = requests.post(
        OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": modelo,
            "messages": [
                {"role": "system", "content": PROMPT_SISTEMA},
                {
                    "role": "user",
                    "content": f"Contexto recuperado de la base de datos:\n\n{contexto}\n\nPregunta: {pregunta}",
                },
            ],
        },
        timeout=60,
    )
    respuesta.raise_for_status()
    return respuesta.json()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--pregunta", help="Pregunta en lenguaje natural.")
    grupo.add_argument("--consulta-id", help="Tomar la pregunta de consultas_prueba.json, ej. CON-01.")
    parser.add_argument(
        "--consultas",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "consultas_prueba.json",
    )
    parser.add_argument("--top-k", type=int, default=5, help="Cantidad de fragmentos a recuperar.")
    parser.add_argument(
        "--modelo",
        default=os.environ.get("OPENROUTER_MODEL", MODELO_LLM_POR_DEFECTO),
        help="Modelo de OpenRouter (ver https://openrouter.ai/models).",
    )
    args = parser.parse_args()

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit(
            "Falta OPENROUTER_API_KEY. Conseguir una en https://openrouter.ai/keys "
            "y exportarla como variable de entorno (o agregarla a .env)."
        )

    pregunta = obtener_pregunta(args)
    modelo_embedding = os.environ.get("MODELO_EMBEDDING", MODELO_EMBEDDING_POR_DEFECTO)

    print(f"Pregunta: {pregunta}\n")

    print(f"Cargando modelo de embeddings: {modelo_embedding}")
    modelo = SentenceTransformer(modelo_embedding)
    vector = modelo.encode(prefijo_consulta(modelo_embedding) + pregunta, normalize_embeddings=True)

    conexion = conectar_bd()
    cur = conexion.cursor()
    try:
        fragmentos = recuperar_fragmentos(cur, formatear_vector(vector), args.top_k)
    finally:
        cur.close()
        conexion.close()

    if not fragmentos:
        raise SystemExit("No se recuperó ningún fragmento. ¿Se cargaron los documentos?")

    print(f"\n--- {len(fragmentos)} fragmentos recuperados (pgvector, distancia coseno) ---")
    for i, frag in enumerate(fragmentos, start=1):
        print(f"[{i}] id={frag['id']} distancia={frag['distancia']:.4f} — {frag['titulo']}")

    contexto = armar_contexto(fragmentos)

    print(f"\nConsultando {args.modelo} en OpenRouter...")
    resultado = llamar_openrouter(pregunta, contexto, args.modelo, api_key)

    respuesta_texto = resultado["choices"][0]["message"]["content"]
    print("\n--- Respuesta del LLM (generada SOLO a partir del contexto recuperado) ---")
    print(respuesta_texto)

    uso = resultado.get("usage")
    if uso:
        print(
            f"\nTokens: {uso.get('prompt_tokens', '?')} entrada + "
            f"{uso.get('completion_tokens', '?')} salida = {uso.get('total_tokens', '?')} total"
        )


if __name__ == "__main__":
    main()
