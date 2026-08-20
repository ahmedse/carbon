"""CBAC / capability gating + module isolation tests for the Dataset Hub."""
import pytest

from catalog.models import Dataset, DatasetAccessPolicy

DATASETS_URL = '/carbon-api/catalog/datasets/'
INGEST_URL = '/carbon-api/catalog/datasets/{id}/ingest/erp/'
APPROVE_URL = '/carbon-api/catalog/datasets/{id}/versions/{vid}/approve/'


@pytest.fixture
def plain_user(create_user):
    """Authenticated user with NO capabilities (no groups, not staff)."""
    return create_user('plain_user')


def _auth(client, token):
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return client


# ── Authentication ──────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_unauthenticated_gets_401(api_client, module_a):
    assert api_client.get(DATASETS_URL).status_code == 401


@pytest.mark.django_db
def test_ingest_requires_authentication(api_client, module_a, make_dataset):
    ds = make_dataset(module_a)
    url = INGEST_URL.format(id=ds.id)
    assert api_client.post(url, {'rows': []}, format='json').status_code == 401


# ── Capability gating ───────────────────────────────────────────────────────

@pytest.mark.django_db
def test_create_dataset_module_scope_and_403_for_unapproved(
        api_client, create_user, get_token_for_user, module_a, domain):
    """Named test #1 — module scope required; unapproved user gets 403."""
    ds = Dataset.objects.create(
        name='Payroll', slug='payroll-cbac-1', module=module_a, domain=domain,
    )
    assert ds.module == module_a

    user = create_user('unapproved_user')  # no capabilities at all
    client = _auth(api_client, get_token_for_user(user))
    resp = client.post(DATASETS_URL, {
        'name': 'Payroll II', 'slug': 'payroll-ii',
        'module': module_a.id,
    }, format='json')
    assert resp.status_code == 403


@pytest.mark.django_db
def test_create_dataset_requires_manage_capability(
        api_client, create_user, get_token_for_user, module_a):
    user = create_user('no_manage')  # plain user
    client = _auth(api_client, get_token_for_user(user))
    resp = client.post(DATASETS_URL, {
        'name': 'Payroll', 'slug': 'payroll-x', 'module': module_a.id,
    }, format='json')
    assert resp.status_code == 403


@pytest.mark.django_db
def test_ingest_requires_ingest_capability(
        api_client, create_user, create_scoped_role, get_token_for_user,
        module_a, make_dataset):
    """A datahub:view-only user may list datasets but NOT ingest."""
    ds = make_dataset(module_a, slug='payroll-viewer')
    viewer = create_user('viewer')
    # viewers_group → datahub:view only (no datahub:ingest)
    create_scoped_role(viewer, 'viewers_group', module=module_a)

    client = _auth(api_client, get_token_for_user(viewer))
    assert client.get(DATASETS_URL).status_code == 200  # can view
    resp = client.post(INGEST_URL.format(id=ds.id), {
        'rows': [{'name': 'Amina', 'age': 30}], 'source_ref': 'erp',
    }, format='json')
    assert resp.status_code == 403


@pytest.mark.django_db
def test_approve_requires_approve_capability(
        api_client, create_user, create_scoped_role, get_token_for_user,
        module_a, make_dataset):
    ds = make_dataset(module_a, slug='payroll-approve-gate')
    table = _make_table(ds, 1)
    from catalog.models import DatasetVersion
    version = DatasetVersion.objects.create(dataset=ds, version_number=1, data_table=table)

    viewer = create_user('viewer2')
    create_scoped_role(viewer, 'viewers_group', module=module_a)
    client = _auth(api_client, get_token_for_user(viewer))
    resp = client.post(APPROVE_URL.format(id=ds.id, vid=version.id))
    assert resp.status_code == 403


@pytest.mark.django_db
def test_manage_capability_allows_writes(
        api_client, create_user, create_scoped_role, get_token_for_user, module_a):
    """A global datahub_lead (capability datahub:manage) can create datasets."""
    lead = create_user('hub_lead')
    create_scoped_role(lead, 'datahub_lead')  # global scope
    client = _auth(api_client, get_token_for_user(lead))
    resp = client.post(DATASETS_URL, {
        'name': 'Payroll', 'slug': 'payroll-lead',
        'module': module_a.id,
    }, format='json')
    assert resp.status_code == 201


# ── Module isolation (named test #6) ───────────────────────────────────────

@pytest.mark.django_db
def test_cbac_module_isolation(
        api_client, create_user, create_scoped_role, get_token_for_user,
        module_a, module_b, make_dataset):
    """Named test #6 — a user scoped to module A cannot see module B datasets."""
    ds_a = make_dataset(module_a, slug='payroll-a')
    ds_b = make_dataset(module_b, slug='payroll-b')

    user = create_user('module_a_user')
    create_scoped_role(user, 'viewers_group', module=module_a)
    client = _auth(api_client, get_token_for_user(user))

    resp = client.get(DATASETS_URL)
    assert resp.status_code == 200
    ids = [item['id'] for item in resp.json()]
    assert str(ds_a.id) in ids
    assert str(ds_b.id) not in ids

    # Direct detail access to the other module's dataset → 404 (scoped queryset)
    assert client.get(f"{DATASETS_URL}{ds_b.id}/").status_code == 404


@pytest.mark.django_db
def test_module_scoped_write_denied_outside_scope(
        api_client, create_user, create_scoped_role, get_token_for_user,
        module_a, module_b):
    """A module-A-scoped datahub_lead cannot create a dataset in module B."""
    lead = create_user('scoped_lead')
    create_scoped_role(lead, 'datahub_lead', module=module_a)
    client = _auth(api_client, get_token_for_user(lead))
    resp = client.post(DATASETS_URL, {
        'name': 'Payroll B', 'slug': 'payroll-b-write',
        'module': module_b.id,
    }, format='json')
    assert resp.status_code == 403


# ── Access policy override (named test #7) ─────────────────────────────────

@pytest.mark.django_db
def test_access_policy_override(
        api_client, create_user, create_scoped_role, get_token_for_user,
        module_a, module_b, make_dataset):
    """Named test #7 — explicit DatasetAccessPolicy overrides module ScopedRole.

    The user has NO module-B visibility, but a per-dataset policy grants view.
    """
    ds_b = make_dataset(module_b, slug='payroll-b-policy')

    # No policy yet → hidden
    user = create_user('policy_user')
    create_scoped_role(user, 'viewers_group', module=module_a)
    client = _auth(api_client, get_token_for_user(user))
    resp = client.get(DATASETS_URL)
    assert str(ds_b.id) not in [i['id'] for i in resp.json()]

    # Grant an explicit per-dataset policy → now visible
    DatasetAccessPolicy.objects.create(dataset=ds_b, user=user, can_view=True)
    resp = client.get(DATASETS_URL)
    ids = [i['id'] for i in resp.json()]
    assert str(ds_b.id) in ids

    # Detail fetch works too
    assert client.get(f"{DATASETS_URL}{ds_b.id}/").status_code == 200


@pytest.mark.django_db
def test_access_policy_group_grants_view(
        api_client, create_user, get_token_for_user, module_b, make_dataset):
    ds_b = make_dataset(module_b, slug='payroll-b-group')
    user = create_user('group_policy_user')  # no module-B visibility
    from django.contrib.auth.models import Group
    group = Group.objects.create(name='hub_special')
    user.groups.add(group)
    client = _auth(api_client, get_token_for_user(user))
    assert str(ds_b.id) not in [i['id'] for i in client.get(DATASETS_URL).json()]

    DatasetAccessPolicy.objects.create(dataset=ds_b, group=group, can_view=True)
    ids = [i['id'] for i in client.get(DATASETS_URL).json()]
    assert str(ds_b.id) in ids


def _make_table(dataset, version_number):
    from dataschema.models import DataTable
    return DataTable.objects.create(
        name=f'{dataset.slug}_t{version_number}',
        title=dataset.name,
        module=dataset.module,
    )
