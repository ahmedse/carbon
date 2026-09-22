"""Nibras leave ``leave.request.lifecycle`` — governance artifact tests.

Verifies the P3-01/P5a artifacts scaffolded for the Nibras leave lifecycle:

  (a) the ProcessDefinition document validates against ``validate_definition``;
  (b) every step's capability resolves (known set + host_action fail-closed);
  (c) review/record gates are enforced (review=human_only + SoD, record
      consent-required and confirmation-required);
  (d) the ``seed_nibras_processes`` command is idempotent (re-runnable).

Run under the Nibras brand::

    DJANGO_BRAND=nibras ../.venv/bin/python -m pytest ai/tests/test_nibras_leave_process.py -q
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
PROCESS_ID = "leave.request.lifecycle"


def _pack():
    return load_domain_pack(PACK_DIR)


def _document() -> dict:
    doc = next(p for p in _pack().processes() if p.get("id") == PROCESS_ID)
    return dict(doc)


def _known_capabilities() -> set[str]:
    return {cap.capability_id for cap in load_capabilities(_pack())}


# -- (a) the process document validates -------------------------------------


def test_process_definition_validates():
    doc = _document()
    assert validate_definition(doc, known_capabilities=_known_capabilities()) == []

    pd = ProcessDefinition.from_document(
        doc, known_capabilities=_known_capabilities(),
    )
    assert pd.process_id == PROCESS_ID
    assert pd.status == STATUS_ACTIVE
    assert pd.owner == "ai"


# -- (b) every step capability resolves -------------------------------------


def test_every_step_capability_resolves():
    doc = _document()
    known = _known_capabilities()
    caps_by_id = {cap.capability_id: cap for cap in load_capabilities(_pack())}

    steps = doc["steps"]
    assert [s["id"] for s in steps] == ["submit", "review", "record", "verify"]

    for step in steps:
        capability_id = step["capability"]
        assert capability_id in known, capability_id
        # host_action resolves fail-closed (raises on unknown/unimportable).
        resolve_host_action(caps_by_id[capability_id].host_action)


def test_objective_predicate_is_a_known_capability():
    doc = _document()
    predicate = doc["objective"]["predicate"]
    assert predicate == "leave.request.recorded_and_entitlement_decremented"
    assert predicate in _known_capabilities()


# -- (c) review/record gating semantics -------------------------------------


def test_review_step_is_human_only_with_separation_of_duties():
    doc = _document()
    review = next(s for s in doc["steps"] if s["id"] == "review")

    assert review["kind"] == "human_task"
    assert review["autonomy"] == "human_only"
    assert review["separation_of_duties"] == ["requester", "approver"]
    assert review["capability"] == "leave.request.review"


def test_record_step_is_host_effect_not_agent_mutation():
    """ADR-0045: record is Correspondence approve → signal, not Agent act_confirm."""
    doc = _document()
    record = next(s for s in doc["steps"] if s["id"] == "record")

    assert record["kind"] == "command"
    assert record["autonomy"] == "observe"
    assert record["consent"] is False
    assert record["capability"] == "leave.request.record"


# -- (d) seed command is idempotent -----------------------------------------


@override_settings(DJANGO_BRAND="nibras")
@pytest.mark.django_db
def test_seed_command_is_idempotent():
    call_command("seed_nibras_processes", stdout=StringIO())

    caps_after_first = Capability.objects.count()
    active_after_first = ProcessDefinition.objects.filter(
        process_id=PROCESS_ID, status=STATUS_ACTIVE,
    ).count()

    # Second run must not error, must not duplicate the active process, and
    # must not multiply capability rows.
    call_command("seed_nibras_processes", stdout=StringIO())

    assert active_after_first == 1
    assert ProcessDefinition.objects.filter(
        process_id=PROCESS_ID, status=STATUS_ACTIVE,
    ).count() == 1
    assert Capability.objects.count() == caps_after_first

    seeded_ids = set(
        Capability.objects.values_list("capability_id", flat=True)
    )
    assert _known_capabilities() <= seeded_ids
