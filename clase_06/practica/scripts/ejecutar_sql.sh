#!/bin/sh
# Objetivo: ejecutar un archivo SQL de la práctica contra postgres-vectorial.
# Requiere / entradas: ruta /sql/NN_archivo.sql (montada desde ./postgres) y las
#   variables de conexión del servicio (POSTGRES_DB, POSTGRES_USER).
# Produce / modifica: lo que el archivo SQL indicado defina.
# Resultado esperado: salida de psql para ese archivo en la terminal.
# Guía: mismo helper para cada paso manual de la práctica (crear estructura,
#   consultas, EXPLAIN ANALYZE, índices, reindexación, verificación).
set -eu

archivo="${1:?Uso: ejecutar_sql.sh /sql/NN_archivo.sql}"

psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f "$archivo"
