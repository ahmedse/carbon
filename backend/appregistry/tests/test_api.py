"""API tests for the App Registry (Phase P3)."""
import pytest

from appregistry.models import AppActivation, AppManifest
from appregistry.services import AppRegistryService

APPS_URL = '/carbon-api/apps/'
ACTIVATE_URL = APPS_URL + '{slug}/activate/'
DEACTIVATE_URL = APPS_URL + '{slug}/deactivate/'


@pytest.fixture
def plain_user(create_user):
    """Authenticated user with NO capabilities (no groups, not staff)."""
    return create_user('plain_user')


@pytest.fixture
def viewer_user(create_user, create_scoped_role):
    """User with a global viewers_group role → appregistry:view only."""
    user = create_user('viewer_user')
    create_scoped_role(user, 'viewers_group', org_unit=None, module=None)
    return user


def _auth(client, token):
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return client


# ── Authentication & capability gating ───────────────────────────────────

@pytest.mark.django_db
def test_unauthenticated_gets_401(api_client):
    assert api_client.get(APPS_URL).status_code == 401


@pytest.mark.django_db
def test_plain_user_without_capability_gets_403(
        api_client, plain_user, get_token_for_user):
    client = _auth(api_client, get_token_for_user(plain_user))
    assert client.get(APPS_URL).status_code == 403


@pytest.mark.django_db
def test_viewer_can_list_apps(
        api_client, viewer_user, get_token_for_user, make_app):
    make_app(slug='healthy', name='Healthy Foods')
    make_app(slug='water', name='Water Quality')
    client = _auth(api_client, get_token_for_user(viewer_user))
    resp = client.get(APPS_URL)
    assert resp.status_code == 200
    slugs = [item['slug'] for item in resp.data]
    assert 'healthy' in slugs and 'water' in slugs


@pytest.mark.django_db
def test_viewer_can_get_app_detail(
        api_client, viewer_user, get_token_for_user, make_app):
    app = make_app(slug='healthy', name='Healthy Foods', version='1.2.0')
    client = _auth(api_client, get_token_for_user(viewer_user))
    resp = client.get(APPS_URL + 'healthy/')
    assert resp.status_code == 200
    assert resp.data['name'] == 'Healthy Foods'
    assert resp.data['version'] == '1.2.0'
    assert resp.data['activation']['is_active'] is True


@pytest.mark.django_db
def test_detail_404_for_unknown_slug(
        api_client, viewer_user, get_token_for_user):
    client = _auth(api_client, get_token_for_user(viewer_user))
    assert client.get(APPS_URL + 'nope/').status_code == 404


# ── Activation lifecycle (appregistry:manage) ───────────────────────────

@pytest.mark.django_db
def test_viewer_cannot_activate_app(
        api_client, viewer_user, get_token_for_user, make_app):
    make_app(slug='healthy')
    client = _auth(api_client, get_token_for_user(viewer_user))
    resp = client.post(ACTIVATE_URL.format(slug='healthy'))
    assert resp.status_code == 403


@pytest.mark.django_db
def test_manage_capability_user_can_activate(
        api_client, create_user, create_scoped_role, get_token_for_user,
        make_app):
    """Manage capability via a global admins_group → activate succeeds."""
    manager = create_user('app_manager')
    create_scoped_role(manager, 'admins_group', org_unit=None, module=None)
    make_app(slug='healthy')
    client = _auth(api_client, get_token_for_user(manager))
    resp = client.post(ACTIVATE_URL.format(slug='healthy'))
    assert resp.status_code == 200
    assert resp.data['activation']['is_active'] is True
    assert AppActivation.objects.get(app__slug='healthy').is_active is True


@pytest.mark.django_db
def test_activate_idempotent_and_sets_actor(
        api_client, superuser, get_token_for_user, make_app):
    make_app(slug='healthy')
    client = _auth(api_client, get_token_for_user(superuser))
    first = client.post(ACTIVATE_URL.format(slug='healthy'))
    second = client.post(ACTIVATE_URL.format(slug='healthy'))
    assert first.status_code == 200 and second.status_code == 200
    activation = AppActivation.objects.get(app__slug='healthy')
    assert activation.is_active is True
    assert activation.activated_by_id == superuser.id


@pytest.mark.django_db
def test_deactivate_marks_inactive_and_records_actor(
        api_client, superuser, get_token_for_user, make_app):
    make_app(slug='healthy')
    client = _auth(api_client, get_token_for_user(superuser))
    resp = client.post(DEACTIVATE_URL.format(slug='healthy'))
    assert resp.status_code == 200
    assert resp.data['activation']['is_active'] is False
    assert resp.data['activation']['deactivated_at'] is not None
    activation = AppActivation.objects.get(app__slug='healthy')
    assert activation.is_active is False
    assert activation.deactivated_by_id == superuser.id


@pytest.mark.django_db
def test_deactivate_system_app_rejected_400(
        api_client, superuser, get_token_for_user, make_app):
    make_app(slug='emissions', is_system=True)
    client = _auth(api_client, get_token_for_user(superuser))
    resp = client.post(DEACTIVATE_URL.format(slug='emissions'))
    assert resp.status_code == 400
    assert 'System app' in resp.data['detail']
    assert AppActivation.objects.get(app__slug='emissions').is_active is True


# ── Services layer ───────────────────────────────────────────────────────

@pytest.mark.django_db
def test_register_manifest_is_idempotent(make_app):
    app = make_app(slug='healthy')
    first, created1 = AppRegistryService.register_manifest(
        slug='healthy', name='Healthy Foods', version='1.0.0')
    second, created2 = AppRegistryService.register_manifest(
        slug='healthy', name='Healthy Foods Renamed', version='1.1.0')
    assert created1 is False  # already existed
    assert created2 is False
    second.refresh_from_db()
    assert second.name == 'Healthy Foods Renamed'
    assert second.version == '1.1.0'
    assert app.id == second.id  # same row — no duplicates
