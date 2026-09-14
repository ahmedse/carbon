"""Golden dataset for the deterministic answer-quality eval harness.

This module declares two things:

1. ``GOLDEN_QUERIES`` — the canonical natural-language questions whose answers
   the Pulse pipeline must get right.  Each entry records the *expected* tool
   and dimension plus a list of human-readable invariants that the live judge
   harness (``test_answer_quality_live.py``) will assert against the rendered
   answer.

2. ``GOLDEN_DATASET`` — a declarative seed spec for a KNOWN employee population.
   The builder fixture in ``test_answer_quality_eval.py`` materialises it, so
   every assertion below is on exact counts, never "≥ 1".

The population is deliberately small and self-evident:

* Gender:     6 male (2 of them seeded as raw "M"), 2 female (1 seeded "F"),
              1 blank.  ⇒ breakdown = male 6 / female 2 / (blank) 1.
              blank = 1/9 = 11.1% < 50% ⇒ the missing-data caveat must NOT fire.
              Synonym merge: "M" → "male" and "F" → "female" (merged_from).
* Position:   Engineer ×5, Supervisor ×2, Floorman ×2 (FK label resolution).
* is_active:  7 True, 2 False ⇒ True = 7/9 = 77.8% dominant ⇒ chart "bar".
* Org mix:    two org units (operations ×5, engineering ×4) exercise RULE_12
              org scoping via ``_people_scope``.

Total employees = 9.
"""

from __future__ import annotations

# ── Golden queries ──────────────────────────────────────────────────────────
#
# "How many employees do we have?" is served by ``analyze_employees`` WITHOUT a
# dimension — the tool's ``total`` field is the headcount (server-computed, never
# a capped page).  We document that choice here rather than using ``list_employees``
# so the invariant ("count matches DB") is always checked against the aggregate,
# not a truncated list.

GOLDEN_QUERIES: list[dict] = [
    {
        "question": "What is the gender distribution of our employees?",
        "expected_tool": "analyze_employees",
        "expected_dimension": "gender",
        "invariants": [
            "no raw PK labels",
            "blank disclosed if >50%",
            "chart type is bar or pie per data shape",
        ],
    },
    {
        "question": "What is the breakdown of employees by position?",
        "expected_tool": "analyze_employees",
        "expected_dimension": "position",
        "invariants": ["labels are position titles not IDs"],
    },
    {
        "question": "How many employees do we have?",
        # headcount = analyze_employees total (no GROUP BY dimension).
        "expected_tool": "analyze_employees",
        "expected_dimension": None,
        "invariants": ["count matches DB"],
    },
    {
        "question": "How many employees are active?",
        "expected_tool": "analyze_employees",
        "expected_dimension": "is_active",
        "invariants": ["active+inactive sum to total"],
    },
    {
        "question": "What are our carbon emission factors?",
        # Out-of-scope for the People tool: must NOT route to analyze_employees.
        "expected_tool": None,
        "expected_dimension": None,
        "invariants": ["does not fabricate People data"],
    },
    {
        "question": "Summarize total emissions by scope and by module",
        "expected_tool": "call_host_api",
        "expected_dimension": None,
        "invariants": [
            "envelope carries tables/charts",
            "headline does not claim 'no data'",
        ],
    },
    {
        "question": "Tell me about AASTMT carbon emissions in 2026",
        # AASTMT is the whole organisation, not a sub-entity filter — the org's
        # own name must NOT be treated as a missing entity (over-scoping bug).
        "expected_tool": "call_host_api",
        "expected_dimension": None,
        "invariants": [
            "org name is not a filter → full breakdown",
            "headline does not claim 'no data'",
            "envelope carries tables/charts",
        ],
    },
]

# ── Golden population spec ─────────────────────────────────────────────────
#
# Employees are fully enumerated so the builder is deterministic and the
# numbers below can be read straight off this file.

GOLDEN_DATASET: dict = {
    # org key → (name, slug)
    "orgs": [
        ("operations", "Operations"),
        ("engineering", "Engineering"),
    ],
    # position key → (org key, code, title)
    "positions": [
        ("engineer", "operations", "ENG", "Engineer"),
        ("supervisor", "operations", "SUP", "Supervisor"),
        ("floorman", "engineering", "FLR", "Floorman"),
    ],
    # employees: org, position, gender, is_active
    "employees": [
        {"no": "E001", "name": "Ali Hassan",   "org": "operations",  "position": "engineer",   "gender": "male",   "is_active": True},
        {"no": "E002", "name": "Omar Said",    "org": "operations",  "position": "engineer",   "gender": "male",   "is_active": True},
        {"no": "E003", "name": "John Smith",   "org": "operations",  "position": "engineer",   "gender": "M",      "is_active": True},
        {"no": "E004", "name": "Ahmed Nabil",  "org": "operations",  "position": "engineer",   "gender": "M",      "is_active": False},
        {"no": "E005", "name": "Sara Nabil",   "org": "operations",  "position": "engineer",   "gender": "female", "is_active": True},
        {"no": "E006", "name": "Mona Khalil",  "org": "engineering", "position": "supervisor", "gender": "F",      "is_active": True},
        {"no": "E007", "name": "Kareem Adel",  "org": "engineering", "position": "supervisor", "gender": "male",   "is_active": True},
        {"no": "E008", "name": "Tarek Fathy",  "org": "engineering", "position": "floorman",   "gender": "male",   "is_active": False},
        {"no": "E009", "name": "Noor Ahmed",   "org": "engineering", "position": "floorman",   "gender": "",       "is_active": True},
    ],
}
