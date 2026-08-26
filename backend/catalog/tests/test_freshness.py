"""Tests for freshness monitoring + staleness alerts (EPH-3B)."""
import pytest
from django.utils import timezone

from accounts.models import NotificationRule, UserAlert
from catalog.freshness_service import check_freshness
from catalog.models import FreshnessPolicy
from dataschema.models import DataRow, DataTable

FRESHNESS_URL = '/carbon-api/catalog/tables/{id}/freshness/'


def _stale_table(module_a):
    """A table whose data is 30 hours old (older than the 24h default)."""
    table = DataTable.objects.create(title='Stale Orders', module=module_a)
    DataTable.objects.filter(pk=table.pk).update(
        last_data_updated_at=timezone.now() - timezone.timedelta(hours=30),
    )
    return table


@pytest.mark.django_db
def test_datarow_save_updates_last_data_updated_at(module_a):
    table = DataTable.objects.create(title='Orders', module=module_a)
    assert table.last_data_updated_at is None

    DataRow.objects.create(data_table=table, values={'customer': 'Amina'})

    table.refresh_from_db()
    assert table.last_data_updated_at is not None


@pytest.mark.django_db
def test_check_freshness_alerts_when_stale(module_a, create_user):
    user = create_user('stale_owner')
    NotificationRule.objects.create(
        event_type='freshness_violation', min_severity='info', enabled=True)
    table = _stale_table(module_a)
    policy = FreshnessPolicy.objects.create(table=table, max_age_hours=24)

    result = check_freshness()

    assert result['alerted'] == 1
    assert UserAlert.objects.filter(user=user, category='dq_violation').exists()
    policy.refresh_from_db()
    assert policy.last_alerted_at is not None
    assert policy.last_checked_at is not None


@pytest.mark.django_db
def test_check_freshness_no_alert_when_fresh(module_a, create_user):
    user = create_user('fresh_owner')
    NotificationRule.objects.create(
        event_type='freshness_violation', min_severity='info', enabled=True)
    table = DataTable.objects.create(title='Fresh Orders', module=module_a)
    DataTable.objects.filter(pk=table.pk).update(last_data_updated_at=timezone.now())
    policy = FreshnessPolicy.objects.create(table=table, max_age_hours=24)

    result = check_freshness()

    assert result['alerted'] == 0
    assert not UserAlert.objects.filter(user=user).exists()
    policy.refresh_from_db()
    assert policy.last_alerted_at is None
    assert policy.last_checked_at is not None


@pytest.mark.django_db
def test_rate_limit_skips_second_alert(module_a, create_user):
    user = create_user('rate_owner')
    NotificationRule.objects.create(
        event_type='freshness_violation', min_severity='info', enabled=True)
    table = _stale_table(module_a)
    policy = FreshnessPolicy.objects.create(table=table, max_age_hours=24)

    check_freshness()
    policy.refresh_from_db()
    first_alerted = policy.last_alerted_at
    assert first_alerted is not None
    alert_count = UserAlert.objects.filter(user=user).count()

    check_freshness()
    policy.refresh_from_db()

    assert policy.last_alerted_at == first_alerted
    assert UserAlert.objects.filter(user=user).count() == alert_count


@pytest.mark.django_db
def test_get_freshness_404_when_no_policy(
        module_a, create_user, get_token_for_user, api_client):
    user = create_user('api_super', is_superuser=True)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}')
    table = DataTable.objects.create(title='No Policy', module=module_a)

    response = api_client.get(FRESHNESS_URL.format(id=table.id))

    assert response.status_code == 404
