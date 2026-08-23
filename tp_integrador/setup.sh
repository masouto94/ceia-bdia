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

# Cargando seed media en MinIO
MINIO_URL="http://localhost:9000"
MINIO_USER="admin"
MINIO_PASS="12345678"
MINIO_BUCKET="assets"

echo "Esperando a que MinIO esté listo..."
until curl -sf "$MINIO_URL/minio/health/live" > /dev/null 2>&1; do
    sleep 2
done
echo "MinIO listo."

docker run --rm --network host \
    -v "$(pwd)/data:/data" \
    --entrypoint /bin/sh \
    minio/mc -c "
        mc alias set local '$MINIO_URL' '$MINIO_USER' '$MINIO_PASS' --api s3v4 &&
        mc mb --ignore-existing 'local/$MINIO_BUCKET' &&
        mc cp '/data/b6666666-6666-6666-6666-666666666666.jpg' 'local/$MINIO_BUCKET/infraestructura_cloud.png' &&
        mc cp '/data/b1111111-1111-1111-1111-111111111111.mp4' 'local/$MINIO_BUCKET/tutorial_pg16.mp4'
    "

echo "Archivos subidos a MinIO bucket '$MINIO_BUCKET'."
