"""Unit tests for ai.engine.core.resolution — the tri-state result helper.

Pure functions, no DB, no network. Verifies the canonical tri-state shape and
that ``no_match``/``error`` can never be conflated with ``resolved`` by a
truthiness check.
"""
from __future__ import annotations

from ai.engine.core.resolution import (
    error,
    is_error,
    is_no_match,
    is_resolved,
    min_confidence,
    no_match,
    payload_status,
    resolved,
    truthiness_guard,
)


# ── Constructors ─────────────────────────────────────────────────────────

def test_resolved_shape():
    r = resolved({"city": "Cairo"}, confidence=0.8, source="geocoder")
    assert r == {
        "status": "resolved",
        "data": {"city": "Cairo"},
        "confidence": 0.8,
        "source": "geocoder",
    }


def test_resolved_confidence_clamped():
    assert resolved({}, confidence=1.7)["confidence"] == 1.0
    assert resolved({}, confidence=-0.3)["confidence"] == 0.0
    assert resolved({})["confidence"] == 1.0  # default


def test_resolved_default_source():
    assert resolved("x")["source"] == ""


def test_no_match_shape_and_default_candidates():
    r = no_match("unresolved_location", hint="north coast egypt")
    assert r == {
        "status": "no_match",
        "reason": "unresolved_location",
        "hint": "north coast egypt",
        "candidates": [],
    }


def test_no_match_preserves_candidates():
    cands = ["Alexandria", "Cairo"]
    r = no_match("ambiguous", candidates=cands)
    assert r["candidates"] is cands


def test_error_shape():
    r = error("forecast_http_500", detail="upstream down")
    assert r == {
        "status": "error",
        "cause": "forecast_http_500",
        "detail": "upstream down",
    }
    assert error("boom")["detail"] == ""


# ── Predicates ───────────────────────────────────────────────────────────

def test_predicates_discriminate_all_three():
    r = resolved({"x": 1})
    n = no_match("nope")
    e = error("fail")
    assert is_resolved(r) and not is_resolved(n) and not is_resolved(e)
    assert is_no_match(n) and not is_no_match(r) and not is_no_match(e)
    assert is_error(e) and not is_error(r) and not is_error(n)


def test_predicates_false_for_non_dict_and_unrelated():
    assert not is_resolved(None)
    assert not is_no_match(None)
    assert not is_error(None)
    assert not is_resolved("resolved")
    assert not is_resolved({"foo": "bar"})
    assert not is_no_match({"status": "resolved"})
    assert not is_error({"status": "errorish"})


# ── Conservation helper ──────────────────────────────────────────────────

def test_min_confidence_empty_is_one():
    assert min_confidence() == 1.0


def test_min_confidence_returns_min_numeric():
    r1 = resolved({}, confidence=0.4)
    r2 = error("x")  # no confidence key
    assert min_confidence(r1, r2) == 0.4
    r3 = resolved({}, confidence=0.7)
    assert min_confidence(r1, r3) == 0.4


def test_min_confidence_skips_non_numeric():
    bad = {"status": "resolved", "confidence": "high"}
    assert min_confidence(bad) == 1.0
    assert min_confidence(bad, resolved({}, confidence=0.5)) == 0.5
    assert min_confidence({"status": "resolved"}) == 1.0


def test_min_confidence_clamped():
    high = resolved({}, confidence=1.7)
    low = resolved({}, confidence=-0.2)
    # raw min is -0.2 → clamped to 0.0
    assert min_confidence(high, low) == 0.0
    # all above 1.0 → clamped to 1.0
    assert min_confidence(high, resolved({}, confidence=2.0)) == 1.0


# ── Truthiness guard ─────────────────────────────────────────────────────

def test_truthiness_guard():
    assert truthiness_guard(resolved({})) is True
    assert truthiness_guard(no_match("nope")) is False
    assert truthiness_guard(error("fail")) is False


def test_no_conflation_between_no_match_and_error():
    n = no_match("unresolved_location")
    e = error("forecast_http_500")
    assert is_no_match(n) is True
    assert is_error(n) is False
    assert is_error(e) is True
    assert is_no_match(e) is False
    # the two are distinct branches — never the same state
    assert n["status"] != e["status"]
    assert n["status"] == "no_match" and e["status"] == "error"


# ── payload_status ───────────────────────────────────────────────────────

def test_payload_status_resolved_dict():
    assert payload_status(resolved({"city": "Cairo"})) == "resolved"


def test_payload_status_no_match_json_string():
    import json
    payload = json.dumps(no_match("unresolved_location", hint="north coast"))
    assert payload_status(payload) == "no_match"


def test_payload_status_error_dict():
    assert payload_status(error("forecast_http_500")) == "error"


def test_payload_status_host_envelope():
    env = {"status_code": 200, "data": no_match("unresolved_location", hint="x")}
    assert payload_status(env) == "no_match"


def test_payload_status_plain_dict_returns_none():
    assert payload_status({"foo": "bar"}) is None


def test_payload_status_non_json_string_returns_none():
    assert payload_status("not json at all") is None


def test_payload_status_none_returns_none():
    assert payload_status(None) is None
