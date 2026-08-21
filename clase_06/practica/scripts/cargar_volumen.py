#!/usr/bin/env python3
"""
Carga en PostgreSQL el volumen sintético de fragmentos generado por
`generar_volumen.py` (data/fragmentos_volumen.csv), calculando su embedding
con el mismo modelo usado en `cargar_documentos.py`.

Pensado para el Paso 4 de la práctica: con ~10.000 filas cargadas se puede
medir de verdad la diferencia entre búsqueda exacta, HNSW e IVFFlat con
EXPLAIN ANALYZE, en vez de comparar planes sobre un puñado de fragmentos.

Requiere haber corrido antes, en este orden:
    1. scripts/cargar_documentos.py       (crea los 30 documentos base)
    2. scripts/generar_volumen.py         (genera fragmentos_volumen.csv)
    3. scripts/cargar_volumen.py          (este script)

Uso:
    python3 cargar_volumen.py [--csv ../data/fragmentos_volumen.csv] [--lote 500]
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

import psycopg2
from sentence_transformers import SentenceTransformer

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generar_volumen import (  # noqa: E402
    MODELO_EMBEDDING,
    prefijo_pasaje,
    texto_con_contexto,
)

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


def cargar_mapa_ids(ruta: Path) -> dict[str, int]:
    if not ruta.exists():
        raise SystemExit(
            f"No se encontró {ruta}. Correr primero scripts/cargar_documentos.py, "
            "que genera este mapeo al cargar los 30 documentos base."
        )
    with ruta.open(encoding="utf-8") as f:
        return json.load(f)


def leer_fragmentos_csv(ruta: Path) -> list[dict]:
    if not ruta.exists():
        raise SystemExit(
            f"No se encontró {ruta}. Correr primero scripts/generar_volumen.py "
            "para generar el CSV de fragmentos sintéticos."
        )
    with ruta.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def cargar_titulos(ruta: Path) -> dict[str, str]:
    if not ruta.exists():
        raise SystemExit(
            f"No se encontró {ruta}. Necesario para dar contexto (título del "
            "documento) a cada fragmento antes de calcular su embedding."
        )
    with ruta.open(encoding="utf-8") as f:
        documentos = json.load(f)
    return {doc["documento_id"]: doc["titulo"] for doc in documentos}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "fragmentos_volumen.csv",
    )
    parser.add_argument(
        "--mapa",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "documento_id_map.json",
    )
    parser.add_argument(
        "--documentos",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "documentos.json",
        help="Ruta a documentos.json, usado para dar el título como contexto al embeber.",
    )
    parser.add_argument("--lote", type=int, default=500, help="Cantidad de filas por commit.")
    args = parser.parse_args()

    modelo_nombre = os.environ.get("MODELO_EMBEDDING", MODELO_POR_DEFECTO)
    mapa_ids = cargar_mapa_ids(args.mapa)
    titulos = cargar_titulos(args.documentos)
    filas = leer_fragmentos_csv(args.csv)

    print(f"Cargando modelo de embeddings: {modelo_nombre}")
    modelo = SentenceTransformer(modelo_nombre)

    conexion = conectar_bd()
    conexion.autocommit = False
    cur = conexion.cursor()

    try:
        total = 0
        for inicio in range(0, len(filas), args.lote):
            lote = filas[inicio : inicio + args.lote]
            prefijo = prefijo_pasaje(modelo_nombre)
            textos_para_embeber = [
                prefijo + texto_con_contexto(titulos.get(fila["documento_id"], ""), fila["contenido"])
                for fila in lote
            ]
            embeddings = modelo.encode(textos_para_embeber, normalize_embeddings=True)

            for fila, vector in zip(lote, embeddings):
                documento_id = mapa_ids.get(fila["documento_id"])
                if documento_id is None:
                    continue  # fragmento de un documento fuera de los 30 base
                cur.execute(
                    """
                    INSERT INTO fragmentos (
                        documento_id, numero_fragmento, contenido, pagina,
                        embedding, modelo_embedding, fecha_indexacion
                    )
                    VALUES (%s, %s, %s, %s, %s::vector, %s, %s);
                    """,
                    (
                        documento_id,
                        int(fila["numero_fragmento"]),
                        fila["contenido"],
                        int(fila["pagina"]),
                        formatear_vector(vector),
                        fila["modelo_embedding"],
                        fila["fecha_indexacion"],
                    ),
                )
                total += 1
            conexion.commit()
            print(f"  {total}/{len(filas)} fragmentos cargados...")

        print(f"Listo: {total} fragmentos sintéticos cargados desde {args.csv}")

    except Exception:
        conexion.rollback()
        raise
    finally:
        cur.close()
        conexion.close()


if __name__ == "__main__":
    main()
