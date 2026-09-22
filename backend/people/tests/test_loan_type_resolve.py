"""Loan-type alias ensure + Arabic brief grounding."""
import pytest
from mdm.models import ReferenceSet, ReferenceValue


@pytest.mark.django_db
def test_ensure_loan_type_aliases_grounds_tawarie_brief():
    from people.loan_type_resolve import ensure_loan_type_aliases
    from mdm.reference_resolve import find_reference_in_text
    from ai.write_slots import fill_write_body
    from ai.engine.cognition.plan.process_dial import _LOAN_SLOTS

    rs, _ = ReferenceSet.objects.get_or_create(
        name="loan_type",
        defaults={"slug": "loan-type", "description": "Loan types"},
    )
    ReferenceValue.objects.update_or_create(
        reference_set=rs,
        code="emergency",
        defaults={
            "label": "Emergency Loan",
            "is_active": True,
            "metadata": {"label_ar": "سلفة طارئة"},
        },
    )
    assert ensure_loan_type_aliases() >= 1
    assert ensure_loan_type_aliases() == 0  # idempotent

    hit = find_reference_in_text(
        "loan_type", "أريد قرض طوارئ 5000 لمدة 12 شهر غدا",
    )
    assert hit is not None
    assert hit.code == "emergency"

    body = fill_write_body(
        {},
        slots=_LOAN_SLOTS,
        text="أريد قرض طوارئ 5000 لمدة 12 شهر غدا",
    )
    assert body.get("loan_type") == "emergency"
    assert body.get("principal") == 5000.0
    assert body.get("term_months") == 12


@pytest.mark.django_db
def test_label_ar_is_a_needle_without_aliases():
    from mdm.reference_resolve import find_reference_in_text

    rs, _ = ReferenceSet.objects.get_or_create(
        name="loan_type",
        defaults={"slug": "loan-type", "description": "Loan types"},
    )
    ReferenceValue.objects.update_or_create(
        reference_set=rs,
        code="housing",
        defaults={
            "label": "Housing Loan",
            "is_active": True,
            "metadata": {"label_ar": "سلفة سكن"},
        },
    )
    hit = find_reference_in_text("loan_type", "أريد سلفة سكن")
    assert hit is not None
    assert hit.code == "housing"
