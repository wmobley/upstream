#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD=(docker-compose)
else
  echo "Error: docker compose not found. Install Docker Desktop or docker-compose." >&2
  exit 1
fi

LOG_DIR="${ROOT_DIR}/logs"
mkdir -p "$LOG_DIR"
TIMESTAMP="$(date +'%Y%m%d-%H%M%S')"
API_LOG="${LOG_DIR}/api-${TIMESTAMP}.log"
UI_LOG="${LOG_DIR}/ui-${TIMESTAMP}.log"
PID_FILE="${LOG_DIR}/dev-upstream.pids"

usage() {
  cat <<EOF
Usage: $0 [start|stop] [--detach]

Commands:
  start    Start API, DB, and UI (default).
  stop     Stop API, DB, and UI started by this script.

Options:
  --detach   Do not wait for the UI process; return control to the shell.
EOF
}

ACTION="start"
DETACH="false"
for arg in "${@:-}"; do
  case "$arg" in
    start|stop)
      ACTION="$arg"
      ;;
    --detach|-d)
      DETACH="true"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      usage
      exit 1
      ;;
  esac
done

if [ "$ACTION" = "stop" ]; then
  if [ -f "$PID_FILE" ]; then
    # shellcheck disable=SC1090
    source "$PID_FILE"
    if [ -n "${UI_PID:-}" ] && kill -0 "$UI_PID" >/dev/null 2>&1; then
      echo "Stopping UI (PID $UI_PID)..."
      kill "$UI_PID" >/dev/null 2>&1 || true
    fi
    if [ -n "${API_LOG_PID:-}" ] && kill -0 "$API_LOG_PID" >/dev/null 2>&1; then
      echo "Stopping API log tail (PID $API_LOG_PID)..."
      kill "$API_LOG_PID" >/dev/null 2>&1 || true
    fi
    rm -f "$PID_FILE"
  else
    echo "No PID file found at $PID_FILE (UI log tail may already be stopped)."
  fi

  echo "Stopping API and database..."
  (
    cd "$ROOT_DIR/upstream-docker-pods"
    "${COMPOSE_CMD[@]}" -f docker-compose.yml down
  )
  exit 0
fi

STOP_ON_EXIT="${STOP_ON_EXIT:-false}"
cleanup() {
  if [ "$STOP_ON_EXIT" = "true" ]; then
    echo "Stopping API and database..."
    (
      cd "$ROOT_DIR/upstream-docker-pods"
      "${COMPOSE_CMD[@]}" -f docker-compose.yml down
    )
  fi
}

trap cleanup EXIT

echo "Starting API + database (Docker)..."
(
  cd "$ROOT_DIR/upstream-docker-pods"
  ENV=dev \
  TAPIS_ENFORCE_AUTH_IN_DEV=false \
  TAPIS_BASE_URL=https://portals.tapis.io \
  TAPIS_TENANT_ID=portals \
  DATABASE_URL="postgresql+psycopg://fastapi_traefik:fastapi_traefik@db:5432/fastapi_traefik" \
    "${COMPOSE_CMD[@]}" -f docker-compose.yml up --build -d
)

echo "Streaming API logs to $API_LOG"
(
  cd "$ROOT_DIR/upstream-docker-pods"
  "${COMPOSE_CMD[@]}" -f docker-compose.yml logs -f --tail=200 web
) >"$API_LOG" 2>&1 &
API_LOG_PID=$!

echo "Waiting for API to be ready..."
API_URL="http://127.0.0.1:8000/docs"
READY=0
for i in {1..30}; do
  if curl -fsS "$API_URL" >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 1
done

if [ "$READY" -ne 1 ]; then
  echo "API did not become ready at $API_URL. Showing container logs..."
  (
    cd "$ROOT_DIR/upstream-docker-pods"
    "${COMPOSE_CMD[@]}" -f docker-compose.yml logs --tail=200 web
  )
  exit 1
fi

if [ ! -d "$ROOT_DIR/upstream-ui/node_modules" ]; then
  echo "Note: upstream-ui/node_modules not found. Run 'npm install' in upstream-ui if dev server fails."
fi

echo "Starting UI (Vite dev server)..."
cd "$ROOT_DIR/upstream-ui"
npm run dev >"$UI_LOG" 2>&1 &
UI_PID=$!

echo "UI running in background (PID $UI_PID). Logs: $UI_LOG"
echo "API log streaming in background (PID $API_LOG_PID). Logs: $API_LOG"
cat >"$PID_FILE" <<EOF
UI_PID=$UI_PID
API_LOG_PID=$API_LOG_PID
API_LOG="${API_LOG}"
UI_LOG="${UI_LOG}"
EOF

echo "To stop everything: $0 stop"

if [ "$DETACH" = "true" ]; then
  exit 0
fi

wait $UI_PID
