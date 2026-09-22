"""Leave day quantities for API responses.

Stored as ``Decimal(…, decimal_places=2)`` so half-days remain possible, but
ESS/HR UIs should not show ``30.00`` for whole days. Serialize whole values as
JSON ints and fractional values as JSON numbers (no trailing zeros).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from rest_framework import serializers

__all__ = ['LeaveDaysField', 'leave_days_json']

_QUANT = Decimal('0.01')


def leave_days_json(value):
    """Normalize a leave-day quantity for JSON (int when whole, else float)."""
    if value is None:
        return None
    try:
        d = Decimal(str(value)).quantize(_QUANT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return None
    if d == d.to_integral_value():
        return int(d)
    return float(d)


class LeaveDaysField(serializers.Field):
    """Read/write leave days: accept number/string; emit int or float."""

    default_error_messages = {
        'invalid': 'A valid number is required.',
        'negative': 'Must be greater than or equal to zero.',
    }

    def to_internal_value(self, data):
        if data is None and self.allow_null:
            return None
        try:
            d = Decimal(str(data)).quantize(_QUANT, rounding=ROUND_HALF_UP)
        except (InvalidOperation, TypeError, ValueError):
            self.fail('invalid')
        if d < 0:
            self.fail('negative')
        return d

    def to_representation(self, value):
        return leave_days_json(value)
