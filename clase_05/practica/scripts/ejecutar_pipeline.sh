#!/bin/sh
# Objetivo: reproducir de extremo a extremo Bronze -> Silver -> Gold con controles finales.
# Requiere / entradas: ejecutar desde clase_05/practica, Docker/Compose y puertos disponibles.
# Produce / modifica: levanta la pila y reconstruye salidas Silver, calidad y Gold.
# Resultado esperado: 32 hechos, 11 filas puente; lotes con balances 84/0 y 9/16.
# Guía: automatización y recuperación; la primera enseñanza debe ejecutar los pasos manuales.
# Seguridad: requiere que la UI local del estudiante esté cerrada; limpia derivados y hace full reload de Gold.
set -eu

# Frontera 1, infraestructura y entrada: servicios saludables y ambos lotes Bronze completos.
# La UI ahora corre como proceso `duckdb` en la máquina del estudiante, fuera de este stack:
# cerrala vos (Ctrl+C en su terminal) antes de reprocesar; si sigue abierta, DuckDB rechaza
# el lock del archivo y este comando falla con ese motivo.
docker compose up -d --wait
docker compose exec -T minio-admin sh /scripts/cargar_bronze.sh lote_01_inicial
docker compose exec -T minio-admin sh /scripts/cargar_bronze.sh lote_02_nuevos
# Frontera 2, diagnóstico y transformación: perfila antes de limpiar sólo salidas derivadas.
docker compose exec -T duckdb-transformer sh /scripts/ejecutar_sql.sh /sql/01_perfilar_bronze.sql
docker compose exec -T minio-admin sh /scripts/limpiar_salidas.sh
docker compose exec -T duckdb-transformer sh /scripts/ejecutar_sql.sh /sql/02_procesar_silver.sql
docker compose exec -T duckdb-transformer sh /scripts/ejecutar_sql.sh /sql/03_publicar_silver.sql
# Frontera 3, publicación: Gold se confirma sólo tras sus verificaciones transaccionales.
docker compose exec -T duckdb-transformer sh /scripts/ejecutar_sql.sh /sql/04_cargar_gold.sql
# Los conteos son específicos del fixture y convierten cualquier desvío en fallo del pipeline.
docker compose exec -T postgres-warehouse sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /dev/stdin' < postgres/03_verificar_carga.sql
