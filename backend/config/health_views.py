"""Phase 1.9: Health & Metrics endpoint."""
import os
import shutil
import time
from django.http import JsonResponse, HttpResponse
from django.db import connections
from django.db.utils import OperationalError
from django.utils import timezone


def health_check(request):
    """Enhanced health endpoint — DB, Redis, disk, last backup, error count."""
    result = {'status': 'ok', 'timestamp': timezone.now().isoformat(), 'checks': {}}

    # 1. Database check
    try:
        db_conn = connections['default']
        db_conn.cursor().execute('SELECT 1')
        result['checks']['database'] = 'ok'
    except OperationalError:
        result['status'] = 'degraded'
        result['checks']['database'] = 'unreachable'

    # 2. Redis check (best-effort)
    try:
        from django.conf import settings
        redis_configured = any('redis' in str(c.get('LOCATION', '')).lower()
                               for c in getattr(settings, 'CACHES', {}).values())
        if redis_configured:
            from django.core.cache import cache
            cache.set('_health_check', '1', 10)
            if cache.get('_health_check') == '1':
                result['checks']['redis'] = 'ok'
            else:
                result['checks']['redis'] = 'unreachable'
                result['status'] = 'degraded'
        else:
            result['checks']['redis'] = 'not_configured'
    except Exception:
        result['checks']['redis'] = 'error'

    # 3. Disk free %
    try:
        stat = shutil.disk_usage('/')
        disk_pct = round((stat.free / stat.total) * 100, 1)
        result['disk_free_pct'] = disk_pct
        if disk_pct < 10:
            result['status'] = 'degraded'
    except Exception:
        result['disk_free_pct'] = None

    # 4. Last backup timestamp
    try:
        from accounts.models import BackupConfig
        backup = BackupConfig.objects.first()
        result['last_backup_at'] = backup.last_backup_at.isoformat() if backup and backup.last_backup_at else None
    except Exception:
        result['last_backup_at'] = None

    # 5. Recent error count (last 24h)
    try:
        from django.contrib.admin.models import LogEntry
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(hours=24)
        error_count = LogEntry.objects.filter(
            action_time__gte=cutoff,
            action_flag=0,  # ADDITION, but we check for error-related
        ).count()
        # Use a simpler approach: just report admin log entries as proxy
        result['recent_admin_actions'] = error_count
    except Exception:
        result['recent_admin_actions'] = None

    status_code = 503 if result['status'] == 'degraded' else 200
    return JsonResponse(result, status=status_code)


def metrics_view(request):
    """Prometheus-compatible text metrics endpoint."""
    lines = ['# HELP carbon_health Health check status (1=ok, 0=degraded)',
             '# TYPE carbon_health gauge']

    try:
        # DB check
        db_conn = connections['default']
        db_conn.cursor().execute('SELECT 1')
        lines.append('carbon_database_up 1')
    except OperationalError:
        lines.append('carbon_database_up 0')

    # Disk free %
    try:
        stat = shutil.disk_usage('/')
        disk_pct = round((stat.free / stat.total) * 100, 1)
        lines.append(f'carbon_disk_free_pct {disk_pct}')
    except Exception:
        lines.append('carbon_disk_free_pct -1')

    # Last backup age in seconds
    try:
        from accounts.models import BackupConfig
        backup = BackupConfig.objects.first()
        if backup and backup.last_backup_at:
            age = (timezone.now() - backup.last_backup_at).total_seconds()
            lines.append(f'carbon_last_backup_age_seconds {age:.0f}')
        else:
            lines.append('carbon_last_backup_age_seconds -1')
    except Exception:
        lines.append('carbon_last_backup_age_seconds -1')

    lines.append('# EOF')
    return HttpResponse('\n'.join(lines) + '\n', content_type='text/plain; version=0.0.4')


def prometheus_metrics_view(request):
    """EPH-6A / P1-11: full Prometheus registry export.

    Serves every registered collector (``carbon_api_requests_total``,
    ``carbon_api_duration_seconds``, ``carbon_dq_runs_total``,
    ``carbon_ai_conversations_active``, plus ``process_*`` runtime metrics)
    via ``prometheus_client.generate_latest()``. Exempt from
    ``SECURE_SSL_REDIRECT`` through ``SECURE_REDIRECT_EXEMPT`` so scrapers can
    poll over plain HTTP on the loopback (CB-09).
    """
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
    return HttpResponse(generate_latest(), content_type=CONTENT_TYPE_LATEST)
