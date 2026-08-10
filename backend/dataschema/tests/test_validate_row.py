"""
Level 1 validation tests for validate_row().

Tests: required, number type, number negative, number min/max, boolean,
select, multiselect, regex pattern, reference_set, date validation,
strict vs non-strict modes.
"""

import pytest
from datetime import date, datetime

from django.test import TestCase

from core.models import Module
from dataschema.models import DataTable, DataField
from dataschema.validators import validate_row


class ValidateRowUnitTests(TestCase):
    """Pure unit tests — no serializer, no DRF, just validate_row()."""

    def setUp(self):
        self.module = Module.objects.create(name="DQ Test Module")

    def _make_table(self, title="Test Table"):
        return DataTable.objects.create(
            title=title, name=title.lower().replace(' ', '_'), module=self.module
        )

    def _make_field(self, table, **kwargs):
        defaults = {
            'name': kwargs.pop('name', 'test_field'),
            'label': kwargs.pop('label', kwargs.get('name', 'Test Field')),
            'type': kwargs.pop('type', 'string'),
            'required': kwargs.pop('required', False),
            'options': kwargs.pop('options', None),
            'validation': kwargs.pop('validation', None),
        }
        defaults.update(kwargs)
        return DataField.objects.create(data_table=table, **defaults)

    # ── Happy path ──────────────────────────────────────────────────

    def test_valid_row_no_errors(self):
        table = self._make_table()
        fields = [
            self._make_field(table, name='name', type='string', required=True),
            self._make_field(table, name='age', type='number', required=True),
        ]
        errors = validate_row({'name': 'Ali', 'age': 30}, fields)
        assert errors == []

    def test_optional_field_missing_no_error(self):
        table = self._make_table()
        fields = [
            self._make_field(table, name='name', type='string', required=True),
            self._make_field(table, name='nickname', type='string', required=False),
        ]
        errors = validate_row({'name': 'Ali'}, fields)
        assert errors == []

    # ── Required ────────────────────────────────────────────────────

    def test_required_missing_key(self):
        table = self._make_table()
        fields = [self._make_field(table, name='name', type='string', required=True)]
        errors = validate_row({}, fields)
        assert len(errors) == 1
        assert errors[0]['code'] == 'required'
        assert errors[0]['field'] == 'name'

    def test_required_null_value(self):
        table = self._make_table()
        fields = [self._make_field(table, name='name', type='string', required=True)]
        errors = validate_row({'name': None}, fields)
        assert len(errors) == 1
        assert errors[0]['code'] == 'required'

    def test_required_empty_string(self):
        table = self._make_table()
        fields = [self._make_field(table, name='name', type='string', required=True)]
        errors = validate_row({'name': ''}, fields)
        assert len(errors) == 1
        assert errors[0]['code'] == 'required'

    def test_required_empty_list(self):
        table = self._make_table()
        fields = [
            self._make_field(table, name='tags', type='multiselect', required=True, options=[{'value': 'a'}])
        ]
        errors = validate_row({'tags': []}, fields)
        assert len(errors) == 1
        assert errors[0]['code'] == 'required'

    # ── Number type ─────────────────────────────────────────────────

    def test_number_type_reject_string(self):
        table = self._make_table()
        fields = [self._make_field(table, name='kwh', type='number')]
        errors = validate_row({'kwh': 'not_a_number'}, fields)
        assert len(errors) == 1
        assert errors[0]['code'] == 'invalid_type'

    def test_number_type_reject_bool(self):
        """bool is a subclass of int, must reject explicitly."""
        table = self._make_table()
        fields = [self._make_field(table, name='kwh', type='number')]
        errors = validate_row({'kwh': True}, fields)
        assert len(errors) == 1
        assert errors[0]['code'] == 'invalid_type'

    def test_number_negative(self):
        """Negative numbers are no longer banned at platform level; use DQ range rules."""
        table = self._make_table()
        fields = [self._make_field(table, name='kwh', type='number')]
        errors = validate_row({'kwh': -5}, fields)
        assert errors == []

    def test_number_zero_allowed(self):
        table = self._make_table()
        fields = [self._make_field(table, name='kwh', type='number')]
        errors = validate_row({'kwh': 0}, fields)
        assert errors == []

    def test_number_below_min(self):
        table = self._make_table()
        fields = [
            self._make_field(table, name='kwh', type='number', validation={'min': 10, 'max': 200000})
        ]
        errors = validate_row({'kwh': 5}, fields)
        assert len(errors) == 1
        assert errors[0]['code'] == 'below_min'

    def test_number_above_max(self):
        table = self._make_table()
        fields = [
            self._make_field(table, name='kwh', type='number', validation={'min': 0, 'max': 100})
        ]
        errors = validate_row({'kwh': 150}, fields)
        assert len(errors) == 1
        assert errors[0]['code'] == 'above_max'

    def test_number_within_range(self):
        table = self._make_table()
        fields = [
            self._make_field(table, name='kwh', type='number', validation={'min': 0, 'max': 100})
        ]
        errors = validate_row({'kwh': 50}, fields)
        assert errors == []

    # ── Boolean ─────────────────────────────────────────────────────

    def test_boolean_reject_string(self):
        table = self._make_table()
        fields = [self._make_field(table, name='active', type='boolean')]
        errors = validate_row({'active': 'yes'}, fields)
        assert len(errors) == 1
        assert errors[0]['code'] == 'invalid_type'

    def test_boolean_accept_true(self):
        table = self._make_table()
        fields = [self._make_field(table, name='active', type='boolean')]
        errors = validate_row({'active': True}, fields)
        assert errors == []

    def test_boolean_accept_false(self):
        table = self._make_table()
        fields = [self._make_field(table, name='active', type='boolean')]
        errors = validate_row({'active': False}, fields)
        assert errors == []

    # ── Select ──────────────────────────────────────────────────────

    def test_select_valid_option(self):
        table = self._make_table()
        fields = [
            self._make_field(table, name='color', type='select',
                             options=[{'value': 'red'}, {'value': 'blue'}])
        ]
        errors = validate_row({'color': 'red'}, fields)
        assert errors == []

    def test_select_not_in_options(self):
        table = self._make_table()
        fields = [
            self._make_field(table, name='color', type='select',
                             options=[{'value': 'red'}, {'value': 'blue'}])
        ]
        errors = validate_row({'color': 'green'}, fields)
        assert len(errors) == 1
        assert errors[0]['code'] == 'not_allowed'

    # ── Multiselect ─────────────────────────────────────────────────

    def test_multiselect_valid(self):
        table = self._make_table()
        fields = [
            self._make_field(table, name='tags', type='multiselect',
                             options=[{'value': 'a'}, {'value': 'b'}])
        ]
        errors = validate_row({'tags': ['a', 'b']}, fields)
        assert errors == []

    def test_multiselect_not_allowed(self):
        table = self._make_table()
        fields = [
            self._make_field(table, name='tags', type='multiselect',
                             options=[{'value': 'a'}, {'value': 'b'}])
        ]
        errors = validate_row({'tags': ['a', 'x']}, fields)
        assert len(errors) == 1
        assert errors[0]['code'] == 'not_allowed'

    def test_multiselect_not_list(self):
        table = self._make_table()
        fields = [
            self._make_field(table, name='tags', type='multiselect',
                             options=[{'value': 'a'}])
        ]
        errors = validate_row({'tags': 'a'}, fields)
        assert len(errors) == 1
        assert errors[0]['code'] == 'not_allowed'

    # ── Regex pattern ───────────────────────────────────────────────

    def test_regex_pattern_match(self):
        table = self._make_table()
        fields = [
            self._make_field(table, name='code', type='string',
                             validation={'pattern': r'^[A-Z]{2}-\d{4}$'})
        ]
        errors = validate_row({'code': 'AB-1234'}, fields)
        assert errors == []

    def test_regex_pattern_mismatch(self):
        table = self._make_table()
        fields = [
            self._make_field(table, name='code', type='string',
                             validation={'pattern': r'^[A-Z]{2}-\d{4}$'})
        ]
        errors = validate_row({'code': 'invalid'}, fields)
        assert len(errors) == 1
        assert errors[0]['code'] == 'pattern_mismatch'

    # ── Reference set ───────────────────────────────────────────────

    def test_reference_set_valid_value(self):
        from mdm.models import ReferenceSet, ReferenceValue
        table = self._make_table()
        ref_set = ReferenceSet.objects.create(name='Buildings', slug='buildings')
        ReferenceValue.objects.create(reference_set=ref_set, code='B401', label='Building 401')
        ReferenceValue.objects.create(reference_set=ref_set, code='B501', label='Building 501')

        field = self._make_field(table, name='building', type='string')
        field.reference_set = ref_set
        field.save()

        errors = validate_row({'building': 'B401'}, [field])
        assert errors == []

    def test_reference_set_invalid_value(self):
        from mdm.models import ReferenceSet, ReferenceValue
        table = self._make_table()
        ref_set = ReferenceSet.objects.create(name='Buildings', slug='buildings-ref')
        ReferenceValue.objects.create(reference_set=ref_set, code='B401', label='Building 401')

        field = self._make_field(table, name='building', type='string')
        field.reference_set = ref_set
        field.save()

        errors = validate_row({'building': 'B999'}, [field])
        assert len(errors) == 1
        assert errors[0]['code'] == 'not_in_reference'

    def test_reference_set_inactive_value_rejected(self):
        from mdm.models import ReferenceSet, ReferenceValue
        table = self._make_table()
        ref_set = ReferenceSet.objects.create(name='Old Codes', slug='old-codes')
        ReferenceValue.objects.create(
            reference_set=ref_set, code='OLD', label='Old Code', is_active=False
        )

        field = self._make_field(table, name='code', type='string')
        field.reference_set = ref_set
        field.save()

        errors = validate_row({'code': 'OLD'}, [field])
        assert len(errors) == 1
        assert errors[0]['code'] == 'not_in_reference'

    def test_reference_set_no_fk_no_error(self):
        """Field without reference_set should not trigger reference validation."""
        table = self._make_table()
        field = self._make_field(table, name='building', type='string')  # no reference_set
        errors = validate_row({'building': 'ANYTHING'}, [field])
        assert errors == []

    # ── Date ────────────────────────────────────────────────────────

    def test_date_valid_iso(self):
        table = self._make_table()
        fields = [self._make_field(table, name='month', type='date', required=True)]
        errors = validate_row({'month': '2026-01-15'}, fields)
        assert errors == []

    def test_date_valid_python_date_object(self):
        table = self._make_table()
        fields = [self._make_field(table, name='month', type='date')]
        errors = validate_row({'month': date(2026, 1, 15)}, fields)
        assert errors == []

    def test_date_valid_datetime_object(self):
        table = self._make_table()
        fields = [self._make_field(table, name='month', type='date')]
        errors = validate_row({'month': datetime(2026, 1, 15, 12, 0, 0)}, fields)
        assert errors == []

    def test_date_invalid_string(self):
        table = self._make_table()
        fields = [self._make_field(table, name='month', type='date')]
        errors = validate_row({'month': 'not-a-date'}, fields)
        assert len(errors) == 1
        assert errors[0]['code'] == 'invalid_date'

    def test_date_invalid_type(self):
        table = self._make_table()
        fields = [self._make_field(table, name='month', type='date')]
        errors = validate_row({'month': 42}, fields)
        assert len(errors) == 1
        assert errors[0]['code'] == 'invalid_date'

    # ── strict vs non-strict ────────────────────────────────────────

    def test_strict_returns_all_errors(self):
        table = self._make_table()
        fields = [
            self._make_field(table, name='kwh', type='number', required=True,
                             validation={'min': 0, 'max': 100}),
            self._make_field(table, name='color', type='select', required=True,
                             options=[{'value': 'red'}]),
        ]
        errors = validate_row({'kwh': -5, 'color': 'blue'}, fields, strict=True)
        # kwh=-5 with min=0 triggers 'below_min'; color='blue' triggers 'not_allowed' = 2 total
        assert len(errors) == 2
        codes = {e['code'] for e in errors}
        assert codes == {'below_min', 'not_allowed'}

    def test_non_strict_returns_first_only(self):
        table = self._make_table()
        # A field below its min value
        fields = [
            self._make_field(table, name='kwh', type='number', required=True,
                             validation={'min': 10, 'max': 100}),
        ]
        errors = validate_row({'kwh': -5}, fields, strict=False)
        assert len(errors) == 1
        # First error for kwh is 'below_min' (negative ban removed)
        assert errors[0]['code'] == 'below_min'

    # ── Edge cases ──────────────────────────────────────────────────

    def test_empty_fields_list(self):
        errors = validate_row({'anything': 'value'}, [])
        assert errors == []

    def test_no_matching_field_in_values(self):
        table = self._make_table()
        fields = [
            self._make_field(table, name='only_field', type='string', required=False)
        ]
        # Field not present in values, not required = no error
        errors = validate_row({}, fields)
        assert errors == []

    def test_null_value_skips_type_check(self):
        """If value is None and field is not required, skip type checks."""
        table = self._make_table()
        fields = [
            self._make_field(table, name='kwh', type='number', required=False,
                             validation={'min': 0, 'max': 100})
        ]
        errors = validate_row({'kwh': None}, fields)
        assert errors == []


class ValidateRowViaSerializerTests(TestCase):
    """Integration: ensure DataRowSerializer still works after refactor."""

    def setUp(self):
        self.module = Module.objects.create(name="Serializer Test Module")

    def test_serializer_validation_still_works(self):
        """The existing validation tests should still pass through the serializer."""
        from dataschema.serializers import DataRowSerializer

        table = DataTable.objects.create(
            title='Ser Test', name='ser_test', module=self.module
        )
        DataField.objects.create(data_table=table, name='name', label='Name',
                                 type='string', required=True)
        DataField.objects.create(data_table=table, name='age', label='Age',
                                 type='number', required=True)

        # Valid
        s = DataRowSerializer(data={'data_table': table.id, 'values': {'name': 'Ali', 'age': 30}})
        assert s.is_valid(), s.errors

        # Invalid — missing required
        s2 = DataRowSerializer(data={'data_table': table.id, 'values': {'name': 'Ali'}})
        assert not s2.is_valid()
        assert 'age' in s2.errors

        # Invalid — wrong type
        s3 = DataRowSerializer(data={'data_table': table.id, 'values': {'name': 'Ali', 'age': 'old'}})
        assert not s3.is_valid()
        assert 'age' in s3.errors


class ValidateRowViaServiceTests(TestCase):
    """Integration: ensure SchemaValidationService still works after refactor."""

    def setUp(self):
        self.module = Module.objects.create(name="Service Test Module")

    def test_validate_field_backward_compat(self):
        from dataschema.services import SchemaValidationService

        table = DataTable.objects.create(
            title='Svc Test', name='svc_test', module=self.module
        )
        num_field = DataField.objects.create(
            data_table=table, name='kwh', label='kWh', type='number'
        )

        # Valid
        assert SchemaValidationService.validate_field(num_field, 100) is None

        # Invalid
        with pytest.raises(ValueError) as exc:
            SchemaValidationService.validate_field(num_field, 'abc')
        assert 'kwh' in exc.value.args[0]

    def test_validate_field_select_backward_compat(self):
        from dataschema.services import SchemaValidationService

        table = DataTable.objects.create(
            title='Svc Test 2', name='svc_test_2', module=self.module
        )
        sel_field = DataField.objects.create(
            data_table=table, name='color', label='Color', type='select',
            options=[{'value': 'red'}, {'value': 'blue'}]
        )

        assert SchemaValidationService.validate_field(sel_field, 'red') is None

        with pytest.raises(ValueError) as exc:
            SchemaValidationService.validate_field(sel_field, 'green')
        assert 'color' in exc.value.args[0]
