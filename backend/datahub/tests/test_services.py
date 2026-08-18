"""Service-level tests: health mirror + access policy resolution."""
import pytest

from catalog.models import AssetProfile
from datahub.models import DatasetAccessPolicy, DatasetVersion
from datahub.services import get_dataset_access, mirror_health_to_catalog


def _version_with_health(ds, score=0.95, detail=None, n=1):
    from dataschema.models import DataTable
    table = DataTable.objects.create(
        name=f'{ds.slug}_sv{n}', title=ds.name, module=ds.module,
    )
    return DatasetVersion.objects.create(
        dataset=ds, version_number=n, data_table=table,
        health_score=score,
        health_detail=detail or {
            'completeness': 0.98, 'validity': 0.95, 'freshness': 1.0,
        },
    )


@pytest.mark.django_db
def test_mirror_health_sets_asset_profile(module_a, make_dataset):
    ds = make_dataset(module_a, slug='payroll-mirror')
    version = _version_with_health(ds, score=0.95)

    mirror_health_to_catalog(version)

    ap = AssetProfile.objects.get(data_table=version.data_table)
    assert ap.quality_status == 'passing'  # 0.95 ≥ 0.9
    assert ap.quality_score == 95


@pytest.mark.django_db
def test_mirror_health_warning_and_failing(module_a, make_dataset):
    ds = make_dataset(module_a, slug='payroll-mirror2')
    warn = _version_with_health(ds, score=0.75, n=1)
    mirror_health_to_catalog(warn)
    assert AssetProfile.objects.get(
        data_table=warn.data_table).quality_status == 'warning'

    fail = _version_with_health(ds, score=0.5, n=2)
    mirror_health_to_catalog(fail)
    assert AssetProfile.objects.get(
        data_table=fail.data_table).quality_status == 'failing'


@pytest.mark.django_db
def test_get_dataset_access_policy_overrides(
        module_b, make_dataset, create_user):
    ds = make_dataset(module_b, slug='payroll-access-flags')
    user = create_user('policy_holder')

    # No policy and no module visibility → denied
    access = get_dataset_access(user, ds)
    assert access == {'can_view': False, 'can_ingest': False, 'can_approve': False}

    # Explicit policy grants view only
    DatasetAccessPolicy.objects.create(
        dataset=ds, user=user, can_view=True, can_ingest=False, can_approve=False,
    )
    access = get_dataset_access(user, ds)
    assert access['can_view'] is True
    assert access['can_ingest'] is False
    assert access['can_approve'] is False


@pytest.mark.django_db
def test_get_dataset_access_module_grant(
        module_a, make_dataset, create_user, create_scoped_role):
    ds = make_dataset(module_a, slug='payroll-access-module')
    user = create_user('module_holder')
    create_scoped_role(user, 'viewers_group', module=module_a)

    access = get_dataset_access(user, ds)
    assert access['can_view'] is True


@pytest.mark.django_db
def test_check_contract_no_contract_returns_empty(module_a, make_dataset):
    from datahub.services import check_contract
    ds = make_dataset(module_a, slug='payroll-nocontract')
    version = _version_with_health(ds)
    assert check_contract(version) == []
