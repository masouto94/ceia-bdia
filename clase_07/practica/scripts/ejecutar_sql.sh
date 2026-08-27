#!/bin/sh
# Objetivo: ejecutar un archivo SQL de la practica contra postgres-vectorial, con un
#   rol de conexion configurable.
# Requiere / entradas: ruta /sql/NN_archivo.sql (montada desde ./postgres) y las
#   variables de conexion del servicio (POSTGRES_DB, POSTGRES_USER).
# Produce / modifica: lo que el archivo SQL indicado defina.
# Resultado esperado: salida de psql para ese archivo en la terminal.
# Guia: los Pasos 01, 02, 03 y 04 deben correr con el usuario administrador
#   ($POSTGRES_USER, por defecto). Los Pasos 05, 06 y 07 deben correr con el rol
#   aplicacion: pasarlo como segundo argumento. Correrlos con el administrador
#   haria que RLS no se aplicara (ver postgres/04_crear_rol_aplicacion.sql) y la
#   practica mostraria un falso resultado de aislamiento.
set -eu

archivo="${1:?Uso: ejecutar_sql.sh /sql/NN_archivo.sql [usuario]}"
usuario="${2:-$POSTGRES_USER}"

psql -U "$usuario" -d "$POSTGRES_DB" -f "$archivo"
