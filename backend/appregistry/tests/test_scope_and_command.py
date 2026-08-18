"""Management command + Scope integration tests for the App Registry."""
import io
import pytest
from django.core.management import call_command

from appregistry.models import AppActivation, AppManifest


# ── register_app command ─────────────────────────────────────────────────

@pytest.mark.django_db
def test_register_app_creates_manifest_and_activation():
    out = io.StringIO()
    call_command(
        'register_app',
        '--slug', 'healthy',
        '--name', 'Healthy Foods Factory',
        '--app-version', '1.0.0',
        '--entry-route', '/apps/healthy',
        '--required-module', 'healthy-sales',
        '--required-capability', 'healthy:view',
        '--consumed-dataset', 'healthy-sales-lines',
        stdout=out,
    )
    app = AppManifest.objects.get(slug='healthy')
    assert app.name == 'Healthy Foods Factory'
    assert app.version == '1.0.0'
    assert app.entry_route == '/apps/healthy'
    assert app.required_modules == ['healthy-sales']
    assert app.required_capabilities == ['healthy:view']
    assert app.consumed_datasets == ['healthy-sales-lines']
    assert app.is_system is False
    # Activation row auto-created
    assert AppActivation.objects.filter(app=app, is_active=True).exists()


@pytest.mark.django_db
def test_register_app_marks_system_app():
    call_command(
        'register_app',
        '--slug', 'emissions',
        '--name', 'Emissions Core',
        '--app-version', '1.0.0',
        '--is-system',
    )
    app = AppManifest.objects.get(slug='emissions')
    assert app.is_system is True


# ── Scope injection (App Registry §7.5) ──────────────────────────────────

@pytest.mark.django_db
def test_build_scope_injects_active_apps_for_superuser(
        superuser, make_app):
    from ai.intelligence import build_scope
    make_app(slug='healthy', name='Healthy Foods',
             required_capabilities=['healthy:view'])
    make_app(slug='water', name='Water Quality',
             required_capabilities=['water:view'])
    scope = build_scope(superuser)
    assert sorted(scope.active_apps) == ['healthy', 'water']
    assert scope.is_superuser is True
    # Serialized audit form includes active_apps
    payload = scope.to_dict()
    assert sorted(payload['active_apps']) == ['healthy', 'water']


@pytest.mark.django_db
def test_build_scope_filters_apps_by_capability(
        create_user, create_scoped_role, make_app):
    from ai.intelligence import build_scope
    # App gated behind a capability the user does NOT have
    make_app(slug='restricted', name='Restricted App',
             required_capabilities=['turnkey:manage'])
    # App with no capability gate → any authenticated user can reach it
    make_app(slug='open', name='Open App', required_capabilities=[])

    user = create_user('plain_user')
    create_scoped_role(user, 'viewers_group', org_unit=None, module=None)
    scope = build_scope(user)
    assert 'open' in scope.active_apps
    assert 'restricted' not in scope.active_apps


@pytest.mark.django_db
def test_build_scope_excludes_deactivated_apps(
        create_user, create_scoped_role, make_app):
    from ai.intelligence import build_scope
    make_app(slug='off', required_capabilities=[])
    AppActivation.objects.filter(app__slug='off').update(is_active=False)

    user = create_user('plain_user')
    create_scoped_role(user, 'viewers_group', org_unit=None, module=None)
    scope = build_scope(user)
    assert 'off' not in scope.active_apps


@pytest.mark.django_db
def test_build_scope_returns_empty_for_anonymous():
    from ai.intelligence import build_scope
    scope = build_scope(None)
    assert scope.active_apps == []
    assert scope.org_unit_ids == []


@pytest.mark.django_db
def test_build_scope_does_not_include_unregistered_apps(
        superuser, make_app):
    from ai.intelligence import build_scope
    make_app(slug='only-one', required_capabilities=[])
    # A second manifest WITHOUT activation record is not runtime-active
    AppManifest.objects.create(
        slug='no-activation', name='No Activation', version='0.1.0',
    )
    scope = build_scope(superuser)
    assert scope.active_apps == ['only-one']
