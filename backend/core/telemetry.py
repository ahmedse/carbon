# File: backend/core/telemetry.py
# EPH-6A / P1-11 — Prometheus metric definitions shared across the platform.
#
# Importing this module registers the collectors on the default registry that
# ``prometheus_client`` maintains, which ``config/health_views.py`` exports via
# ``generate_latest()``. Metric recording is a cheap counter/histogram bump —
# safe to call on every request (see ``core/middleware.py``).

from prometheus_client import Counter, Gauge, Histogram

# ── API request telemetry (incremented by RequestLoggingMiddleware) ────────
api_requests_total = Counter(
    'carbon_api_requests_total',
    'Total API requests handled',
    ['method', 'status', 'app'],
)

api_duration_seconds = Histogram(
    'carbon_api_duration_seconds',
    'API request handling duration in seconds',
    ['app'],
)

# ── DQ rule executions (incremented by dq/services.run_dq) ─────────────────
dq_runs_total = Counter(
    'carbon_dq_runs_total',
    'DQ rule executions by outcome',
    ['status'],
)

# ── AI workspace occupancy (set by AI session lifecycle) ───────────────────
ai_conversations_active = Gauge(
    'carbon_ai_conversations_active',
    'Active AI conversations',
)

# ── Freshness monitoring (EPH-6C — set by catalog.freshness_service) ───────
freshness_stale_tables = Gauge(
    'carbon_freshness_stale_tables',
    'Tables with an enabled FreshnessPolicy currently over max_age_hours',
)
freshness_tables_total = Gauge(
    'carbon_freshness_tables_total',
    'Enabled FreshnessPolicy tables checked in the last freshness pass',
)
freshness_alerts_total = Counter(
    'carbon_freshness_alerts_total',
    'Freshness violation alerts raised',
    ['severity'],
)
freshness_table_age_hours = Gauge(
    'carbon_freshness_table_age_hours',
    'Hours since the last data update, per table with an enabled policy',
    ['table_id', 'table'],
)


def app_label_from_path(path: str) -> str:
    """Best-effort app label from a request path.

    ``/carbon-api/dq/rules/...`` → ``dq``; unknown/empty → ``unknown``.
    Never raises; used only for metric labels.
    """
    parts = [p for p in (path or '').split('/') if p]
    if len(parts) >= 2:
        return parts[1]
    return parts[0] if parts else 'unknown'
