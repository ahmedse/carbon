"""Numeric grounding survives legitimate reformatting (2026-10-03 nibras cadence).

The payload is raw host data; the written summary is prose. The same figure
can arrive as ``74965.975`` and be written ``74,965.975``, or as western
digits and be written ``٧٤٬٩٦٥٫٩٧٥``. Grounding compares the value, not the
spelling, so a reformatted figure grounds — while a figure the payload never
carried (a derived sum, a made-up count) is still rejected. This is the
ADR-0049 P6 / IRP-5 contract, not a relaxation of it.
"""
from __future__ import annotations

import json

from ai.engine.cognition.turn.grounding import (
    strip_ungrounded_numbers,
    ungrounded_numbers,
)

#: A real analyze_committed_pay payload (nibras Sept 2026), trimmed to four
#: org units. Totals are strings; the writer restates them with separators.
PAY = {
    "period_end": "2026-09-30",
    "dimension": "org_unit",
    "line_type": "net",
    "status": "committed",
    "omitted": 0,
    "breakdown": [
        {"label": "Drilling", "headcount": 133, "total": "74965.975"},
        {"label": "Coiled Tubing", "headcount": 95, "total": "49830.413"},
        {"label": "CEO Office", "headcount": 14, "total": "27085.449"},
        {"label": "Business Development", "headcount": 1, "total": "3070.856"},
    ],
}
WRAP = {"status_code": 200, "data": PAY}


def test_comma_grouped_totals_ground():
    prose = (
        "Drilling بإجمالي 74,965.975، تليها Coiled Tubing بإجمالي 49,830.413، "
        "ثم CEO Office بإجمالي 27,085.449."
    )
    assert ungrounded_numbers(prose, [WRAP]) == []
    assert ungrounded_numbers(prose, [json.dumps(WRAP)]) == []


def test_arabic_indic_and_arabic_separators_ground():
    prose = "Drilling بإجمالي ٧٤٬٩٦٥٫٩٧٥ وعدد الموظفين ١٣٣."
    assert ungrounded_numbers(prose, [WRAP]) == []


def test_integer_and_trailing_zero_equivalents_ground():
    assert ungrounded_numbers("16,800", [{"total": "16800.000"}]) == []
    assert ungrounded_numbers("16800.00", [{"total": 16800}]) == []
    assert ungrounded_numbers("1,043", [{"n": 1043}]) == []


def test_percent_and_fraction_are_the_same_figure():
    assert ungrounded_numbers("15%", [{"share": 0.15}]) == []
    assert ungrounded_numbers("0.15", [{"share": "15%"}]) == []


def test_rounding_is_only_allowed_where_the_payload_implies_it():
    # Payload carries one decimal, so an integer restatement is the same figure.
    assert ungrounded_numbers("16800", [{"total": "16800.4"}]) == []
    # ...but a spurious round-up is not that figure.
    assert ungrounded_numbers("16801", [{"total": "16800.4"}]) == ["16801"]
    # A sub-unit rate is never rounded up to the integer 1.
    assert ungrounded_numbers("1", [{"rate": 0.15}]) == ["1"]


def test_a_genuinely_absent_figure_is_still_rejected():
    # A derived grand total is not a payload field.
    assert ungrounded_numbers("الإجمالي العام 151,881.837", [WRAP]) == ["151,881.837"]
    # Invented counts are rejected.
    assert ungrounded_numbers("About 90 percent are in one site.", [WRAP]) == ["90"]
    assert ungrounded_numbers("There are 9999 people.", [WRAP]) == ["9999"]
    # A near-miss (one digit off) is not the payload figure.
    assert ungrounded_numbers("74,965.976", [{"total": "74965.975"}]) == ["74,965.976"]


def test_strip_drops_only_the_ungrounded_figure():
    text = "Drilling 74,965.975 and an invented 9999 total"
    assert strip_ungrounded_numbers(text, [WRAP]) == "Drilling 74,965.975 and an invented total"
