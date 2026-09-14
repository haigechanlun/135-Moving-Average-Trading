#!/usr/bin/env bash
# Local learning deploy: venv + deps + web desk.
#   ./deploy_local.sh              # install (if needed) and start http://127.0.0.1:8000
#   ./deploy_local.sh --install-only
#   ./deploy_local.sh --with-live   # also install Gate SDK
#   HOST=0.0.0.0 PORT=8000 ./deploy_local.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
PYTHON="${PYTHON:-python3}"
INSTALL_ONLY=0
WITH_LIVE=0

for arg in "$@"; do
  case "$arg" in
    --install-only) INSTALL_ONLY=1 ;;
    --with-live) WITH_LIVE=1 ;;
    -h|--help)
      sed -n '2,7p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown flag: $arg" >&2
      echo "Use --install-only or --with-live." >&2
      exit 1
      ;;
  esac
done

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "Need Python 3.9+ ($PYTHON not found)." >&2
  exit 1
fi

if [ ! -d .venv ]; then
  echo ">> creating .venv"
  "$PYTHON" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo ">> installing requirements"
python -m pip install -U pip
python -m pip install -e .
python -m pip install -r requirements.txt
if [ "$WITH_LIVE" -eq 1 ]; then
  python -m pip install -r requirements-live.txt
fi

if [ ! -f .env ] && [ -f .env.example ]; then
  cp .env.example .env
  echo ">> wrote .env from .env.example (needed only for Gate --live)"
fi

echo
echo "Local setup ready."
echo "  venv:     source .venv/bin/activate"
echo "  backtest: python -m njm135 backtest --csv data/BTCUSDT_futures_1d.csv"
echo "  tests:    pytest"
echo "  web:      python -m web"
echo

if [ "$INSTALL_ONLY" -eq 1 ]; then
  exit 0
fi

echo ">> starting web desk at http://${HOST}:${PORT}"
exec python -m uvicorn web.app:app --host "$HOST" --port "$PORT" --reload
