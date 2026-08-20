"""Management-command tests: idempotent registration of the healthy app."""
import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_register_healthy_app_creates_manifest_modules_datasource_datasets():
    call_command('register_healthy_app')

    from appregistry.models import AppManifest, AppActivation
    from catalog.models import DataContract, Dataset
    from connections.models import DataSource
    from core.models import Module

    manifest = AppManifest.objects.get(slug='healthy')
    assert manifest.name == 'Healthy Foods Factory'
    assert 'healthy:view' in manifest.required_capabilities
    assert AppActivation.objects.filter(app=manifest).exists()

    assert Module.objects.filter(name__startswith='healthy-').count() == 5
    assert DataSource.objects.filter(
        name='Healthy ERP (Azure PostgreSQL)', source_type='database',
    ).exists()
    assert Dataset.objects.filter(
        slug__in=[
            'healthy-returns-panel', 'healthy-churn-panel', 'healthy-sales-lines',
            'healthy-ar-aging', 'healthy-transaction-classifier-panel',
        ],
    ).count() == 5
    assert DataContract.objects.filter(consumer_apps__contains=['healthy']).count() == 5


@pytest.mark.django_db
def test_register_healthy_app_is_idempotent():
    from appregistry.models import AppManifest
    from catalog.models import DataContract, Dataset
    from core.models import Module

    call_command('register_healthy_app')
    call_command('register_healthy_app')

    assert AppManifest.objects.filter(slug='healthy').count() == 1
    assert Module.objects.filter(name__startswith='healthy-').count() == 5
    assert Dataset.objects.filter(slug__startswith='healthy-').count() == 5
    assert DataContract.objects.filter(consumer_apps__contains=['healthy']).count() == 5
