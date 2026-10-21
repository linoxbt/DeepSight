#!/bin/sh
set -eu

if [ "${DEEPSIGHT_PROCESS:-api}" = "worker" ]; then
  if [ -n "${DEEPSIGHT_KEYSTORE_B64:-}" ]; then
    umask 077
    printf '%s' "$DEEPSIGHT_KEYSTORE_B64" | base64 -d > /app/data/relay.keystore.json
    export DEEPSIGHT_KEYSTORE=/app/data/relay.keystore.json
    unset DEEPSIGHT_KEYSTORE_B64
  fi
  # The API applies migrations first. The worker waits for that shared schema.
  attempt=0
  until python -c 'from api.db import init_db; init_db()'; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 30 ]; then
      echo "Database schema did not become ready" >&2
      exit 1
    fi
    sleep 2
  done
  exec python -m api.worker
fi

alembic upgrade head
exec uvicorn api.main:app --host 0.0.0.0 --port "${PORT:-8000}"
