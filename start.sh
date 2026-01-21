#!/bin/bash
# Startup script for Xentauri Cloud Core
# Runs database migrations before starting the app

set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting application..."
# 1 worker to save memory
# ============================================================================
# TECHNICAL DEBT: 600s timeout is a workaround for slow LLM operations
# The full flow (Opus generation + validation + repair + feedback fixes) can
# take 5-10 minutes with Gemini Pro. Proper fix: async/background job processing.
# See: CONTEXT.md "Technical Debt" section
# Sprint 6.1 - January 2026
# ============================================================================
exec gunicorn app.main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8080 --workers 2 --timeout 600 --graceful-timeout 600
