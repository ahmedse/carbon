"""API + CBAC tests for the Healthy Foods Factory app (DESIGN-PLATFORM.md §8.5)."""
import pytest

HEALTHY_API = '/carbon-api/healthy/'
SNAPSHOTS_URL = HEALTHY_API + 'snapshots/'
LOADOUT_URL = HEALTHY_API + 'loadout/'
REP_HEALTH_URL = HEALTHY_API + 'rep-health/'
SUMMARY_URL = HEALTHY_API + 'dashboards/summary/'
AR_QUEUE_URL = HEALTHY_API + 'dashboards/ar-queue/'


# ── Authentication (401) ────────────────────────────────────────────────────

@pytest.mark.django_db
@pytest.mark.parametrize('url', [SNAPSHOTS_URL, LOADOUT_URL, REP_HEALTH_URL, SUMMARY_URL])
def test_unauthenticated_gets_401(api_client, url):
    assert api_client.get(url).status_code == 401


@pytest.mark.django_db
def test_unauthenticated_cannot_trigger_snapshot(api_client):
    resp = api_client.post(SNAPSHOTS_URL, {'pipeline': 'returns'}, format='json')
    assert resp.status_code == 401


# ── Capability gating (403) ─────────────────────────────────────────────────

@pytest.mark.django_db
def test_plain_user_gets_403_on_read(api_client, create_user, get_token_for_user):
    user = create_user('healthy_plain')  # no capabilities at all
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}')
    assert api_client.get(SNAPSHOTS_URL).status_code == 403


@pytest.mark.django_db
def test_viewer_can_read_but_not_write(auth, viewer):
    client = auth(viewer)
    assert client.get(SNAPSHOTS_URL).status_code == 200
    assert client.get(LOADOUT_URL).status_code == 200
    assert client.get(REP_HEALTH_URL).status_code == 200
    assert client.get(SUMMARY_URL).status_code == 200
    # viewers_group has healthy:view but NOT healthy:manage
    resp = client.post(SNAPSHOTS_URL, {'pipeline': 'returns'}, format='json')
    assert resp.status_code == 403


# ── Authorized reads (200) ──────────────────────────────────────────────────

@pytest.mark.django_db
def test_viewer_read_shapes(auth, viewer):
    client = auth(viewer)
    resp = client.get(SNAPSHOTS_URL)
    assert resp.status_code == 200
    body = resp.json()
    assert 'count' in body and 'results' in body
    assert body['count'] == 0

    summary = client.get(SUMMARY_URL).json()
    assert summary['pipelines'] == 5
    assert summary['snapshots'] == 0


@pytest.mark.django_db
def test_superuser_dashboards(auth, superuser):
    client = auth(superuser)
    assert client.get(SUMMARY_URL).status_code == 200
    assert client.get(AR_QUEUE_URL).status_code == 200


# ── Authorized writes (201) ─────────────────────────────────────────────────

@pytest.mark.django_db
def test_superuser_triggers_pipeline(auth, superuser):
    client = auth(superuser)
    resp = client.post(SNAPSHOTS_URL, {'pipeline': 'returns'}, format='json')
    assert resp.status_code == 201
    body = resp.json()
    assert body['snapshot']['status'] == 'done'
    assert body['dataset_version_id']
    assert body['turnkey_model_link_id']
    assert body['prediction_id']


@pytest.mark.django_db
def test_superuser_unknown_pipeline_400(auth, superuser):
    client = auth(superuser)
    resp = client.post(SNAPSHOTS_URL, {'pipeline': 'nope'}, format='json')
    assert resp.status_code == 400


@pytest.mark.django_db
def test_superuser_missing_payload_400(auth, superuser):
    client = auth(superuser)
    resp = client.post(SNAPSHOTS_URL, {}, format='json')
    assert resp.status_code == 400


# ── Load-out actuals (write) ────────────────────────────────────────────────

@pytest.mark.django_db
def test_superuser_posts_loadout_actuals(auth, superuser):
    from healthy.services import LoadoutService
    LoadoutService().generate_sheet(
        '2026-08-24', 'R-1042',
        line_items=[{'item_code': 'SKU-101', 'qty_recommended': 10}],
    )
    client = auth(superuser)
    resp = client.post(
        HEALTHY_API + 'loadout/2026-08-24/R-1042/actuals/',
        {'SKU-101': 8}, format='json',
    )
    assert resp.status_code == 200
    assert resp.json()['line_items'][0]['qty_actual'] == 8
