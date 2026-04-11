#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE="${1:-}"
HOLD="${2:-}"

if [ -z "$SERVICE" ]; then
  echo "Usage: bash $0 <service> [--hold]"
  exit 1
fi

run_service() {
  case "$SERVICE" in
    fastapi)
      cd "$ROOT/FastAPI"
      . .venv-linux/bin/activate
      pkill -f "uvicorn main:app --host 127.0.0.1 --port 8000" 2>/dev/null || true
      pkill -f "$ROOT/FastAPI/.venv-linux/bin/python .*uvicorn.*main:app" 2>/dev/null || true
      pkill -f "main:app --host 127.0.0.1 --port 8000 --reload" 2>/dev/null || true
      exec uvicorn main:app --host 127.0.0.1 --port 8000 --reload
      ;;
    backend)
      cd "$ROOT"
      . ./dev-env.sh
      # Avoid EADDRINUSE when an old backend process is still running.
      pkill -f "$ROOT/backend/node_modules/.bin/nodemon index.js" 2>/dev/null || true
      pkill -f "$ROOT/backend.*nodemon index.js" 2>/dev/null || true
      pkill -f "$ROOT/backend.*node index.js" 2>/dev/null || true
      cd backend
      exec npm run dev
      ;;
    admin-backend)
      cd "$ROOT"
      . ./dev-env.sh
      # Clear stale admin backend processes before starting a new one.
      pkill -f "$ROOT/admin-backend/node_modules/.bin/nodemon index.js" 2>/dev/null || true
      pkill -f "$ROOT/admin-backend.*nodemon index.js" 2>/dev/null || true
      pkill -f "$ROOT/admin-backend.*node index.js" 2>/dev/null || true
      cd admin-backend
      exec npm run dev
      ;;
    frontend)
      cd "$ROOT"
      . ./dev-env.sh
      cd frontend
      exec env VITE_API_TARGET=http://127.0.0.1:5001 npm run dev -- --host 127.0.0.1 --port 5173
      ;;
    admin-frontend)
      cd "$ROOT"
      . ./dev-env.sh
      cd admin-frontend
      exec npm run dev -- --host 127.0.0.1 --port 5174
      ;;
    *)
      echo "Unknown service: $SERVICE"
      exit 1
      ;;
  esac
}

if [ "$HOLD" = "--hold" ]; then
  set +e
  run_service
  status=$?
  set -e
  echo
  echo "Service '$SERVICE' exited with status $status"
  exec bash
else
  run_service
fi
