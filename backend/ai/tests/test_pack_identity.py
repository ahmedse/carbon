"""The identity person-number label follows the bound pack."""
from __future__ import annotations

from ai.engine.cognition.context_pack import _user_identity_lines
from ai.engine.pack_vocab import bind_pack

_ROW = {
    "full_name": "Bilagot Panta Suerte",
    "employee_no": "1067",
    "job_title": "Coiled Tubing",
}

_INFO = {
    "username": "emp_1067",
    "display_name": "Bilagot Panta Suerte",
    "employee": _ROW,
}


def test_nibras_identity_still_names_the_number():
    with bind_pack("nibras"):
        text = "\n".join(_user_identity_lines(_INFO))
    assert "employee_no=1067" in text
    assert "Employee:" in text


def test_medicine_identity_omits_the_number_label():
    with bind_pack("aast-med"):
        text = "\n".join(_user_identity_lines(_INFO))
    assert "employee_no" not in text
    assert "username=emp_1067" in text


def test_direct_row_without_a_pack_field_has_no_number_label():
    from ai.engine.cognition.context_pack import person_identity_bits

    with bind_pack("aast-med"):
        bits = person_identity_bits(_ROW)
    assert all("employee_no" not in str(bit) for bit in bits)
    assert all("=1067" not in str(bit) for bit in bits)


def test_empty_person_key_does_not_read_the_blank_slot():
    stuffed = dict(_INFO)
    stuffed[""] = _ROW
    with bind_pack("aast-med"):
        text = "\n".join(_user_identity_lines(stuffed))
    assert "employee_no" not in text
    assert "=1067" not in text
