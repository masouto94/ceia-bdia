#!/bin/sh
# Objetivo: reiniciar exclusivamente el estado de datos de la practica de Clase 7
#   (tenants, documentos, fragmentos) y recargarlo desde cero.
# Requiere / entradas: ejecutar desde clase_07/practica, con la pila levantada
#   (docker compose up -d).
# Produce / modifica: TRUNCATE de tenants, documentos y fragmentos (con CASCADE y
#   RESTART IDENTITY); vuelve a correr scripts/cargar_datos.py.
# Resultado esperado: mismo estado de datos que una carga inicial, con los ids
#   reiniciados desde 1.
# Guia: reinicio de datos, no de infraestructura. No toca politicas de RLS, roles
#   ni la estructura de tablas: solo vacia y recarga las filas. Para volver a un
#   estado completamente vacio (sin estructura ni politicas), correr
#   `docker compose down -v` y repetir el pipeline desde el Paso 01.
set -eu

echo "Vaciando tenants, documentos y fragmentos..."
docker compose exec -T postgres-vectorial sh -c \
    'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "TRUNCATE fragmentos, documentos, tenants RESTART IDENTITY CASCADE;"'

echo "Recargando datos..."
docker compose exec -T loader-embeddings python3 scripts/cargar_datos.py

echo "Practica de Clase 7 reiniciada."
