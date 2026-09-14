"""P3-02 — host predicate ``dq.rule.active_revision_matches_approved_revision``.

Pure, deterministic, fail-closed revision-equality predicate (host-side).
"""
from __future__ import annotations

from ai.predicates import dq_rule_active_revision_matches_approved_revision


def test_predicate_true_on_match():
    rule = {"active_revision": 7, "approved_revision": 7}
    assert dq_rule_active_revision_matches_approved_revision(rule) is True


def test_predicate_false_on_mismatch():
    rule = {"active_revision": 8, "approved_revision": 7}
    assert dq_rule_active_revision_matches_approved_revision(rule) is False


def test_predicate_fail_closed_on_missing_active():
    rule = {"approved_revision": 7}
    assert dq_rule_active_revision_matches_approved_revision(rule) is False


def test_predicate_fail_closed_on_missing_approved():
    rule = {"active_revision": 7}
    assert dq_rule_active_revision_matches_approved_revision(rule) is False


def test_predicate_reads_definition_dict():
    class Rule:
        definition = {"active_revision": 7, "approved_revision": 7}

    assert dq_rule_active_revision_matches_approved_revision(Rule()) is True


def test_predicate_string_equivalence():
    rule = {"active_revision": "7", "approved_revision": 7}
    assert dq_rule_active_revision_matches_approved_revision(rule) is True
