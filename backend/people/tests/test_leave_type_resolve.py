"""Host leave_type resolution — synonyms → governed ReferenceValue codes."""
from django.test import TestCase

from people.leave_type_resolve import (
    ensure_leave_type_aliases,
    resolve_leave_type,
)
from people.tests.ref_helpers import ensure_ref


class LeaveTypeResolveTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for code, label in (
            ("emergency", "Emergency"),
            ("annual", "Annual"),
            ("sick", "Sick"),
        ):
            ensure_ref("leave_type", code, label)
        ensure_leave_type_aliases()

    def test_code_passthrough(self):
        rv = resolve_leave_type("emergency")
        assert rv is not None
        assert rv.code == "emergency"

    def test_arabic_arada_maps_to_emergency(self):
        rv = resolve_leave_type("عارضة")
        assert rv is not None
        assert rv.code == "emergency"

    def test_arabic_aadi_maps_to_annual(self):
        """Bare masculine عادي (live Agent brief) → annual."""
        for raw in ("عادي", "عادية", "إجازة عادي", "ordinary leave"):
            rv = resolve_leave_type(raw)
            assert rv is not None, raw
            assert rv.code == "annual", raw

    def test_find_in_text_bare_aadi(self):
        from mdm.reference_resolve import find_reference_in_text

        rv = find_reference_in_text(
            "leave_type",
            "اريد اجازة، ليوم واحد غدا، عادي.",
        )
        assert rv is not None
        assert rv.code == "annual"

    def test_unknown_returns_none(self):
        assert resolve_leave_type("not-a-real-type") is None

    def test_ensure_aliases_idempotent(self):
        n1 = ensure_leave_type_aliases()
        n2 = ensure_leave_type_aliases()
        assert n2 == 0
        assert n1 >= 0
