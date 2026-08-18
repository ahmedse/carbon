"""TurnKey Bridge management API tests (DESIGN-PLATFORM.md §6.6 / §6.8).

Covers: config CRUD with encrypted-at-rest API key, link lifecycle, feedback
loop, and the CBAC capability gates (turnkey:view / turnkey:manage).
"""
import pytest

from integrations.turnkey.models import PredictionRecord, TurnKeyConfig, TurnKeyModelLink
from integrations.turnkey.tests.conftest import signed_post

CONFIGS = '/carbon-api/integrations/turnkey/configs/'
LINKS = '/carbon-api/integrations/turnkey/links/'


@pytest.fixture
def linked_version(make_dataset, make_table, make_version, make_config, make_link, module_a):
    def _build(**link_kwargs):
        dataset = make_dataset(module_a)
        table = make_table(module_a)
        version = make_version(dataset, table)
        config = make_config()
        link = make_link(version, config, **link_kwargs)
        return {'dataset': dataset, 'table': table, 'version': version,
                'config': config, 'link': link}
    return _build


# ── Configs ────────────────────────────────────────────────────────────────

def test_api_key_encrypted_at_rest(db, auth_client):
    """§6.8 gate: API key stored Fernet-encrypted, never plaintext."""
    response = auth_client().post(
        CONFIGS, {
            'name': 'prod-turnkey',
            'base_url': 'https://turnkey.prod.example',
            'api_key': 'sk-super-secret-key-value',
        },
        format='json',
    )
    assert response.status_code == 201, response.content
    data = response.json()
    assert data['has_api_key'] is True
    assert 'api_key' not in data
    assert 'api_key_encrypted' not in data

    config = TurnKeyConfig.objects.get(name='prod-turnkey')
    assert config.api_key_encrypted != 'sk-super-secret-key-value'
    assert 'sk-super-secret-key-value' not in config.api_key_encrypted
    # Round-trip decrypt works.
    assert config.get_api_key() == 'sk-super-secret-key-value'


def test_config_create_encrypts_api_key(db, auth_client):
    """Alias of the §6.8 gate (descriptive name)."""
    test_api_key_encrypted_at_rest(db, auth_client)


def test_config_list_requires_turnkey_manage(db, api_client, create_user,
                                             create_scoped_role, get_token_for_user):
    """User without turnkey:manage cannot list configs (403)."""
    user = create_user('config_peon')
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}')
    response = api_client.get(CONFIGS)
    assert response.status_code == 403

    # A turnkey_lead (global manage) can list.
    create_scoped_role(user, 'turnkey_lead')
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}')
    response = api_client.get(CONFIGS)
    assert response.status_code == 200


# ── Links + CBAC ───────────────────────────────────────────────────────────

def test_link_create_requires_turnkey_manage(db, api_client, create_user,
                                             create_scoped_role, get_token_for_user,
                                             linked_version):
    """POST /links/ is gated on turnkey:manage (turnkey:view is not enough)."""
    ctx = linked_version()
    user = create_user('link_viewer')
    create_scoped_role(user, 'viewers_group', module=ctx['version'].dataset.module)
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}')
    response = api_client.get(LINKS)
    assert response.status_code == 200  # turnkey:view granted → list OK

    response = api_client.post(
        LINKS, {
            'dataset_version': str(ctx['version'].id),
            'turnkey_config': str(ctx['config'].id),
            'purpose': 'inference',
            'model_name': 'payroll-forecast',
        },
        format='json',
    )
    assert response.status_code == 403  # turnkey:manage missing


def test_cbac_turnkey_view_required(db, api_client, create_user,
                                    get_token_for_user, linked_version):
    """User without turnkey:view gets 403 on the links list (§6.8 gate)."""
    ctx = linked_version()
    user = create_user('no_perms')
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}')
    assert api_client.get(LINKS).status_code == 403

    # Global admin (admin group) bypasses — same capability resolution path.
    from django.contrib.auth.models import Group
    from accounts.models import ScopedRole
    Group.objects.get_or_create(name='admin')
    ScopedRole.objects.create(user=user, group=Group.objects.get(name='admin'))
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}')
    assert api_client.get(LINKS).status_code == 200


def test_link_list_scoped_by_module(db, auth_client, create_user, create_scoped_role,
                                    get_token_for_user, make_dataset, make_table,
                                    make_version, make_config, make_link, module_a,
                                    module_b):
    """User with a module-scoped turnkey:view role only sees links in that module."""
    ds_a = make_dataset(module_a)
    ds_b = make_dataset(module_b, name='Other Dataset', slug='other-dataset')
    v_a = make_version(ds_a, make_table(module_a, title='Table A', name='table_a'))
    v_b = make_version(ds_b, make_table(module_b, title='Table B', name='table_b'))
    config = make_config()
    link_a = make_link(v_a, config)
    link_b = make_link(v_b, config, turnkey_model_name='other-model')

    user = create_user('module_viewer')
    create_scoped_role(user, 'viewers_group', module=module_a)
    api_client = auth_client(user)

    response = api_client.get(LINKS)
    assert response.status_code == 200
    ids = [item['id'] for item in response.json()]
    assert str(link_a.id) in ids
    assert str(link_b.id) not in ids


def test_link_create_and_feedback_loop(db, auth_client, linked_version, monkeypatch):
    """Superuser: create link, then submit feedback closes the loop."""
    ctx = linked_version()
    client = auth_client()

    # Stub outbound TurnKey calls (no live TurnKey in tests) — register returns
    # a fake model id so the link lifecycle proceeds to 'registered'.
    class FakeTurnKeyClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def register_or_get_model(self, name, model_type='custom'):
            return {'id': 'm_fake_001', 'name': name}

    import integrations.turnkey.services as services
    monkeypatch.setattr(services, 'CarbonTurnKeyClient',
                        lambda base_url, api_key, timeout=30.0: FakeTurnKeyClient())

    # Create a link (POST) → link row created and registered.
    response = client.post(
        LINKS, {
            'dataset_version': str(ctx['version'].id),
            'turnkey_config': str(ctx['config'].id),
            'purpose': 'training',
            'model_name': 'training-model',
        },
        format='json',
    )
    assert response.status_code == 201, response.content
    link = TurnKeyModelLink.objects.get(id=response.json()['id'])
    assert link.purpose == 'training'
    assert link.status == 'registered'
    assert link.turnkey_model_id == 'm_fake_001'

    # Seed a prediction via the signed callback.
    from integrations.turnkey.models import input_hash_of
    payload = {
        'model_link': str(link.id),
        'prediction': {'forecast': 10},
        'input_hash': input_hash_of({'sku': 'X1'}),
    }
    resp = signed_post(client, '/carbon-api/integrations/turnkey/callback/predictions/', payload)
    assert resp.status_code == 201
    prediction = PredictionRecord.objects.get(model_link=link)
    assert prediction.actual is None

    # Feedback loop: submit the actual outcome (turnkey:view).
    url = (
        f'/carbon-api/integrations/turnkey/links/{link.id}/'
        f'predictions/{prediction.id}/feedback/'
    )
    resp = client.post(url, {'actual': {'forecast': 12}}, format='json')
    assert resp.status_code == 200, resp.content
    prediction.refresh_from_db()
    assert prediction.actual == {'forecast': 12}
    assert prediction.feedback_submitted_at is not None
    assert prediction.feedback_by is not None


def test_feedback_loop(db, auth_client, linked_version):
    """§6.8 gate: submit actual → PredictionRecord.actual set."""
    ctx = linked_version()
    prediction = PredictionRecord.objects.create(
        model_link=ctx['link'], prediction={'forecast': 10},
    )
    url = (
        f'/carbon-api/integrations/turnkey/links/{ctx["link"].id}/'
        f'predictions/{prediction.id}/feedback/'
    )
    response = auth_client().post(url, {'actual': {'forecast': 12}}, format='json')
    assert response.status_code == 200, response.content
    prediction.refresh_from_db()
    assert prediction.actual == {'forecast': 12}
    assert prediction.feedback_submitted_at is not None
    assert prediction.feedback_by is not None


def test_drift_alerts_listing(db, auth_client, linked_version):
    """GET drift alerts for a link (turnkey:view for superuser)."""
    ctx = linked_version()
    url = f'/carbon-api/integrations/turnkey/links/{ctx["link"].id}/drift-alerts/'
    response = auth_client().get(url)
    assert response.status_code == 200
    assert response.json() == []
