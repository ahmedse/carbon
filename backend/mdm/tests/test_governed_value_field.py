# mdm/tests/test_governed_value_field.py
# NSR-7B — GovernedValueField read/write contract (ADR-0027).

import pytest
from rest_framework.exceptions import ValidationError

from mdm.models import ReferenceSet, ReferenceValue
from mdm.serializers import GovernedValueField


@pytest.fixture
def nationality_set(db):
    rs = ReferenceSet.objects.create(
        name='nationality', slug='nationality',
        is_active=True, lifecycle_state='active',
    )
    kw = ReferenceValue.objects.create(
        reference_set=rs, code='KW', label='Kuwaiti', is_active=True,
    )
    eg = ReferenceValue.objects.create(
        reference_set=rs, code='EG', label='Egyptian', is_active=True,
    )
    return rs, kw, eg


@pytest.mark.django_db
def test_governed_value_field_read_nested(nationality_set):
    _, kw, _ = nationality_set
    field = GovernedValueField(set_name='nationality')
    assert field.to_representation(kw) == {
        'id': kw.pk, 'code': 'KW', 'label': 'Kuwaiti', 'set': 'nationality',
    }
    assert field.to_representation(None) is None


@pytest.mark.django_db
def test_governed_value_field_write_by_code_and_id(nationality_set):
    _, kw, eg = nationality_set
    field = GovernedValueField(set_name='nationality')
    assert field.to_internal_value('EG').pk == eg.pk
    assert field.to_internal_value(kw.pk).pk == kw.pk
    assert field.to_internal_value({'code': 'KW'}).pk == kw.pk
    assert field.to_internal_value(None) is None
    assert field.to_internal_value('') is None


@pytest.mark.django_db
def test_governed_value_field_rejects_unknown(nationality_set):
    field = GovernedValueField(set_name='nationality')
    with pytest.raises(ValidationError):
        field.to_internal_value('XX')
