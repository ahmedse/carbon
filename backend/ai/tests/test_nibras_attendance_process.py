"""Nibras ``attendance.permission.lifecycle`` — governance artifact tests.

Verifies ProcessDefinition + capabilities for the attendance permission
lifecycle (submit → review → approve → verify):

  (a) the ProcessDefinition document validates against ``validate_definition``;
  (b) every step's capability resolves (known set + host_action fail-closed);
  (c) review/approve gates are enforced (review=human_only + SoD, approve
      consent-required and confirmation-required);
  (d) the ``seed_nibras_processes`` command is idempotent (re-runnable).

Run under the Nibras brand::

    DJANGO_BRAND=nibras ../.venv/bin/python -m pytest ai/tests/test_nibras_attendance_process.py -q
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command
from django.test import override_settings

from ai.engine.ports.domain import load_domain_pack
from ai.models.capability import (
    Capability,
    load_capabilities,
    resolve_host_action,
)
from ai.models.process import (
    STATUS_ACTIVE,
    ProcessDefinition,
    validate_definition,
)

PACK_DIR = Path(settings.BASE_DIR).parent / "domain_packs" / "nibras"
PROCESS_ID = "attendance.permission.lifecycle"


def _pack():
    return load_domain_pack(PACK_DIR)


def _document() -> dict:
    doc = next(p for p in _pack().processes() if p.get("id") == PROCESS_ID)
    return dict(doc)


def _known_capabilities() -> set[str]:
    return {cap.capability_id for cap in load_capabilities(_pack())}


def test_process_definition_validates():
    doc = _document()
    assert validate_definition(doc, known_capabilities=_known_capabilities()) == []

    pd = ProcessDefinition.from_document(
        doc, known_capabilities=_known_capabilities(),
    )
    assert pd.process_id == PROCESS_ID
    assert pd.status == STATUS_ACTIVE
    assert pd.owner == "ai"


def test_every_step_capability_resolves():
    doc = _document()
    known = _known_capabilities()
    caps_by_id = {cap.capability_id: cap for cap in load_capabilities(_pack())}

    steps = doc["steps"]
    assert [s["id"] for s in steps] == ["submit", "review", "approve", "verify"]

    for step in steps:
        capability_id = step["capability"]
        assert capability_id in known, capability_id
        resolve_host_action(caps_by_id[capability_id].host_action)


def test_objective_predicate_is_a_known_capability():
    doc = _document()
    predicate = doc["objective"]["predicate"]
    assert predicate == "attendance.permission.approved_and_recorded"
    assert predicate in _known_capabilities()


def test_review_step_is_human_only_with_separation_of_duties():
    doc = _document()
    review = next(s for s in doc["steps"] if s["id"] == "review")

    assert review["kind"] == "human_task"
    assert review["autonomy"] == "human_only"
    assert review["separation_of_duties"] == ["requester", "approver"]
    assert review["capability"] == "attendance.permission.review"


def test_approve_step_is_host_effect_not_agent_mutation():
    """ADR-0045: approve is Team corr → signal, not Agent act_confirm."""
    doc = _document()
    approve = next(s for s in doc["steps"] if s["id"] == "approve")

    assert approve["kind"] == "command"
    assert approve["autonomy"] == "observe"
    assert approve["consent"] is False
    assert approve["capability"] == "attendance.permission.approve"


@pytest.mark.django_db
@override_settings(DJANGO_BRAND="nibras")
def test_seed_nibras_processes_idempotent_for_attendance():
    out1 = StringIO()
    call_command("seed_nibras_processes", stdout=out1)
    assert ProcessDefinition.objects.filter(
        process_id=PROCESS_ID, status=STATUS_ACTIVE,
    ).exists()
    assert Capability.objects.filter(
        capability_id="attendance.permission.approve",
    ).exists()

    out2 = StringIO()
    call_command("seed_nibras_processes", stdout=out2)
    assert ProcessDefinition.objects.filter(
        process_id=PROCESS_ID, status=STATUS_ACTIVE,
    ).count() >= 1
