#!/bin/sh
# Objetivo: retirar derivados publicados antes de un reproceso idempotente.
# Requiere / entradas: MinIO disponible y credenciales administrativas.
# Produce / modifica: elimina únicamente prefijos silver/ y calidad/ del lakehouse.
# Resultado esperado: destino derivado vacío y Bronze preservado sin cambios.
# Guía: preparación previa a publicar Silver; el pipeline la ejecuta automáticamente.
# Seguridad: operación destructiva acotada a derivados reconstruibles; nunca borra Bronze.
set -eu

mc alias set local http://minio-storage:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null
# Silver y calidad se regeneran desde Bronze; conservar objetos previos mezclaría ejecuciones.
mc rm --recursive --force local/lakehouse/silver/ >/dev/null 2>&1 || true
mc rm --recursive --force local/lakehouse/calidad/ >/dev/null 2>&1 || true
echo "Salidas Silver y calidad preparadas para el reproceso. Bronze no fue modificado."
