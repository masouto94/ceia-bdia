#!/bin/sh
# Objetivo: copiar un lote permitido a Bronze sin sobrescribir su evidencia original.
# Requiere / entradas: nombre de lote, ocho CSV montados y credenciales de MinIO.
# Produce / modifica: bucket lakehouse y la partición Bronze del lote solicitado.
# Resultado esperado: ocho objetos idénticos al origen o confirmación de carga ya completa.
# Guía: carga manual de cada lote; el pipeline la automatiza antes del perfilado.
# Seguridad: Bronze es inmutable; una carga parcial se rechaza y exige reinicio controlado.
set -eu

lote="${1:?Uso: cargar_bronze.sh <lote_01_inicial|lote_02_nuevos>}"
origen="/data/practica/${lote}"
destino="local/lakehouse/bronze/lote=${lote}"

case "$lote" in
  lote_01_inicial|lote_02_nuevos) ;;
  *) echo "Lote no permitido: $lote" >&2; exit 1 ;;
esac

mc alias set local http://minio-storage:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null
mc mb --ignore-existing local/lakehouse >/dev/null

existentes="$(mc ls "$destino/" 2>/dev/null | wc -l | tr -d ' ')"
# Ocho es un conteo propio del fixture. Una partición completa se conserva sin reescribir;
# cualquier otro volumen indica estado parcial y evita mezclar una nueva carga con residuos.
if [ "$existentes" = "8" ]; then
  echo "Bronze ya contiene $lote (8 objetos); no se modifica."
  exit 0
fi
if [ "$existentes" != "0" ]; then
  echo "Carga parcial detectada en $destino ($existentes objetos). Ejecutá el reinicio determinista." >&2
  exit 1
fi

mc cp --recursive "$origen/" "$destino/" >/dev/null
objetos="$(mc ls "$destino/" | wc -l | tr -d ' ')"
[ "$objetos" = "8" ] || { echo "Se esperaban 8 objetos y se cargaron $objetos" >&2; exit 1; }
echo "Bronze: $lote cargado correctamente (8 archivos cargados)."
