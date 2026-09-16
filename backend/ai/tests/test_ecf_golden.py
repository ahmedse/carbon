"""ECF-0 — Golden regression harness seeded from real failure transcript (2026-09-05 → 2026-09-16).

All cases are marked xfail(strict=False) because ECF code doesn't exist yet.
They document the BASELINE of broken behaviour. As ECF phases land they flip to xpass.

To run:
    cd backend && ../.venv/bin/python -m pytest ai/tests/test_ecf_golden.py -v
"""
from __future__ import annotations

import pytest
from dataclasses import dataclass, field


@dataclass
class GoldenCase:
    id: str
    query: str
    must_find: bool          # True → a record must resolve; False → grounded-none required
    employee_no: str | None  # expected employee_no when must_find=True
    invariants: list[str] = field(default_factory=list)


GOLDEN_CASES: list[GoldenCase] = [
    GoldenCase(
        id="lookup_salman_en_full",
        query="Salman Ali Hussain Zakareya",
        must_find=False,
        employee_no=None,
        invariants=[
            "grounded-none must include searched_total (e.g. 'searched 530 of 530')",
            "must NOT emit 'no such employee' without count — that is a false confident negative",
            "must NOT hallucinate a record (e.g. must not map this to Wellie Bonglay Eslit)",
        ],
    ),
    GoldenCase(
        id="lookup_salman_ar",
        query="سلمان علي زكريا",
        must_find=False,
        employee_no=None,
        invariants=[
            "Arabic input → Arabic response language",
            "grounded-none with searched_total",
            "must not claim the person was found",
        ],
    ),
    GoldenCase(
        id="lookup_salman_partial",
        query="salman zakareya",
        must_find=False,
        employee_no=None,
        invariants=[
            "partial match attempt before final none",
            "no hallucination of a random employee",
        ],
    ),
    GoldenCase(
        id="lookup_employee_no_1046",
        query="1046",  # this is employee_no, not a PK
        must_find=True,
        employee_no="1046",
        invariants=[
            "must resolve via employee_no field, not only PK",
            "must NOT return 'employee not found'",
            "response contains name Sanavulla Shaik",
        ],
    ),
    GoldenCase(
        id="lookup_employee_no_1021",
        query="1021",  # employee_no
        must_find=True,
        employee_no="1021",
        invariants=[
            "must resolve via employee_no",
            "must NOT return 'no matching employee found'",
            "response contains name Abrar Alam Azeemullah Ansari",
        ],
    ),
    GoldenCase(
        id="lookup_employee_no_2403",
        query="2403",  # employee_no — user insisted this exists
        must_find=False,  # may not exist; but must not hallucinate
        employee_no=None,
        invariants=[
            "if not found: searched_total must be present",
            "must not map to a random employee (hallucination forbidden)",
        ],
    ),
    GoldenCase(
        id="lookup_reena_sekaran",
        query="Reena Sekaran",
        must_find=True,
        employee_no="1009",
        invariants=[
            "name search returns correct employee_no 1009",
            "response shows position title, not numeric id 170",
        ],
    ),
    GoldenCase(
        id="lookup_ar_موارد_partial",
        query="عبرار عالم",  # partial Arabic approximation of Abrar Alam
        must_find=True,
        employee_no="1021",
        invariants=[
            "Arabic search reaches employee in rows > 100 of list endpoint",
            "normalisation handles hamza/diacritic variants",
        ],
    ),
    GoldenCase(
        id="existence_over_truncated",
        query="is there an employee named Salman?",
        must_find=False,
        employee_no=None,
        invariants=[
            "CONTRACT: must NOT claim 'no such employee' without 'searched N of N'",
            "truncated source cannot back a universal existence claim",
            "response must acknowledge complete scan was done or explain limitation",
        ],
    ),
    GoldenCase(
        id="headcount_stable",
        query="كم عدد الموظفين",
        must_find=False,
        employee_no=None,
        invariants=[
            "number matches total active employees in DB",
            "consistent across repeated calls — not 529 one time and 530 another",
            "uses analyze_employees total (server-side count), not len(page)",
        ],
    ),
    GoldenCase(
        id="kuwaiti_count_stable",
        query="كم كويتي موظف",
        must_find=False,
        employee_no=None,
        invariants=[
            "single canonical definition used — nationality_code='KW'",
            "does not return 55 one time and 5 another time",
            "cites which field/definition was used",
        ],
    ),
    GoldenCase(
        id="position_label",
        query="tell me about Reena Sekaran",
        must_find=True,
        employee_no="1009",
        invariants=[
            "position shown as human label (e.g. 'CT Senior Operator'), not numeric id '170'",
            "org_unit shown as name, not numeric id",
        ],
    ),
    GoldenCase(
        id="arabic_in_arabic_out",
        query="كم موظف لدينا",
        must_find=False,
        employee_no=None,
        invariants=[
            "response language is Arabic",
            "no English 'Key takeaways' section inside an Arabic answer",
        ],
    ),
]


# ── Baseline documentation tests ─────────────────────────────────────────────
# These run offline (no LLM, no DB) and document expected invariants.
# They will be expanded into live assertions once ECF is wired.

class TestGoldenCasesAreDeclared:
    """Sanity: all required cases are present and well-formed."""

    def test_all_required_ids_present(self):
        ids = {c.id for c in GOLDEN_CASES}
        required = {
            "lookup_salman_en_full", "lookup_salman_ar", "lookup_salman_partial",
            "lookup_employee_no_1046", "lookup_employee_no_1021",
            "lookup_reena_sekaran", "existence_over_truncated",
            "headcount_stable", "kuwaiti_count_stable",
            "position_label", "arabic_in_arabic_out",
        }
        assert required.issubset(ids), f"Missing cases: {required - ids}"

    def test_each_case_has_invariants(self):
        for case in GOLDEN_CASES:
            assert case.invariants, f"Case {case.id} has no invariants"

    def test_must_find_cases_have_employee_no(self):
        for case in GOLDEN_CASES:
            if case.must_find:
                assert case.employee_no is not None, (
                    f"Case {case.id} must_find=True but no expected employee_no"
                )


# ── Live assertion stubs (xfail until ECF is wired) ──────────────────────────

@pytest.mark.xfail(reason="ECF-0 baseline — resolve_entity not yet implemented", strict=False)
class TestEntityResolutionLive:
    """These will flip to xpass as ECF phases ECF-2 and ECF-4 land."""

    @pytest.mark.parametrize("case", [c for c in GOLDEN_CASES if not c.must_find and c.id.startswith("lookup_")], ids=[c.id for c in GOLDEN_CASES if not c.must_find and c.id.startswith("lookup_")])
    def test_grounded_none_includes_total(self, case):
        """Grounded-none responses must carry searched_total, never a bare 'not found'."""
        # ECF-2 resolve() → ResolveResult.searched_total > 0
        pytest.skip("ECF-2 not yet implemented")

    @pytest.mark.parametrize("case", [c for c in GOLDEN_CASES if c.must_find], ids=[c.id for c in GOLDEN_CASES if c.must_find])
    def test_must_find_resolves(self, case):
        """Employee lookup must succeed for known records."""
        # ECF-4 resolve_entity tool → action="match", record.employee_no == case.employee_no
        pytest.skip("ECF-4 not yet implemented")

    def test_existence_claim_never_over_truncated_source(self):
        """Contract: truncated source + existence claim = forbidden."""
        # ECF-3 contract guard → rewrite
        pytest.skip("ECF-3 not yet implemented")

    def test_headcount_stable_across_calls(self):
        """Same question → same number (canonical metric)."""
        # ECF-6 aggregate_entity → canonical "headcount" metric
        pytest.skip("ECF-6 not yet implemented")

    def test_kuwaiti_canonical_definition(self):
        """Kuwaiti count uses nationality_code='KW', never the kuwaitization boolean."""
        # ECF-6 aggregate_entity → canonical "kuwaiti" metric
        pytest.skip("ECF-6 not yet implemented")

    def test_position_shown_as_label_not_id(self):
        """Entity detail response: position title, not numeric FK id."""
        # ECF-3 label-resolution contract
        pytest.skip("ECF-3 not yet implemented")
