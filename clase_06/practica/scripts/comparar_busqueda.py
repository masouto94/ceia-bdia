#!/usr/bin/env python3
"""
Compara, para las mismas preguntas en lenguaje natural, el resultado de una
búsqueda literal (full-text search de PostgreSQL, `tsvector`/`tsquery`) contra
una búsqueda semántica por similitud vectorial (`pgvector`).

Usa las 25 consultas de `data/consultas_prueba.json`: para cada una, muestra
el top 5 de cada estrategia y si el/los documento(s) esperado(s)
(`documentos_relevantes_esperados`) aparecen en cada resultado. El objetivo es
ver en la práctica, no sólo en la teoría, por qué "consultas vectoriales
amplían SQL con un nuevo criterio de ordenamiento" en lugar de reemplazar la
búsqueda por texto.

Uso:
    python3 comparar_busqueda.py                 # corre las 25 consultas
    python3 comparar_busqueda.py --consulta CON-01
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import psycopg2
from sentence_transformers import SentenceTransformer

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generar_volumen import MODELO_EMBEDDING, prefijo_consulta  # noqa: E402

MODELO_POR_DEFECTO = MODELO_EMBEDDING


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


def buscar_semantico(cur, vector_str: str, limite: int) -> list[tuple]:
    cur.execute(
        """
        SELECT f.documento_id, f.contenido
        FROM fragmentos f
        ORDER BY f.embedding <=> %s::vector
        LIMIT %s;
        """,
        (vector_str, limite),
    )
    return cur.fetchall()


def buscar_literal(cur, consulta_texto: str, limite: int) -> list[tuple]:
    # plainto_tsquery conecta todas las palabras de la pregunta con AND: en
    # fragmentos cortos (2-3 oraciones) casi nunca coexisten todas las
    # palabras de una pregunta completa, así que esa forma casi siempre
    # devuelve cero filas y no sirve como punto de comparación. Se convierte
    # a OR (cualquiera de los términos) para imitar una búsqueda por palabras
    # clave real, y se rankea por cuántos términos coinciden (ts_rank).
    cur.execute(
        """
        WITH consulta AS (
            SELECT to_tsquery(
                'spanish',
                regexp_replace(plainto_tsquery('spanish', %s)::text, ' & ', ' | ', 'g')
            ) AS q
        )
        SELECT f.documento_id, f.contenido
        FROM fragmentos f, consulta
        WHERE to_tsvector('spanish', f.contenido) @@ consulta.q
        ORDER BY ts_rank(to_tsvector('spanish', f.contenido), consulta.q) DESC
        LIMIT %s;
        """,
        (consulta_texto, limite),
    )
    return cur.fetchall()


def acierta(resultados: list[tuple], documentos_ids_reales: set[int]) -> bool:
    return any(doc_id in documentos_ids_reales for doc_id, _ in resultados)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--consultas",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "consultas_prueba.json",
    )
    parser.add_argument(
        "--mapa",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "documento_id_map.json",
    )
    parser.add_argument("--consulta", help="Correr sólo un consulta_id puntual, ej. CON-01.")
    parser.add_argument("--limite", type=int, default=5, help="Cantidad de resultados por estrategia.")
    args = parser.parse_args()

    if not args.mapa.exists():
        raise SystemExit(
            f"No se encontró {args.mapa}. Correr primero scripts/cargar_documentos.py."
        )
    mapa_ids: dict[str, int] = json.loads(args.mapa.read_text(encoding="utf-8"))

    with args.consultas.open(encoding="utf-8") as f:
        consultas = json.load(f)
    if args.consulta:
        consultas = [q for q in consultas if q["consulta_id"] == args.consulta]
        if not consultas:
            raise SystemExit(f"No existe la consulta {args.consulta} en {args.consultas}")

    modelo_nombre = os.environ.get("MODELO_EMBEDDING", MODELO_POR_DEFECTO)
    print(f"Cargando modelo de embeddings: {modelo_nombre}")
    modelo = SentenceTransformer(modelo_nombre)

    conexion = conectar_bd()
    cur = conexion.cursor()

    aciertos_semantico = 0
    aciertos_literal = 0

    try:
        for q in consultas:
            esperados_ids = {
                mapa_ids[d] for d in q["documentos_relevantes_esperados"] if d in mapa_ids
            }

            vector = modelo.encode(prefijo_consulta(modelo_nombre) + q["consulta"], normalize_embeddings=True)
            resultado_semantico = buscar_semantico(cur, formatear_vector(vector), args.limite)
            resultado_literal = buscar_literal(cur, q["consulta"], args.limite)

            acierto_sem = acierta(resultado_semantico, esperados_ids)
            acierto_lit = acierta(resultado_literal, esperados_ids)
            aciertos_semantico += acierto_sem
            aciertos_literal += acierto_lit

            print(f"\n=== {q['consulta_id']} — {q['consulta']}")
            print(f"    esperados: {q['documentos_relevantes_esperados']}")
            print(f"    semántica -> {'OK' if acierto_sem else 'NO encontró el esperado'} "
                  f"({len(resultado_semantico)} resultados)")
            print(f"    literal   -> {'OK' if acierto_lit else 'NO encontró el esperado'} "
                  f"({len(resultado_literal)} resultados)")

        total = len(consultas)
        print(f"\n--- Resumen ---")
        print(f"Consultas evaluadas: {total}")
        print(f"Aciertos búsqueda semántica: {aciertos_semantico}/{total}")
        print(f"Aciertos búsqueda literal:   {aciertos_literal}/{total}")

    finally:
        cur.close()
        conexion.close()


if __name__ == "__main__":
    main()
