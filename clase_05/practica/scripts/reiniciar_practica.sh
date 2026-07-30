#!/bin/sh
# Objetivo: devolver exclusivamente la práctica de Clase 5 a un estado inicial vacío.
# Requiere / entradas: ejecutar desde clase_05/practica, donde Compose resuelve su proyecto.
# Produce / modifica: elimina contenedores, red y volúmenes del proyecto bdia_clase_05,
#   y también ./duckdb_data (bind mount, fuera del alcance de "compose down -v").
# Resultado esperado: próxima ejecución recrea infraestructura, Bronze, DuckDB y Warehouse.
# Guía: recuperación determinista ante carga parcial; no es un paso normal de enseñanza.
# Seguridad: DESTRUCTIVO; pierde todo estado persistido de esta práctica, no datos fuente.
set -eu

# El directorio de trabajo define qué archivo y nombre de proyecto Compose administra.
docker compose down -v --remove-orphans
# duckdb_data es un bind mount, no un volumen Docker: "down -v" no lo toca.
rm -rf ./duckdb_data
echo "Se eliminaron únicamente contenedores, red, volúmenes y duckdb_data del proyecto bdia_clase_05."
