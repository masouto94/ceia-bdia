#!/bin/sh
# Objetivo: reproducir de extremo a extremo la practica de Clase 7: crear el
#   esquema, cargar datos, mostrar el problema sin RLS, activar RLS, crear el rol
#   de aplicacion con privilegio minimo, y verificar el aislamiento (incluida la
#   busqueda vectorial) conectando como ese rol, no como el administrador.
# Requiere / entradas: ejecutar desde clase_07/practica, Docker/Compose y puertos
#   libres (5435, 8087 por defecto).
# Produce / modifica: levanta la pila, crea tenants/documentos/fragmentos, activa
#   RLS y politicas, crea el rol aplicacion, y corre las verificaciones 05 a 07.
# Resultado esperado: conteos distintos por tenant en el Paso 6, los tres intentos
#   de romper el aislamiento fallan o devuelven 0 filas en el Paso 7, y la busqueda
#   vectorial del Paso 8 no devuelve ninguna fila fuera del tenant activo.
# Guia: automatizacion y recuperacion; la primera enseñanza debe ejecutar los pasos
#   manuales de docs/guia-practica.md, no este atajo. Los Pasos 6, 7 y 8 se conectan
#   deliberadamente con -U aplicacion: conectarlos con el administrador haria que
#   RLS no se aplicara y el resultado seria enganoso.
set -eu

docker compose up -d --build --wait

echo "--- Paso 1: crear tenants, tablas y extension ---"
docker compose exec -T postgres-vectorial sh /scripts/ejecutar_sql.sh /sql/01_crear_extension_y_tablas.sql

echo "--- Paso 2: cargar tenants, documentos y fragmentos (genera embeddings) ---"
docker compose exec -T loader-embeddings python3 scripts/cargar_datos.py

echo "--- Paso 3: mostrar el problema sin RLS ---"
docker compose exec -T postgres-vectorial sh /scripts/ejecutar_sql.sh /sql/02_probar_sin_rls.sql

echo "--- Paso 4: activar RLS y politicas ---"
docker compose exec -T postgres-vectorial sh /scripts/ejecutar_sql.sh /sql/03_activar_rls_y_politicas.sql

echo "--- Paso 5: crear rol de aplicacion con privilegio minimo ---"
docker compose exec -T postgres-vectorial sh /scripts/ejecutar_sql.sh /sql/04_crear_rol_aplicacion.sql

echo "--- Paso 5b: crear rol de solo lectura (para SQL generado por el LLM) ---"
docker compose exec -T postgres-vectorial sh /scripts/ejecutar_sql.sh /sql/08_crear_rol_solo_lectura.sql

echo "--- Paso 6: verificar aislamiento (como aplicacion) ---"
docker compose exec -T postgres-vectorial sh /scripts/ejecutar_sql.sh /sql/05_verificar_aislamiento.sql aplicacion

echo "--- Paso 7: intentar romper el aislamiento (como aplicacion) ---"
docker compose exec -T postgres-vectorial sh /scripts/ejecutar_sql.sh /sql/06_intentar_romper_aislamiento.sql aplicacion

echo "--- Paso 8: busqueda vectorial respetando RLS (como aplicacion) ---"
docker compose exec -T postgres-vectorial sh /scripts/ejecutar_sql.sh /sql/07_busqueda_vectorial_con_rls.sql aplicacion

echo ""
echo "Pipeline completo. Revisar arriba: conteos distintos por tenant (Paso 6),"
echo "intentos fallidos o en 0 filas (Paso 7), y busqueda vectorial sin fugas (Paso 8)."
