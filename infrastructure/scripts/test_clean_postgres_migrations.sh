#!/usr/bin/env sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/infrastructure/testing/migration-compose.yml"
PROJECT_NAME="${AGENTVPN_MIGRATION_TEST_PROJECT:-agentvpn-migration-test-$$}"

cleanup() {
  docker compose --project-name "$PROJECT_NAME" --file "$COMPOSE_FILE" down --remove-orphans
}

trap cleanup EXIT INT TERM

docker compose \
  --project-name "$PROJECT_NAME" \
  --file "$COMPOSE_FILE" \
  up --build --abort-on-container-exit --exit-code-from migration-test
