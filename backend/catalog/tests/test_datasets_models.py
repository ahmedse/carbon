"""Model-level tests for the Dataset Hub (Phase P1)."""
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from catalog.models import (
    DataContract, DataContractViolation, Dataset, DatasetAccessPolicy,
    DatasetVersion,
)


@pytest.mark.django_db
def test_dataset_slug_unique(module_a):
    Dataset.objects.create(name='First', slug='same-slug', module=module_a)
    with pytest.raises(IntegrityError):
        Dataset.objects.create(name='Second', slug='same-slug', module=module_a)


@pytest.mark.django_db
def test_dataset_defaults(module_a):
    ds = Dataset.objects.create(name='Payroll', slug='payroll', module=module_a)
    assert ds.status == 'draft'
    assert ds.classification == 'internal'
    assert ds.current_version is None
    assert ds.tags.count() == 0


@pytest.mark.django_db
def test_access_policy_requires_exactly_one_subject(module_a):
    ds = Dataset.objects.create(name='Payroll', slug='payroll', module=module_a)
    policy = DatasetAccessPolicy(dataset=ds, can_view=True)  # neither user nor group
    with pytest.raises(ValidationError):
        policy.clean()


@pytest.mark.django_db
def test_version_unique_number_per_dataset(module_a, make_dataset):
    ds = make_dataset(module_a, slug='payroll-unique')
    table1 = _table_for(ds, 1)
    table2 = _table_for(ds, 2)
    DatasetVersion.objects.create(
        dataset=ds, version_number=1, data_table=table1,
    )
    with pytest.raises(IntegrityError):
        DatasetVersion.objects.create(
            dataset=ds, version_number=1, data_table=table2,
        )


@pytest.mark.django_db
def test_contract_one_to_one_per_dataset(module_a, make_dataset):
    ds = make_dataset(module_a, slug='payroll-contract')
    DataContract.objects.create(dataset=ds, min_health_score=0.9)
    with pytest.raises(IntegrityError):
        DataContract.objects.create(dataset=ds, min_health_score=0.5)


@pytest.mark.django_db
def test_violation_ordering_newest_first(module_a, make_dataset):
    ds = make_dataset(module_a, slug='payroll-violations')
    table = _table_for(ds, 1)
    version = DatasetVersion.objects.create(dataset=ds, version_number=1, data_table=table)
    contract = DataContract.objects.create(dataset=ds)
    v1 = DataContractViolation.objects.create(
        contract=contract, dataset_version=version, violation_type='schema',
    )
    v2 = DataContractViolation.objects.create(
        contract=contract, dataset_version=version, violation_type='quality',
    )
    ids = list(DataContractViolation.objects.values_list('id', flat=True))
    assert ids == [v2.id, v1.id]  # -detected_at ordering


def _table_for(dataset, version_number):
    from dataschema.models import DataTable
    return DataTable.objects.create(
        name=f'{dataset.slug}_v{version_number}',
        title=dataset.name,
        module=dataset.module,
    )
