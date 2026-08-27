#!/bin/sh
# Remove only this repository's local-development Compose resources.
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(dirname -- "$SCRIPT_DIR")
COMPOSE_FILE="$PROJECT_DIR/compose.yaml"
EXPECTED_PROJECT="bdia-project"
CI_APPROVED=false

usage() {
  printf 'Usage: %s [--ci-confirm]\n' "$0"
  printf '  --ci-confirm  non-interactive confirmation; accepted only when CI=true\n'
}

case "${1:-}" in
"") ;;
--ci-confirm) CI_APPROVED=true ;;
-h | --help)
  usage
  exit 0
  ;;
*)
  usage >&2
  exit 2
  ;;
esac
[ "$#" -le 1 ] || {
  usage >&2
  exit 2
}

fail() {
  printf 'REFUSED: %s\n' "$1" >&2
  exit 1
}
command -v docker >/dev/null 2>&1 || fail "Docker is required."
docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 is required."
[ "${APP_ENV:-development}" = development ] || fail "APP_ENV must be development."
case "${DOCKER_HOST:-}" in "" | unix://*) ;; *) fail "remote or non-Unix DOCKER_HOST is not allowed." ;; esac

PROJECT=$(docker compose -f "$COMPOSE_FILE" --project-directory "$PROJECT_DIR" config --format json |
  python3 -c 'import json,sys; print(json.load(sys.stdin)["name"])')
[ "$PROJECT" = "$EXPECTED_PROJECT" ] || fail "Compose project name is not the expected local project."

printf 'This will stop and remove only Compose project: %s\n' "$PROJECT"
printf 'Compose file: %s\n' "$COMPOSE_FILE"
printf "%s\n" "Removal scope: this project's containers, default network, and named volumes."
printf 'Project-owned volumes currently visible:\n'
docker volume ls --filter "label=com.docker.compose.project=$PROJECT" --format '  {{.Name}}' || fail "Could not inspect project volumes."

if [ "$CI_APPROVED" = true ]; then
  [ "${CI:-}" = true ] || fail "--ci-confirm requires CI=true."
else
  [ -t 0 ] || fail "interactive confirmation is required (or use CI=true --ci-confirm)."
  printf 'Type RESET %s to continue: ' "$PROJECT"
  IFS= read -r confirmation
  [ "$confirmation" = "RESET $PROJECT" ] || fail "confirmation did not match."
fi

docker compose -f "$COMPOSE_FILE" --project-directory "$PROJECT_DIR" -p "$EXPECTED_PROJECT" \
  down --volumes --remove-orphans
printf 'Local Compose resources for %s were removed.\n' "$PROJECT"
