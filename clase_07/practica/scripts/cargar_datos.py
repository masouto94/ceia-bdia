#!/usr/bin/env python3
"""
Carga tenants, documentos y fragmentos de la practica de Clase 7 en PostgreSQL,
generando el embedding de cada fragmento con un modelo local de
sentence-transformers.

A diferencia de Clase 6, aca cada documento y cada fragmento quedan etiquetados
con un tenant_id: este es el dato que las politicas de Row Level Security (Paso
03) usan para aislar el acceso entre equipos.

Uso:
    python3 cargar_datos.py [--reset]

Variables de entorno esperadas (ver .env.example / docker-compose.yml):
    POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
    MODELO_EMBEDDING (nombre del modelo de sentence-transformers a usar)
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path

import psycopg2
from sentence_transformers import SentenceTransformer

MODELO_POR_DEFECTO = "intfloat/multilingual-e5-small"


def dividir_en_fragmentos(texto: str, oraciones_por_fragmento: int = 6) -> list[str]:
    """Divide el contenido de un documento en fragmentos de pocas oraciones."""
    texto_plano = texto.replace("\n", " ").strip()
    oraciones = re.split(r"(?<=[.!?])\s+", texto_plano)
    oraciones = [o.strip() for o in oraciones if o.strip()]
    fragmentos = []
    for i in range(0, len(oraciones), oraciones_por_fragmento):
        grupo = oraciones[i : i + oraciones_por_fragmento]
        if grupo:
            fragmentos.append(" ".join(grupo))
    return fragmentos or [texto_plano]


def requiere_prefijo_e5(modelo_nombre: str) -> bool:
    return "e5" in modelo_nombre.lower()


def prefijo_pasaje(modelo_nombre: str) -> str:
    return "passage: " if requiere_prefijo_e5(modelo_nombre) else ""


def prefijo_consulta(modelo_nombre: str) -> str:
    return "query: " if requiere_prefijo_e5(modelo_nombre) else ""


def texto_con_contexto(titulo: str, fragmento: str) -> str:
    if not titulo:
        return fragmento
    return f"{titulo}. {fragmento}"


def conectar_bd():
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=os.environ.get("POSTGRES_PORT", "5432"),
        dbname=os.environ.get("POSTGRES_DB", "bdia_rls"),
        user=os.environ.get("POSTGRES_USER", "bdia_admin"),
        password=os.environ.get("POSTGRES_PASSWORD", ""),
    )


def formatear_vector(valores) -> str:
    return "[" + ",".join(f"{v:.8f}" for v in valores) + "]"


def cargar_tenants_csv(ruta: Path) -> list[dict]:
    with ruta.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def cargar_documentos_json(ruta: Path) -> list[dict]:
    with ruta.open(encoding="utf-8") as f:
        return json.load(f)


def resetear_tablas(cur) -> None:
    cur.execute("TRUNCATE fragmentos, documentos, tenants RESTART IDENTITY CASCADE;")


def ya_hay_datos(cur) -> bool:
    cur.execute("SELECT count(*) FROM tenants;")
    return cur.fetchone()[0] > 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tenants",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "tenants.csv",
        help="Ruta a tenants.csv.",
    )
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
        help="Vacia tenants, documentos y fragmentos antes de cargar (TRUNCATE ... RESTART IDENTITY).",
    )
    args = parser.parse_args()

    modelo_nombre = os.environ.get("MODELO_EMBEDDING", MODELO_POR_DEFECTO)
    print(f"Cargando modelo de embeddings: {modelo_nombre} (puede tardar la primera vez)")
    modelo = SentenceTransformer(modelo_nombre)

    tenants = cargar_tenants_csv(args.tenants)
    documentos = cargar_documentos_json(args.documentos)

    conexion = conectar_bd()
    conexion.autocommit = False
    cur = conexion.cursor()

    try:
        if ya_hay_datos(cur):
            if not args.reset:
                print(
                    "La tabla 'tenants' ya tiene filas. No se modifica nada. "
                    "Volver a ejecutar con --reset para vaciar y recargar."
                )
                return
            print("Vaciando tenants, documentos y fragmentos (--reset)...")
            resetear_tablas(cur)
            conexion.commit()

        # 1) Cargar tenants y construir el mapeo codigo (EQ01) -> id real.
        codigo_a_tenant_id: dict[str, int] = {}
        for fila in tenants:
            cur.execute(
                "INSERT INTO tenants (nombre) VALUES (%s) RETURNING id;",
                (fila["nombre"],),
            )
            tenant_id = cur.fetchone()[0]
            codigo_a_tenant_id[fila["codigo"]] = tenant_id

        # 2) Cargar documentos y fragmentos, cada uno con su tenant_id.
        mapa_ids: dict[str, int] = {}
        total_fragmentos = 0

        for doc in documentos:
            tenant_id = codigo_a_tenant_id[doc["equipo_id"]]

            cur.execute(
                """
                INSERT INTO documentos (tenant_id, titulo, categoria, activo)
                VALUES (%s, %s, %s, %s)
                RETURNING id;
                """,
                (tenant_id, doc["titulo"], doc["categoria"], doc["activo"]),
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
                        tenant_id, documento_id, numero_fragmento, contenido, pagina,
                        embedding, modelo_embedding, fecha_indexacion
                    )
                    VALUES (%s, %s, %s, %s, %s, %s::vector, %s, %s);
                    """,
                    (
                        tenant_id,
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

        dimension = getattr(modelo, "get_embedding_dimension", modelo.get_sentence_embedding_dimension)()
        print(f"Tenants cargados: {len(tenants)}")
        print(f"Documentos cargados: {len(documentos)}")
        print(f"Fragmentos cargados: {total_fragmentos}")
        print(f"Modelo de embeddings: {modelo_nombre} (dimension {dimension})")
        print(f"Mapa documento_id -> id real guardado en: {args.mapa_salida}")

    except Exception:
        conexion.rollback()
        raise
    finally:
        cur.close()
        conexion.close()


if __name__ == "__main__":
    main()
