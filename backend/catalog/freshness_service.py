"""Freshness monitoring service (EPH-3B).

Iterates enabled ``FreshnessPolicy`` rows, computes the data age of the linked
``DataTable`` from ``last_data_updated_at`` (falling back to ``created_at``),
and raises a ``freshness_violation`` notification via ``accounts.notify_event``
when the data is stale — subject to a 6-hour per-policy alert rate-limit.
"""
from django.utils import timezone

from accounts.models import notify_event
from core.telemetry import (
    freshness_alerts_total,
    freshness_stale_tables,
    freshness_table_age_hours,
    freshness_tables_total,
)
from .models import FreshnessPolicy

# Minimum interval (hours) between consecutive alerts for the same policy.
ALERT_RATE_LIMIT_HOURS = 6


def check_freshness():
    """Run one freshness pass over all enabled policies.

    Returns a summary dict: ``{"checked": N, "alerted": N, "skipped": N}``.
    """
    now = timezone.now()
    limit_delta = timezone.timedelta(hours=ALERT_RATE_LIMIT_HOURS)
    summary = {"checked": 0, "alerted": 0, "skipped": 0}
    stale_count = 0

    policies = FreshnessPolicy.objects.filter(enabled=True).select_related('table')
    for policy in policies:
        table = policy.table
        reference = table.last_data_updated_at or table.created_at
        age_hours = 0.0 if reference is None else (now - reference).total_seconds() / 3600.0

        is_stale = age_hours > policy.max_age_hours
        if is_stale:
            stale_count += 1

        # EPH-6C: export the per-policy age (one series per enabled policy).
        freshness_table_age_hours.labels(
            table_id=table.id, table=table.name,
        ).set(age_hours)
        should_alert = is_stale

        # Rate-limit: skip the alert if one was raised within the last 6 hours.
        if should_alert and policy.last_alerted_at is not None:
            if (now - policy.last_alerted_at) < limit_delta:
                should_alert = False
                summary['skipped'] += 1

        if should_alert:
            notify_event(
                'freshness_violation',
                title=f"Stale data: {table.title}",
                body=(
                    f"Table '{table.title}' has not been updated in "
                    f"{age_hours:.1f} hours (limit {policy.max_age_hours}h)."
                ),
                severity=policy.alert_level,
                link=f"/catalog/tables/{table.id}/",
            )
            policy.last_alerted_at = now
            summary['alerted'] += 1
            # EPH-6C: count alerts per severity for Prometheus.
            freshness_alerts_total.labels(severity=policy.alert_level).inc()

        policy.last_checked_at = now
        policy.save(update_fields=['last_checked_at', 'last_alerted_at'])
        summary['checked'] += 1

    # EPH-6C: publish pass-level gauges (set, not inc — snapshot per pass).
    freshness_tables_total.set(summary['checked'])
    freshness_stale_tables.set(stale_count)

    return summary
