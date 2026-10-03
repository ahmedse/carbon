"""Phase 1.9: Health & Metrics endpoint."""
import os
import shutil
import time
from pathlib import Path

from django.http import JsonResponse, HttpResponse
from django.db import connections
from django.db.utils import OperationalError
from django.utils import timezone

# Set when this worker loads. The status bar shows it as process start.
_PROCESS_STARTED_AT = timezone.now().isoformat()


def _packs_root() -> Path:
    """Dev repo layout and the production ``/domain_packs`` mount."""
    from django.conf import settings

    sibling = Path(settings.BASE_DIR).resolve().parent / "domain_packs"
    if sibling.is_dir():
        return sibling
    mounted = Path("/domain_packs")
    if mounted.is_dir():
        return mounted
    return sibling


def _pack_version(root: Path, pack_id: str) -> str | None:
    path = root / pack_id / "pack.yaml"
    if not path.is_file():
        return None
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("version:"):
                return line.split(":", 1)[1].strip().strip("'\"") or None
    except OSError:
        return None
    return None


def release_payload() -> dict:
    """Read-only release identity for the shell tooltip and the deploy gate.

    ``loaded_packs`` / ``catalogs`` are honest disk listings: directories that
    actually contain ``pack.yaml`` / ``api_catalog.yaml``.

    ``extra_packs`` is a *policy* statement, not a disk listing: the packs the
    running brand is authorized to load alongside its primary pack
    (``ai.platform_bind.extra_packs_for_brand``), narrowed to those actually
    mounted. Enumerating raw ``domain_packs/*`` here would over-report every
    checked-out sibling pack and hide a broken isolation invariant — a nibras
    cell must load no other platform pack.
    """
    from ai.instance_registry import active_brand, resolve_instance_id
    from ai.models.control_state import CONTAINMENT_FULL_STOP, PulseControlState
    from ai.platform_bind import extra_packs_for_brand

    brand = active_brand()
    pack = resolve_instance_id()
    root = _packs_root()
    loaded: list[str] = []
    catalogs: list[str] = []
    if root.is_dir():
        for child in sorted(root.iterdir()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            if (child / "pack.yaml").is_file():
                loaded.append(child.name)
            if (child / "api_catalog.yaml").is_file():
                catalogs.append(child.name)
    # Authorized extras that are genuinely mounted (and never the primary pack).
    loaded_set = set(loaded)
    extra_packs = [
        name
        for name in extra_packs_for_brand(brand)
        if name in loaded_set and name != pack
    ]
    present = (root / pack / "pack.yaml").is_file()
    pulse_enabled = present
    try:
        row = PulseControlState.objects.filter(instance_id=pack).only(
            "containment_level"
        ).first()
        if row is not None and row.containment_level == CONTAINMENT_FULL_STOP:
            pulse_enabled = False
    except Exception:
        pass
    return {
        "tag": os.environ.get("CARBON_RELEASE_TAG") or "",
        "process_brand": brand,
        "pack": pack,
        "pack_version": _pack_version(root, pack),
        "extra_packs": extra_packs,
        "loaded_packs": loaded,
        "catalogs": catalogs,
        "pulse_enabled": pulse_enabled,
        "image_built_at": os.environ.get("CARBON_IMAGE_BUILT_AT") or None,
        "process_started_at": _PROCESS_STARTED_AT,
        "deployed_at": os.environ.get("CARBON_DEPLOYED_AT") or None,
    }


def health_check(request):
    """Enhanced health endpoint — DB, Redis, disk, last backup, error count."""
    result = {'status': 'ok', 'timestamp': timezone.now().isoformat(), 'checks': {}}
    try:
        result["release"] = release_payload()
    except Exception:
        result["release"] = {"pulse_enabled": False}

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
