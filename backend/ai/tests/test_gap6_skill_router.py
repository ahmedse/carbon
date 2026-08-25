"""Tests for SkillRouter (GAP-6).

All assertions are domain-agnostic — skill topic slugs are generic.
"""
import json
from unittest.mock import MagicMock

import pytest
from ai.engine.skills.router import SkillRouter


def make_skill(covers: list[str], terminology: dict | None = None) -> MagicMock:
    skill = MagicMock()
    body = {"covers": covers, "terminology": terminology or {}}
    skill.body = json.dumps(body)
    return skill


@pytest.fixture
def router():
    return SkillRouter()


def test_routes_to_matching_skill(router):
    skill_a = make_skill(["data-quality", "null-check"])
    skill_b = make_skill(["reporting", "export"])
    matched = router.find_matching_skills(
        "I need help with data quality checks", [skill_a, skill_b]
    )
    assert skill_a in matched
    assert skill_b not in matched


def test_returns_empty_if_no_skill_matches(router):
    skill = make_skill(["invoicing"])
    matched = router.find_matching_skills("How do I analyze schedules?", [skill])
    assert matched == []


def test_matches_hyphenated_slug_with_space(router):
    skill = make_skill(["null-check"])
    matched = router.find_matching_skills("run a null check on this field", [skill])
    assert skill in matched


def test_matches_slug_case_insensitively(router):
    skill = make_skill(["data-quality"])
    matched = router.find_matching_skills("DATA QUALITY review needed", [skill])
    assert skill in matched


def test_aggregates_terminology_from_multiple_skills(router):
    skill1 = make_skill(["validation"], {"null check": "not_null"})
    skill2 = make_skill(["profiling"], {"empty value": "is_empty"})
    terminology = router.get_terminology([skill1, skill2])
    assert terminology.get("null check") == "not_null"
    assert terminology.get("empty value") == "is_empty"


def test_get_terminology_returns_empty_for_no_skills(router):
    assert router.get_terminology([]) == {}


def test_invalid_skill_body_is_skipped_gracefully(router):
    bad_skill = MagicMock()
    bad_skill.body = "not valid json {{{"
    matched = router.find_matching_skills("anything", [bad_skill])
    assert matched == []


def test_skill_with_no_covers_never_matches(router):
    skill = make_skill([])  # empty covers
    matched = router.find_matching_skills("anything", [skill])
    assert matched == []


def test_multiple_skills_can_match(router):
    skill_a = make_skill(["validation", "quality"])
    skill_b = make_skill(["quality", "reporting"])
    matched = router.find_matching_skills("quality review", [skill_a, skill_b])
    assert skill_a in matched
    assert skill_b in matched
