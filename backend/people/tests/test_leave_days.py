"""Unit tests for leave day JSON normalization."""

from decimal import Decimal

from people.leave_days import LeaveDaysField, leave_days_json


def test_leave_days_json_whole_as_int():
    assert leave_days_json(Decimal('30.00')) == 30
    assert leave_days_json('7.00') == 7
    assert leave_days_json(0) == 0
    assert isinstance(leave_days_json(Decimal('1.00')), int)


def test_leave_days_json_fractional_as_float():
    assert leave_days_json(Decimal('0.50')) == 0.5
    assert leave_days_json('1.25') == 1.25


def test_leave_days_field_round_trip():
    field = LeaveDaysField()
    assert field.to_representation(Decimal('30.00')) == 30
    assert field.to_internal_value('1.5') == Decimal('1.50')
    assert field.to_representation(Decimal('1.50')) == 1.5
