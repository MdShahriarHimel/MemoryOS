#!/bin/sh
set -e

if echo "$DATABASE_URL" | grep -q postgresql; then
  echo "Running Alembic migrations..."
  alembic upgrade head
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
