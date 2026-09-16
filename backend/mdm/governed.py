# File: mdm/governed.py
# Shared helpers for governed ReferenceValue lookups (ADR-0027).
#
# RULE_16: never create ReferenceValues here — resolve existing seeded rows only.

from __future__ import annotations

from django.utils import timezone

from .models import ReferenceSet, ReferenceValue


def resolve_reference_value(set_name: str, code_or_id, *, as_of=None, require_current=False):
    """Resolve a ReferenceValue by PK or code within ``set_name``.

    Returns ``None`` when ``code_or_id`` is blank/None.
    Raises ``ReferenceValue.DoesNotExist`` when the value cannot be resolved.
    Raises ``ReferenceSet.DoesNotExist`` when the set is missing.
    """
    if code_or_id is None or code_or_id == '':
        return None

    if isinstance(code_or_id, ReferenceValue):
        rv = code_or_id
        if rv.reference_set_id and rv.reference_set.name != set_name:
            # Lazy-load set name if needed
            set_obj = rv.reference_set
            if set_obj.name != set_name:
                raise ReferenceValue.DoesNotExist(
                    f"ReferenceValue pk={rv.pk} belongs to set {set_obj.name!r}, "
                    f"not {set_name!r}"
                )
        if require_current:
            _assert_current(set_name, rv, as_of=as_of)
        return rv

    rs = ReferenceSet.objects.filter(name=set_name).first()
    if rs is None:
        raise ReferenceSet.DoesNotExist(f"ReferenceSet {set_name!r} does not exist")

    if isinstance(code_or_id, int) or (
        isinstance(code_or_id, str) and code_or_id.isdigit()
    ):
        rv = ReferenceValue.objects.select_related('reference_set').get(
            pk=int(code_or_id), reference_set=rs,
        )
    else:
        rv = ReferenceValue.objects.select_related('reference_set').get(
            reference_set=rs, code=str(code_or_id),
        )

    if require_current:
        _assert_current(set_name, rv, as_of=as_of, rs=rs)
    return rv


def _assert_current(set_name, rv, *, as_of=None, rs=None):
    rs = rs or ReferenceSet.objects.filter(name=set_name).first()
    if rs is None:
        raise ReferenceSet.DoesNotExist(f"ReferenceSet {set_name!r} does not exist")
    target = as_of or timezone.localdate()
    if not rs.get_current_values(as_of=target).filter(pk=rv.pk).exists():
        raise ReferenceValue.DoesNotExist(
            f"{rv.code!r} is not a current value of reference set {set_name!r}"
        )
