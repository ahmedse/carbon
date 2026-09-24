"""Navigation GROUNDING — bilingual (EN + AR).

Comprehension ("is this a navigation request?") belongs to the LLM intent
classifier. This module only *grounds* a target concept the LLM already chose
into a concrete, declared in-app route — so navigation never dead-ends on an
LLM-guessed entity name, and never fabricates a destination.
"""
import pytest

from ai.engine.cognition.turn.navigation import (
    detect_lang,
    ground_navigation,
    load_targets,
    normalize_text,
)


NIBRAS_CONFIG = {
    "navigation_routes": [
        {
            "name": "people_home", "type": "app", "path": "/people",
            "label": "People & Payroll",
            "labels": {
                "en": ["people", "people app", "hr", "human resources"],
                "ar": ["الموارد البشرية", "شؤون الموظفين", "الموظفون"],
            },
        },
        {
            "name": "employees", "type": "page", "path": "/people/employees",
            "labels": {
                "en": ["employees", "employee list"],
                "ar": ["الموظفون", "قائمة الموظفين"],
            },
        },
        {
            "name": "employee_detail", "type": "entity",
            "path": "/people/employees/{id}",
        },
        {
            "name": "payroll", "type": "page", "path": "/people/payroll",
            "labels": {"en": ["payroll", "payslips"], "ar": ["الرواتب"]},
        },
    ],
}

CARBON_CONFIG = {
    "navigation_routes": [
        {
            "name": "dq_home", "type": "app", "path": "/dq",
            "labels": {"en": ["data quality", "dq"], "ar": ["جودة البيانات"]},
        },
    ],
}


# ── Normalisation / language ────────────────────────────────────────────────

def test_normalize_folds_arabic_variants():
    assert normalize_text("الموارد البشرية") == "الموارد البشريه"
    assert normalize_text("أحمد") == "احمد"
    assert normalize_text("إلى") == "الي"


def test_detect_lang():
    assert detect_lang("fly to people app") == "en"
    assert detect_lang("روح لتطبيق الموظفين") == "ar"


# ── Grounding an English concept ─────────────────────────────────────────────
# The concept string may carry surrounding words (the LLM often echoes the
# phrasing); grounding is robust to that via alias substring matching.

def test_ground_people_app_en():
    res = ground_navigation("the people app", NIBRAS_CONFIG)
    assert res.action == "navigate"
    assert res.targets[0].route == "/people"


def test_ground_payroll_en():
    res = ground_navigation("payroll", NIBRAS_CONFIG)
    assert res.action == "navigate"
    assert res.targets[0].route == "/people/payroll"


def test_ground_employees_en():
    res = ground_navigation("employees page", NIBRAS_CONFIG)
    assert res.action == "navigate"
    assert res.targets[0].route == "/people/employees"


def test_ground_carbon_dq_en():
    res = ground_navigation("data quality", CARBON_CONFIG)
    assert res.action == "navigate"
    assert res.targets[0].route == "/dq"


# ── Grounding an Arabic concept ──────────────────────────────────────────────

def test_ground_arabic_app_noun_resolves_to_app_home():
    # "تطبيق" (app) boosts the People *app* home over the employees page.
    res = ground_navigation("تطبيق الموظفين", NIBRAS_CONFIG)
    assert res.action == "navigate"
    assert res.targets[0].route == "/people"


def test_ground_arabic_employees_is_ambiguous():
    # No "app" noun → people home vs employees page are near-equal candidates.
    res = ground_navigation("الموظفين", NIBRAS_CONFIG)
    assert res.action == "disambiguate"
    routes = {t.route for t in res.targets}
    assert routes == {"/people", "/people/employees"}


def test_ground_arabic_normalisation_hamza_and_teh_marbuta():
    res = ground_navigation("الموارد البشريه", NIBRAS_CONFIG)
    assert res.action == "navigate"
    assert res.targets[0].route == "/people"


# ── Graceful no-op ──────────────────────────────────────────────────────────

def test_no_matching_target_no_fire():
    res = ground_navigation("the moon", NIBRAS_CONFIG)
    assert res.action == "none"


def test_empty_config_no_fire():
    res = ground_navigation("people", {})
    assert res.action == "none"


# ── Target loading ──────────────────────────────────────────────────────────

def test_load_targets_skips_entity_routes():
    targets = load_targets(NIBRAS_CONFIG)
    routes = {t.route for t in targets}
    assert "/people/employees/{id}" not in routes
    assert routes == {"/people", "/people/employees", "/people/payroll"}


# ── Grounding (LLM target concept → routes) ─────────────────────────────────

def test_resolve_navigation_alias_matches_ground():
    from ai.engine.cognition.turn.navigation import ground_navigation, resolve_navigation

    g = ground_navigation("payroll", NIBRAS_CONFIG)
    r = resolve_navigation("payroll", NIBRAS_CONFIG)
    assert r.action == g.action
    assert [t.route for t in r.targets] == [t.route for t in g.targets]
    # The LLM names the concept "people"; grounding maps it to the app home.
    res = ground_navigation("people", NIBRAS_CONFIG)
    assert res.action in ("navigate", "disambiguate")
    assert any(t.route == "/people" for t in res.targets)


def test_ground_navigation_matches_exact_display_label():
    # LLM emits the exact display label, not an alias — must still ground.
    res = ground_navigation("People & Payroll", NIBRAS_CONFIG)
    assert res.action == "navigate"
    assert res.targets[0].route == "/people"


def test_ground_navigation_arabic_concept():
    res = ground_navigation("الموارد البشرية", NIBRAS_CONFIG)
    assert res.action == "navigate"
    assert res.targets[0].route == "/people"


def test_ground_navigation_unknown_concept_no_fire():
    res = ground_navigation("accounting", NIBRAS_CONFIG)
    assert res.action == "none"


def test_first_person_self_read_skips_navigation_offer():
    from ai.engine.cognition.turn.navigation import resolve_navigation

    assert resolve_navigation("Show my payslips", NIBRAS_CONFIG).action == "none"
    assert resolve_navigation("What are my loans?", NIBRAS_CONFIG).action == "none"
    assert resolve_navigation("قروضي", NIBRAS_CONFIG).action == "none"
    assert resolve_navigation("Go to payroll", NIBRAS_CONFIG).action == "navigate"


def test_ground_navigation_ignores_no_verb_needed():
    # grounding does not require a verb — the caller has already classified
    # the request as navigation.
    res = ground_navigation("payroll", NIBRAS_CONFIG)
    assert res.action == "navigate"
    assert res.targets[0].route == "/people/payroll"
