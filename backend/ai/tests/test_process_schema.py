"""P3-03 — ``ProcessDefinition`` unified schema validation (hand-rolled fallback).

``jsonschema`` is not in ``backend/requirements.txt``, so validation runs through
:func:`ai.models.process.validate_definition`. These tests assert the schema
accepts the pilot ``dq.rule.release`` definition and rejects six malformed
fixtures (unknown step kind, unknown capability, missing required field, bad
status, bad autonomy, missing dependency).
"""
from __future__ import annotations

from ai.engine.ports.domain import load_domain_pack
from ai.models.capability import default_pack_dir
from ai.models.process import ProcessDefinition, validate_definition

PACK_DIR = default_pack_dir()

KNOWN_CAPABILITIES = {
    "dq.rule.validate",
    "dq.rule.review",
    "dq.rule.publish",
    "dq.rule.active_revision_matches_approved_revision",
}


def _pilot_document() -> dict:
    pack = load_domain_pack(PACK_DIR)
    processes = pack.processes()
    doc = next(p for p in processes if p.get("id") == "dq.rule.release")
    return dict(doc)


def test_pilot_process_definition_validates():
    doc = _pilot_document()

    assert validate_definition(doc) == []
    pd = ProcessDefinition.from_document(doc)  # no raise
    assert pd.process_id == "dq.rule.release"
    assert pd.status == "active"


def test_rejects_unknown_step_kind():
    doc = _pilot_document()
    doc["steps"][0]["kind"] = "frobnicate"
    errors = validate_definition(doc, known_capabilities=KNOWN_CAPABILITIES)
    assert any("unknown kind" in e for e in errors)


def test_rejects_unknown_capability():
    doc = _pilot_document()
    doc["steps"][1]["capability"] = "dq.rule.nonexistent"
    errors = validate_definition(doc, known_capabilities=KNOWN_CAPABILITIES)
    assert any("unknown capability" in e for e in errors)


def test_rejects_missing_required_field():
    doc = _pilot_document()
    del doc["owner"]
    errors = validate_definition(doc, known_capabilities=KNOWN_CAPABILITIES)
    assert any("missing required field" in e for e in errors)


def test_rejects_bad_status():
    doc = _pilot_document()
    doc["status"] = "void"
    errors = validate_definition(doc, known_capabilities=KNOWN_CAPABILITIES)
    assert any("invalid status" in e for e in errors)


def test_rejects_bad_autonomy():
    doc = _pilot_document()
    doc["steps"][2]["autonomy"] = "autopilot"
    errors = validate_definition(doc, known_capabilities=KNOWN_CAPABILITIES)
    assert any("invalid autonomy" in e for e in errors)


def test_rejects_missing_dependency():
    doc = _pilot_document()
    doc["steps"][1]["depends_on"] = ["ghost"]
    errors = validate_definition(doc, known_capabilities=KNOWN_CAPABILITIES)
    assert any("unknown dependency" in e for e in errors)
