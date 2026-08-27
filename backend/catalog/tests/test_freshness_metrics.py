"""EPH-6C — freshness telemetry exported to Prometheus.

Verifies that ``catalog.freshness_service.check_freshness()`` publishes:
- ``carbon_freshness_stale_tables``      (gauge: stale enabled-policy tables)
- ``carbon_freshness_tables_total``      (gauge: enabled policies checked)
- ``carbon_freshness_alerts_total``      (counter: alerts raised, by severity)
- ``carbon_freshness_table_age_hours``   (gauge: per-table age, labelled)
"""
import pytest
from django.utils import timezone
from prometheus_client import REGISTRY, generate_latest

from accounts.models import NotificationRule
from catalog.freshness_service import check_freshness
from catalog.models import FreshnessPolicy
from dataschema.models import DataTable


def _alert_counter(severity='warning'):
    """Current value of the freshness alert counter for a severity."""
    return REGISTRY.get_sample_value(
        'carbon_freshness_alerts_total', {'severity': severity}) or 0.0


def _table(module_a, title='Telemetry Table', hours_ago=None):
    """Create a table; when ``hours_ago`` is set, backdate its data update."""
    table = DataTable.objects.create(title=title, module=module_a)
    if hours_ago is not None:
        DataTable.objects.filter(pk=table.pk).update(
            last_data_updated_at=timezone.now() - timezone.timedelta(hours=hours_ago),
        )
    return table


def _metrics_body():
    return generate_latest().decode()


@pytest.mark.django_db
def test_stale_gauge_counts_stale_policy_tables(module_a):
    t1 = _table(module_a, title='Stale A', hours_ago=30)   # > 24h default
    t2 = _table(module_a, title='Stale B', hours_ago=50)   # > 24h default
    t3 = _table(module_a, title='Fresh C', hours_ago=1)
    for t in (t1, t2, t3):
        FreshnessPolicy.objects.create(table=t, max_age_hours=24)

    check_freshness()

    body = _metrics_body()
    assert 'carbon_freshness_stale_tables 2.0' in body
    assert 'carbon_freshness_tables_total 3.0' in body


@pytest.mark.django_db
def test_fresh_tables_yield_zero_stale(module_a):
    table = _table(module_a, title='Fresh Table', hours_ago=1)
    FreshnessPolicy.objects.create(table=table, max_age_hours=24)

    check_freshness()

    assert 'carbon_freshness_stale_tables 0.0' in _metrics_body()


@pytest.mark.django_db
def test_alert_counter_increments_by_severity(module_a, create_user):
    create_user('alert_owner')
    NotificationRule.objects.create(
        event_type='freshness_violation', min_severity='info', enabled=True)
    table = _table(module_a, title='Stale Alerts', hours_ago=30)
    FreshnessPolicy.objects.create(table=table, max_age_hours=24, alert_level='warning')

    before = _alert_counter('warning')
    check_freshness()
    after = _alert_counter('warning')

    assert after == before + 1.0
    assert 'carbon_freshness_alerts_total' in _metrics_body()


@pytest.mark.django_db
def test_rate_limited_alert_not_recounted(module_a, create_user):
    create_user('rate_owner')
    NotificationRule.objects.create(
        event_type='freshness_violation', min_severity='info', enabled=True)
    table = _table(module_a, title='Stale Rate Limited', hours_ago=30)
    policy = FreshnessPolicy.objects.create(table=table, max_age_hours=24)

    check_freshness()  # first pass → alert
    first = _alert_counter()
    policy.refresh_from_db()
    policy.last_alerted_at = timezone.now()  # recent alert → rate-limited
    policy.save(update_fields=['last_alerted_at'])
    check_freshness()  # second pass → skipped

    assert _alert_counter() == first  # no second alert counted
    assert 'carbon_freshness_stale_tables 1.0' in _metrics_body()


@pytest.mark.django_db
def test_per_table_age_gauge_carries_table_label(module_a):
    table = _table(module_a, title='Stale Labeled', hours_ago=30)
    FreshnessPolicy.objects.create(table=table, max_age_hours=24)

    check_freshness()

    body = _metrics_body()
    line = next(
        (ln for ln in body.splitlines()
         if ln.startswith('carbon_freshness_table_age_hours')
         and f'table_id="{table.id}"' in ln),
        None,
    )
    assert line is not None, 'per-table age gauge series missing'
    assert f'table="{table.name}"' in line
