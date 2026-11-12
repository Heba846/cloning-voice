#!/usr/bin/env bash
# Local dev server with hot reload. Usage: ./scripts/dev.sh
set -e
cd "$(dirname "$0")/../backend"
[ -f ../.env ] && set -a && . ../.env && set +a
python3 -m pip install -q -r requirements.txt
exec uvicorn app.main:app --reload --port "${PORT:-8000}"
