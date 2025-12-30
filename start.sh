#!/bin/bash
# Startup script for Xentauri Cloud Core
# Runs database migrations before starting the app

set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting application..."
# 1 worker to save memory, 120s timeout for AI calls
exec gunicorn app.main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8080 --workers 1 --timeout 120
