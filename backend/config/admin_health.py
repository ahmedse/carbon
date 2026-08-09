"""Phase 1.9: Admin health status — context processor + template tag."""
from django.db import connections
from django.db.utils import OperationalError
from django.utils.html import format_html


def health_context_processor(request):
    """Inject health status into all templates (including admin)."""
    if not request.path.startswith('/admin/'):
        return {}
    return {'health_status': _get_health()}


def _get_health():
    checks = {}

    # Database
    try:
        connections['default'].cursor().execute('SELECT 1')
        checks['database'] = {'status': 'green', 'label': 'DB OK'}
    except OperationalError:
        checks['database'] = {'status': 'red', 'label': 'DB Down'}

    # Redis
    try:
        from django.core.cache import cache
        cache.set('_admin_health', 1, 5)
        if cache.get('_admin_health') == 1:
            checks['redis'] = {'status': 'green', 'label': 'Redis OK'}
        else:
            checks['redis'] = {'status': 'yellow', 'label': 'Redis Slow'}
    except Exception:
        checks['redis'] = {'status': 'red', 'label': 'Redis Down'}

    # Disk
    import shutil
    try:
        stat = shutil.disk_usage('/')
        pct = stat.free / stat.total * 100
        if pct > 20:
            checks['disk'] = {'status': 'green', 'label': f'Disk {pct:.0f}% free'}
        elif pct > 5:
            checks['disk'] = {'status': 'yellow', 'label': f'Disk {pct:.0f}% free'}
        else:
            checks['disk'] = {'status': 'red', 'label': f'Disk {pct:.0f}% free'}
    except Exception:
        checks['disk'] = {'status': 'grey', 'label': 'Disk ?'}

    # Last backup
    try:
        from accounts.models import BackupConfig
        backup = BackupConfig.objects.first()
        if backup and backup.last_backup_at:
            from django.utils import timezone
            age_h = (timezone.now() - backup.last_backup_at).total_seconds() / 3600
            if age_h < 25:
                checks['backup'] = {'status': 'green', 'label': f'Backup {age_h:.0f}h ago'}
            elif age_h < 49:
                checks['backup'] = {'status': 'yellow', 'label': f'Backup {age_h:.0f}h ago'}
            else:
                checks['backup'] = {'status': 'red', 'label': f'Backup {age_h:.0f}h ago'}
        else:
            checks['backup'] = {'status': 'grey', 'label': 'No backups yet'}
    except Exception:
        checks['backup'] = {'status': 'grey', 'label': 'Backup ?'}

    # Aggregate
    reds = sum(1 for c in checks.values() if c['status'] == 'red')
    yellows = sum(1 for c in checks.values() if c['status'] == 'yellow')
    if reds:
        overall = 'red'
    elif yellows:
        overall = 'yellow'
    else:
        overall = 'green'

    return {'overall': overall, 'checks': checks}
