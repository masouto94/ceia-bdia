#!/bin/bash
set -e

cd "$(dirname "$0")"

if [ ! -f .env ]; then
    cp .env.example .env
    echo "Creado .env a partir de .env.example"
fi

docker compose up -d

echo "Esperando a que la base de datos esté lista..."
until docker compose exec -T db pg_isready -U admin -d grupo1 > /dev/null 2>&1; do
    sleep 1
done

uv run --project .. uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
