#!/bin/sh
set -eu
mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
mc mb --ignore-existing local/student-assets
mc anonymous set none local/student-assets
touch /tmp/minio-initialized
