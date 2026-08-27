#!/bin/sh
# Run safe, executable security proofs against the local Compose stack.
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(dirname -- "$SCRIPT_DIR")
compose() { docker compose -f "$PROJECT_DIR/compose.yaml" --project-directory "$PROJECT_DIR" "$@"; }
say() { printf '\n==> %s\n' "$1"; }
fail() {
  printf 'ERROR: %s\n' "$1" >&2
  exit 1
}
command -v docker >/dev/null 2>&1 || fail "Docker is required."
docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 is required."

say "Checking every long-running Compose service health"
for service in landing web api db pgadmin minio mailpit embeddings-api; do
  container=$(compose ps -q "$service")
  [ -n "$container" ] || fail "$service is not running; start the stack with 'docker compose up -d'."
  health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container")
  [ "$health" = healthy ] || fail "$service is not healthy (status: $health); inspect 'docker compose logs $service'."
done
API_PORT=${API_PORT:-8000}
case "$API_PORT" in *[!0-9]* | '') fail "API_PORT must be numeric." ;; esac
curl -fsS "http://127.0.0.1:$API_PORT/health" >/dev/null || fail "API health endpoint failed."
EMBEDDINGS_API_PORT=${EMBEDDINGS_API_PORT:-8011}
case "$EMBEDDINGS_API_PORT" in *[!0-9]* | '') fail "EMBEDDINGS_API_PORT must be numeric." ;; esac
curl -fsS "http://127.0.0.1:$EMBEDDINGS_API_PORT/salud" >/dev/null || fail "Embeddings health endpoint failed."
WEB_PORT=${WEB_PORT:-5173}
case "$WEB_PORT" in *[!0-9]* | '') fail "WEB_PORT must be numeric." ;; esac
TEST_WEB_ORIGIN="http://localhost:$WEB_PORT"
MINIO_API_PORT=${MINIO_API_PORT:-9000}
case "$MINIO_API_PORT" in *[!0-9]* | '') fail "MINIO_API_PORT must be numeric." ;; esac
anonymous_status=$(curl -sS -o /dev/null -w '%{http_code}' "http://127.0.0.1:$MINIO_API_PORT/student-assets")
[ "$anonymous_status" = 403 ] || fail "Private MinIO bucket did not deny anonymous listing (HTTP $anonymous_status)."

say "Proving relational, vector/RAG, MinIO capability, and SQL guard contracts"
compose run --rm -T --no-deps -v "$PROJECT_DIR/backend:/app:ro" api \
  python -m unittest -v tests.test_experiments tests.test_documents tests.test_assistant_sql tests.test_dashboard ||
  fail "Backend security contract tests failed."

say "Proving role matrix, dashboard contract, and tenant isolation through the live HTTP API"
# Runtime connection values remain inside the container and are never echoed.
compose run --rm -T --no-deps -e TEST_WEB_ORIGIN="$TEST_WEB_ORIGIN" -v "$PROJECT_DIR/backend:/app:ro" api sh -eu -c \
  'TEST_API_URL=http://api:8000 MAILPIT_URL=http://mailpit:8025 TEST_DATABASE_URL="$RUNTIME_DATABASE_URL" python -m unittest -v tests.test_identity_http' ||
  fail "Live role/tenant HTTP probes failed."

say "Proving RLS and pooled transaction-context boundaries"
compose run --rm -T --no-deps -v "$PROJECT_DIR/backend:/app:ro" api sh -eu -c \
  'TEST_API_URL=http://api:8000 TEST_DATABASE_URL="$RUNTIME_DATABASE_URL" python -m unittest -v tests.test_rls_integration tests.test_tenant_context' ||
  fail "RLS or pooled-context probes failed."

printf '\nStack verification passed without printing credentials or tokens.\n'
