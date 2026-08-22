#!/bin/bash
set -e

cd "$(dirname "$0")"

PURGE=false
if [ "$1" = "--purge" ]; then
    PURGE=true
fi

docker compose down

if [ "$PURGE" = true ]; then
    echo "Borrando datos de PostgreSQL, pgAdmin y MinIO..."
    sudo rm -rf postgres_data/ pgadmin_data/ minio_data/
else
    echo "Borrando datos de PostgreSQL y pgAdmin (se conserva minio_data/; usar --purge para borrarlo)..."
    sudo rm -rf postgres_data/ pgadmin_data/
fi

docker compose up -d
