#!/usr/bin/env python3
"""
Carga los 30 documentos principales de la práctica de Clase 6 en PostgreSQL,
generando el embedding de cada fragmento con un modelo local de
sentence-transformers (Paso 2 de la práctica guiada).

Este script es el único lugar donde se generan embeddings a partir del texto:
el mismo modelo se usa acá para indexar y en `comparar_busqueda.py` para
consultar, porque los vectores de dos modelos distintos no son comparables
entre sí.

Uso:
    python3 cargar_documentos.py [--reset]

Variables de entorno esperadas (ver .env.example / docker-compose.yml):
    POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
    MODELO_EMBEDDING (nombre del modelo de sentence-transformers a usar)
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
from generar_volumen import (  # noqa: E402
    MODELO_EMBEDDING,
    dividir_en_fragmentos,
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


def cargar_documentos_json(ruta: Path) -> list[dict]:
    with ruta.open(encoding="utf-8") as f:
        return json.load(f)


def formatear_vector(valores) -> str:
    return "[" + ",".join(f"{v:.8f}" for v in valores) + "]"


def resetear_tablas(cur) -> None:
    cur.execute("TRUNCATE fragmentos, documentos RESTART IDENTITY CASCADE;")


def ya_hay_datos(cur) -> bool:
    cur.execute("SELECT count(*) FROM documentos;")
    return cur.fetchone()[0] > 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--documentos",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "documentos.json",
        help="Ruta a documentos.json.",
    )
    parser.add_argument(
        "--mapa-salida",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "documento_id_map.json",
        help="Ruta donde guardar el mapeo DOC-xxx -> id real de PostgreSQL.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Vacía documentos y fragmentos antes de cargar (TRUNCATE ... RESTART IDENTITY).",
    )
    args = parser.parse_args()

    modelo_nombre = os.environ.get("MODELO_EMBEDDING", MODELO_POR_DEFECTO)
    print(f"Cargando modelo de embeddings: {modelo_nombre} (puede tardar la primera vez)")
    modelo = SentenceTransformer(modelo_nombre)

    documentos = cargar_documentos_json(args.documentos)

    conexion = conectar_bd()
    conexion.autocommit = False
    cur = conexion.cursor()

    try:
        if ya_hay_datos(cur):
            if not args.reset:
                print(
                    "La tabla 'documentos' ya tiene filas. No se modifica nada. "
                    "Volver a ejecutar con --reset para vaciar y recargar."
                )
                return
            print("Vaciando documentos y fragmentos (--reset)...")
            resetear_tablas(cur)
            conexion.commit()

        mapa_ids: dict[str, int] = {}
        total_fragmentos = 0

        for doc in documentos:
            cur.execute(
                """
                INSERT INTO documentos (titulo, categoria, activo)
                VALUES (%s, %s, %s)
                RETURNING id;
                """,
                (doc["titulo"], doc["categoria"], doc["activo"]),
            )
            documento_id = cur.fetchone()[0]
            mapa_ids[doc["documento_id"]] = documento_id

            textos = dividir_en_fragmentos(doc["contenido"])
            prefijo = prefijo_pasaje(modelo_nombre)
            textos_para_embeber = [
                prefijo + texto_con_contexto(doc["titulo"], t) for t in textos
            ]
            embeddings = modelo.encode(textos_para_embeber, normalize_embeddings=True)

            for indice, (texto, vector) in enumerate(zip(textos, embeddings), start=1):
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
                        indice,
                        texto,
                        indice,
                        formatear_vector(vector),
                        modelo_nombre,
                        doc["fecha"],
                    ),
                )
                total_fragmentos += 1

        conexion.commit()

        args.mapa_salida.parent.mkdir(parents=True, exist_ok=True)
        with args.mapa_salida.open("w", encoding="utf-8") as f:
            json.dump(mapa_ids, f, ensure_ascii=False, indent=2)

        print(f"Documentos cargados: {len(documentos)}")
        print(f"Fragmentos cargados: {total_fragmentos}")
        dimension = getattr(modelo, "get_embedding_dimension", modelo.get_sentence_embedding_dimension)()
        print(f"Modelo de embeddings: {modelo_nombre} (dimensión {dimension})")
        print(f"Mapa documento_id -> id real guardado en: {args.mapa_salida}")

    except Exception:
        conexion.rollback()
        raise
    finally:
        cur.close()
        conexion.close()


if __name__ == "__main__":
    main()
