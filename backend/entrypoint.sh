#!/bin/bash
# ─────────────────────────────────────────────────────────────────
#  Carbon entrypoint — runs migrations, collects static, starts Gunicorn
# ─────────────────────────────────────────────────────────────────
set -e

echo "==> Running database migrations..."
python manage.py migrate --noinput

echo "==> Bootstrapping platform (groups, apps, CBAC)..."
python manage.py bootstrap_platform || echo "⚠ Bootstrap had issues — continuing anyway"

echo "==> Ensuring Nibras admin accounts (no-op unless DJANGO_BRAND=nibras)..."
python manage.py ensure_nibras_admins || echo "⚠ Admin provisioning had issues — continuing anyway"

# Create-only People official InboundTemplate rows (ADR-0060 · R8). Soft-fail so
# a brand without inbound tables yet still boots. Never AppConfig.ready().
echo "==> Ensuring People official inbound templates (create-only)..."
python manage.py ensure_people_inbound_templates || echo "⚠ People inbound templates ensure had issues — continuing anyway"

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
