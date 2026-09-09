import pytest
from django.utils import timezone

from correspondence.models import CorrespondenceRegistry
from correspondence.registry import allocate_reference_no
from mdm.models import OrgUnit, ReferenceSet, ReferenceValue


@pytest.fixture
def reference_value(db):
    ref_set = ReferenceSet.objects.create(
        name='Correspondence Type', slug='correspondence-type',
    )
    return ReferenceValue.objects.create(
        reference_set=ref_set, code='leave_request', label='Leave Request',
    )


@pytest.fixture
def org_unit(db):
    return OrgUnit.objects.create(
        name='Engineering', slug='engineering', code='ENG', org_type='department',
    )


@pytest.mark.django_db
def test_sequential_allocations_increment(reference_value, org_unit):
    fmt = '{PREFIX}-{YEAR}-{SEQ:04d}'
    first = allocate_reference_no(numbering_format=fmt)
    second = allocate_reference_no(numbering_format=fmt)

    year = timezone.now().year
    assert first == f'CRS-{year}-0001'
    assert second == f'CRS-{year}-0002'
    assert first != second


@pytest.mark.django_db
def test_sequence_is_global_across_units_and_types(reference_value, org_unit):
    # A single global sequence means two different org units / corr types can
    # never produce the same reference number (the old per-unit counter bug).
    other = ReferenceValue.objects.create(
        reference_set=reference_value.reference_set,
        code='loan_request', label='Loan Request',
    )
    other_org = OrgUnit.objects.create(
        name='Finance', slug='finance', code='FIN', org_type='department',
    )
    fmt = '{PREFIX}-{YEAR}-{SEQ:04d}'
    first = allocate_reference_no(numbering_format=fmt)
    second = allocate_reference_no(numbering_format=fmt)

    year = timezone.now().year
    assert first == f'CRS-{year}-0001'
    assert second == f'CRS-{year}-0002'


@pytest.mark.django_db
def test_different_year_independent(reference_value, org_unit):
    year = timezone.now().year
    CorrespondenceRegistry.objects.create(year=year - 1, counter=7)

    first = allocate_reference_no(numbering_format='{PREFIX}-{YEAR}-{SEQ:04d}')
    assert first == f'CRS-{year}-0001'
