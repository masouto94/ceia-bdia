#!/usr/bin/env python3
"""
Genera un volumen sintético de fragmentos a partir de los 30 documentos
principales de la práctica de Clase 6 (Bases de Datos Vectoriales,
Concurrencia y Escalabilidad).

Objetivo: producir un CSV de ~10.000 filas de "fragmentos" para poder
probar, en PostgreSQL + pgvector, el comportamiento de índices HNSW e
IVFFlat, EXPLAIN ANALYZE y búsqueda exacta a escala.

Las columnas de salida corresponden 1:1 con la tabla `fragmentos` del
esquema de la práctica (documento_id, numero_fragmento, contenido, pagina,
modelo_embedding, fecha_indexacion). Este script NO genera embeddings:
el campo `contenido` de cada fila queda listo para que un paso posterior
calcule y guarde el vector correspondiente.

Uso:
    python3 generar_volumen.py \
        --documentos ../data/documentos.json \
        --salida ../data/fragmentos_volumen.csv \
        --objetivo 10000
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
from pathlib import Path

MODELO_EMBEDDING = "intfloat/multilingual-e5-small"


def requiere_prefijo_e5(modelo_nombre: str) -> bool:
    """Los modelos de la familia E5 se entrenan para *retrieval* asimétrico
    (pregunta -> pasaje) y esperan los prefijos "query: "/"passage: " en el
    texto antes de calcular el embedding. Sin ellos, el modelo funciona pero
    con peor calidad de ranking. Otros modelos (por ejemplo los de
    paraphrase-*) no los necesitan."""
    return "e5" in modelo_nombre.lower()


def prefijo_pasaje(modelo_nombre: str) -> str:
    return "passage: " if requiere_prefijo_e5(modelo_nombre) else ""


def prefijo_consulta(modelo_nombre: str) -> str:
    return "query: " if requiere_prefijo_e5(modelo_nombre) else ""


def texto_con_contexto(titulo: str, fragmento: str) -> str:
    """Antepone el título del documento al fragmento antes de calcular el
    embedding (no se guarda así en `contenido`, sólo se usa para el vector).

    Muchos fragmentos empiezan con una apertura genérica compartida entre
    documentos distintos (p. ej. "Equipo de X (EQXX) documenta/informa...");
    sin el título, esa apertura repetida diluye la señal semántica del
    fragmento. Dar el título como contexto es la técnica de "contextual
    retrieval": ayuda a que el embedding capture de qué trata el fragmento
    incluso cuando el propio texto del fragmento es corto o genérico.
    """
    if not titulo:
        return fragmento
    return f"{titulo}. {fragmento}"

# Sustituciones controladas: cada clave puede reemplazarse por cualquiera
# de sus variantes sin cambiar el significado de la oración. Se usan para
# generar redacciones alternativas de un mismo fragmento, no para inventar
# contenido nuevo.
SINONIMOS = {
    "informa": ["reporta", "documenta", "deja constancia de que", "comunica"],
    "detectó": ["identificó", "encontró", "observó", "constató"],
    "se recomienda": ["se sugiere", "se propone", "conviene", "resulta aconsejable"],
    "equipo": ["área", "grupo de trabajo"],
    "problema": ["inconveniente", "dificultad", "situación"],
    "incremento": ["aumento", "crecimiento"],
    "reduce": ["disminuye", "baja", "recorta"],
    "actualmente": ["hoy", "en la actualidad", "por el momento"],
    "posteriormente": ["más adelante", "luego", "después"],
    "verificó": ["confirmó", "constató", "comprobó"],
    "genera": ["produce", "provoca", "ocasiona"],
    "permite": ["habilita", "posibilita"],
}

PATRON_SINONIMOS = re.compile(
    "|".join(re.escape(palabra) for palabra in SINONIMOS), flags=re.IGNORECASE
)


def dividir_en_fragmentos(texto: str, oraciones_por_fragmento: int = 6) -> list[str]:
    """Divide el contenido de un documento en fragmentos de pocas oraciones.

    Se corta por punto seguido de espacio o salto de línea, agrupando de a
    `oraciones_por_fragmento` oraciones por fragmento. Es una segmentación
    simple a propósito: el objetivo de este script es volumen y variación
    controlada, no un chunker de producción.
    """
    texto_plano = texto.replace("\n", " ").strip()
    oraciones = re.split(r"(?<=[.!?])\s+", texto_plano)
    oraciones = [o.strip() for o in oraciones if o.strip()]

    fragmentos = []
    for i in range(0, len(oraciones), oraciones_por_fragmento):
        grupo = oraciones[i : i + oraciones_por_fragmento]
        if grupo:
            fragmentos.append(" ".join(grupo))
    return fragmentos or [texto_plano]


def parafrasear(texto: str, rng: random.Random) -> str:
    """Aplica sustituciones léxicas controladas para variar la redacción
    sin alterar el significado del fragmento."""

    def reemplazar(match: re.Match) -> str:
        original = match.group(0)
        clave = original.lower()
        variantes = SINONIMOS.get(clave)
        if not variantes:
            return original
        elegido = rng.choice(variantes)
        return elegido.capitalize() if original[0].isupper() else elegido

    return PATRON_SINONIMOS.sub(reemplazar, texto)


def cargar_documentos(ruta: Path) -> list[dict]:
    with ruta.open(encoding="utf-8") as f:
        return json.load(f)


def generar_fragmentos_base(documentos: list[dict]) -> list[dict]:
    """Genera los fragmentos originales (sin parafrasear) de cada documento,
    con las columnas físicas de la tabla `fragmentos`."""
    fragmentos = []
    for doc in documentos:
        trozos = dividir_en_fragmentos(doc["contenido"])
        for indice, trozo in enumerate(trozos, start=1):
            fragmentos.append(
                {
                    "fragmento_id": f"{doc['documento_id']}-F{indice:02d}",
                    "documento_id": doc["documento_id"],
                    "numero_fragmento": indice,
                    "contenido": trozo,
                    "pagina": indice,
                    "modelo_embedding": MODELO_EMBEDDING,
                    "fecha_indexacion": doc["fecha"],
                    "es_original": True,
                    "variante": 0,
                }
            )
    return fragmentos


def expandir_con_variantes(
    fragmentos_base: list[dict], objetivo: int, semilla: int
) -> list[dict]:
    """Multiplica los fragmentos base generando variantes parafraseadas
    hasta alcanzar (aproximadamente) `objetivo` filas totales, conservando
    siempre los fragmentos originales sin modificar."""
    rng = random.Random(semilla)
    resultado = list(fragmentos_base)

    if objetivo <= len(resultado):
        return resultado

    faltan = objetivo - len(resultado)
    variantes_por_fragmento = max(1, faltan // len(fragmentos_base) + 1)

    for base in fragmentos_base:
        for variante in range(1, variantes_por_fragmento + 1):
            if len(resultado) >= objetivo:
                break
            nuevo = dict(base)
            nuevo["fragmento_id"] = f"{base['fragmento_id']}-V{variante:03d}"
            nuevo["es_original"] = False
            nuevo["variante"] = variante
            nuevo["contenido"] = parafrasear(base["contenido"], rng)
            resultado.append(nuevo)
        if len(resultado) >= objetivo:
            break

    return resultado[:objetivo] if len(resultado) > objetivo else resultado


def escribir_csv(fragmentos: list[dict], ruta_salida: Path) -> None:
    campos = [
        "fragmento_id",
        "documento_id",
        "numero_fragmento",
        "contenido",
        "pagina",
        "modelo_embedding",
        "fecha_indexacion",
        "es_original",
        "variante",
    ]
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    with ruta_salida.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=campos, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for frag in fragmentos:
            fila = {campo: ("" if frag[campo] is None else frag[campo]) for campo in campos}
            writer.writerow(fila)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--documentos",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "documentos.json",
        help="Ruta al documentos.json con los 30 documentos principales.",
    )
    parser.add_argument(
        "--salida",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "fragmentos_volumen.csv",
        help="Ruta del CSV de fragmentos sintéticos a generar.",
    )
    parser.add_argument(
        "--objetivo",
        type=int,
        default=10000,
        help="Cantidad aproximada de fragmentos a generar (default: 10000).",
    )
    parser.add_argument(
        "--semilla",
        type=int,
        default=42,
        help="Semilla del generador aleatorio, para reproducibilidad.",
    )
    args = parser.parse_args()

    documentos = cargar_documentos(args.documentos)
    fragmentos_base = generar_fragmentos_base(documentos)
    fragmentos = expandir_con_variantes(fragmentos_base, args.objetivo, args.semilla)
    escribir_csv(fragmentos, args.salida)

    originales = sum(1 for f in fragmentos if f["es_original"])
    variantes = len(fragmentos) - originales
    print(f"Documentos de origen: {len(documentos)}")
    print(f"Fragmentos base (originales): {originales}")
    print(f"Variantes sintéticas generadas: {variantes}")
    print(f"Total de fragmentos escritos: {len(fragmentos)}")
    print(f"Archivo: {args.salida}")
    print(
        "Nota: el campo 'contenido' queda listo para que un paso posterior "
        "genere el embedding (columna 'embedding VECTOR(384)'); este script "
        "no calcula ni guarda vectores."
    )


if __name__ == "__main__":
    main()
