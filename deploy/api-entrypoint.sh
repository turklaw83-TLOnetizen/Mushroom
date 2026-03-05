#!/usr/bin/env bash
# ---- API Container Entrypoint -------------------------------------------
# Runs Alembic migrations, then starts uvicorn.
# Used by Dockerfile.api as the ENTRYPOINT.

set -e

echo "[entrypoint] Running database migrations..."

if [ -n "${DATABASE_URL:-}" ]; then
    # Alembic uses DATABASE_URL from environment (configured in alembic/env.py)
    # stamp head if tables already exist (first run after switching to Alembic)
    python -c "
from sqlalchemy import create_engine, inspect
url = '${DATABASE_URL}'.replace('postgresql+asyncpg://', 'postgresql://')
engine = create_engine(url)
inspector = inspect(engine)
tables = inspector.get_table_names()
engine.dispose()
if 'cases' in tables:
    print('TABLES_EXIST')
else:
    print('FRESH_DB')
" > /tmp/db_status 2>/dev/null || echo "DB_ERROR" > /tmp/db_status

    DB_STATUS=$(cat /tmp/db_status)

    if [ "$DB_STATUS" = "TABLES_EXIST" ]; then
        # Tables exist (created by create_tables()) — stamp Alembic to mark as current
        if ! alembic current 2>/dev/null | grep -q "001_initial"; then
            echo "[entrypoint] Existing tables found — stamping Alembic baseline..."
            alembic stamp head
        fi
        echo "[entrypoint] Running any pending migrations..."
        alembic upgrade head
    elif [ "$DB_STATUS" = "FRESH_DB" ]; then
        echo "[entrypoint] Fresh database — running all migrations..."
        alembic upgrade head
    else
        echo "[entrypoint] WARNING: Could not check database state. Skipping migrations."
    fi
else
    echo "[entrypoint] No DATABASE_URL set — skipping migrations (using JSON storage)"
fi

echo "[entrypoint] Starting uvicorn..."
exec "$@"
