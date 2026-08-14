#!/bin/sh
# Objetivo: reproducir de extremo a extremo la práctica base (Pasos 1 a 4, sin volumen
#   sintético ni ejercicio de reindexación, que quedan como pasos manuales aparte).
# Requiere / entradas: ejecutar desde clase_06/practica, Docker/Compose y puertos libres.
# Produce / modifica: levanta la pila, crea la estructura, carga 30 documentos con sus
#   embeddings, crea los índices y corre EXPLAIN ANALYZE antes/después.
# Resultado esperado: 30 documentos (1 inactivo), fragmentos con embedding de 384
#   dimensiones, y dos EXPLAIN ANALYZE para comparar planes.
# Guía: automatización y recuperación; la primera enseñanza debe ejecutar los pasos
#   manuales del docs/guia-practica.md, no este atajo.
set -eu

docker compose up -d --build --wait

echo "--- Paso 1: crear extensión y tablas ---"
docker compose exec -T postgres-vectorial sh /scripts/ejecutar_sql.sh /sql/01_crear_extension_y_tablas.sql

echo "--- Paso 2: cargar documentos y generar embeddings ---"
docker compose exec -T loader-embeddings python3 scripts/cargar_documentos.py

echo "--- Paso 3: consultas por similitud (ejemplo) ---"
docker compose exec -T postgres-vectorial sh /scripts/ejecutar_sql.sh /sql/02_consultas_similitud.sql

echo "--- Paso 4a: EXPLAIN ANALYZE sin índice ---"
docker compose exec -T postgres-vectorial sh /scripts/ejecutar_sql.sh /sql/03_explain_sin_indice.sql

echo "--- Paso 4b: crear índices HNSW e IVFFlat ---"
docker compose exec -T postgres-vectorial sh /scripts/ejecutar_sql.sh /sql/04_crear_indices.sql

echo "--- Paso 4c: EXPLAIN ANALYZE con índices ---"
docker compose exec -T postgres-vectorial sh /scripts/ejecutar_sql.sh /sql/05_explain_con_indice.sql

echo "--- Verificación de carga ---"
docker compose exec -T postgres-vectorial sh /scripts/ejecutar_sql.sh /sql/07_verificar_carga.sql

echo ""
echo "Pipeline base completo. Pasos manuales opcionales:"
echo "  - Volumen sintético (10k fragmentos):"
echo "      docker compose exec loader-embeddings python3 scripts/generar_volumen.py"
echo "      docker compose exec loader-embeddings python3 scripts/cargar_volumen.py"
echo "  - Comparar búsqueda literal vs semántica:"
echo "      docker compose exec loader-embeddings python3 scripts/comparar_busqueda.py"
echo "  - Reindexación/actualización transaccional: ver postgres/06_actualizacion_reindexacion.sql"
