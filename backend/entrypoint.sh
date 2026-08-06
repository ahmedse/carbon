#!/bin/bash
# ─────────────────────────────────────────────────────────────────
#  Carbon entrypoint — runs migrations, collects static, starts Gunicorn
# ─────────────────────────────────────────────────────────────────
set -e

echo "==> Running database migrations..."
python manage.py migrate --noinput

echo "==> Bootstrapping platform (groups, apps, CBAC)..."
python manage.py bootstrap_platform || echo "⚠ Bootstrap had issues — continuing anyway"

echo "==> Collecting static files..."
python manage.py collectstatic --noinput

echo "==> Starting Gunicorn on 0.0.0.0:8000 (workers=3)..."
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level info
