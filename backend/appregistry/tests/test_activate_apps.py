"""activate_apps command tests (ADR-0015 per-instance activation)."""
import io
import pytest
from django.core.management import call_command

from appregistry.models import AppManifest
from appregistry.services import AppRegistryService


def is_active(slug):
    return AppRegistryService.effective_is_active(AppManifest.objects.get(slug=slug))


@pytest.mark.django_db
def test_activates_listed_and_deactivates_others(make_app):
    make_app(slug='people', name='People')
    make_app(slug='healthy', name='Healthy')
    make_app(slug='facility', name='Facility')

    call_command('activate_apps', '--active', 'people')

    assert is_active('people')
    assert not is_active('healthy')
    assert not is_active('facility')


@pytest.mark.django_db
def test_system_apps_stay_active(make_app):
    make_app(slug='emissions', name='Emissions', is_system=True)
    make_app(slug='people', name='People')

    call_command('activate_apps', '--active', 'people')

    assert is_active('emissions')
    assert is_active('people')


@pytest.mark.django_db
def test_all_flag_activates_everything(make_app):
    make_app(slug='people', name='People')
    make_app(slug='healthy', name='Healthy')

    call_command('activate_apps', '--all')

    assert is_active('people')
    assert is_active('healthy')


@pytest.mark.django_db
def test_idempotent(make_app):
    make_app(slug='people', name='People')
    make_app(slug='healthy', name='Healthy')

    call_command('activate_apps', '--active', 'people')
    call_command('activate_apps', '--active', 'people')

    assert is_active('people')
    assert not is_active('healthy')


@pytest.mark.django_db
def test_unknown_slug_is_warning_not_error(make_app):
    make_app(slug='people', name='People')
    out = io.StringIO()
    call_command('activate_apps', '--active', 'people,not-yet-built', stdout=out)
    assert 'not-yet-built' in out.getvalue()
    assert is_active('people')


@pytest.mark.django_db
def test_no_args_changes_nothing(make_app):
    make_app(slug='people', name='People')
    out = io.StringIO()
    call_command('activate_apps', stdout=out)
    # Guard: no --active/--all → nothing changed, people stays as-is.
    assert is_active('people')
    assert 'Nothing changed' in out.getvalue()


@pytest.mark.django_db
def test_empty_registry_is_safe():
    out = io.StringIO()
    call_command('activate_apps', '--active', 'people', stdout=out)
    assert 'No AppManifests' in out.getvalue()
