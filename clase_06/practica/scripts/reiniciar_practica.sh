#!/bin/sh
# Objetivo: devolver exclusivamente la práctica de Clase 6 a un estado inicial vacío.
# Requiere / entradas: ejecutar desde clase_06/practica, donde Compose resuelve su proyecto.
# Produce / modifica: elimina contenedores, red y volúmenes del proyecto bdia_clase_06
#   (incluye el caché del modelo de embeddings, que se vuelve a descargar la próxima vez).
# Resultado esperado: próxima ejecución recrea la base vacía y el modelo se redescarga.
# Guía: recuperación determinista; no es un paso normal de enseñanza.
# Seguridad: DESTRUCTIVO; pierde todo estado persistido de esta práctica, no el dataset fuente.
set -eu

docker compose down -v --remove-orphans
rm -f ./data/fragmentos_volumen.csv ./data/documento_id_map.json
echo "Se eliminaron contenedores, red, volúmenes y archivos generados del proyecto bdia_clase_06."
echo "El dataset fuente (data/documentos.json, data/consultas_prueba.json, etc.) no se tocó."
