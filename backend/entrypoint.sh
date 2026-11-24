#!/bin/sh
set -e

if [ "$1" = "uvicorn" ]; then
  echo "[PulseIQ] Running Alembic database migrations..."
  alembic upgrade head

  if [ "${AUTO_SEED_ON_STARTUP:-true}" = "true" ]; then
    echo "[PulseIQ] Checking initial dataset & seed state..."
    python -m app.data.seed_database
  fi
fi

exec "$@"
