#!/bin/sh
set -e

echo "→ Running migrations"
alembic upgrade head

echo "→ Seeding demo data (no-op if exists)"
python scripts/seed.py

echo "→ Starting uvicorn"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
