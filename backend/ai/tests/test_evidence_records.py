"""Phase 4 — Evidence records."""
import json

import pytest
from asgiref.sync import sync_to_async

pytestmark = pytest.mark.django_db(transaction=True)


def _make_witness(run_id="t1", instance_id="i1", conversation_id="c1", host_user_id="u1"):
    from ai.engine.cognition.turn.execute import ExecuteWitness
    return ExecuteWitness(
        run_id=run_id,
        instance_id=instance_id,
        hook_ctx_defaults={
            "instance_id": instance_id,
            "conversation_id": conversation_id,
            "host_user_id": host_user_id,
            "run_id": run_id,
        },
    )


@pytest.mark.asyncio
async def test_evidence_record_created_for_successful_tool():
    """_register_evidence must create an EvidenceRecord row for real data."""
    from ai.models.core import EvidenceRecord

    ew = _make_witness()
    await ew._register_evidence(
        tool_name="get_entity_details",
        tool_args={"entity_type": "emission_factor", "entity_id": "ef-1"},
        tool_result={
            "tool_name": "get_entity_details",
            "result": json.dumps({"name": "Electricity", "factor": 2.5, "unit": "kg CO2e/kWh"}),
        },
    )

    record = await sync_to_async(EvidenceRecord.objects.get, thread_sensitive=True)(
        turn_id="t1"
    )
    assert record.source_type == "carbon_api"
    assert "entity_type" in record.query_description
    assert record.host_user_id == "u1"


@pytest.mark.asyncio
async def test_evidence_record_skipped_for_no_match():
    """no_match results are not evidence — no row must be created."""
    from ai.models.core import EvidenceRecord

    ew = _make_witness(run_id="t-nomatch")
    await ew._register_evidence(
        tool_name="get_entity_details",
        tool_args={"entity_id": "nonexistent"},
        tool_result={
            "result": json.dumps({"status": "no_match", "hint": "Entity not found"}),
        },
    )

    count = await sync_to_async(
        lambda: EvidenceRecord.objects.filter(turn_id="t-nomatch").count(),
        thread_sensitive=True,
    )()
    assert count == 0


@pytest.mark.asyncio
async def test_evidence_record_does_not_fail_turn_on_error():
    """_register_evidence must silently swallow errors and never raise."""
    from ai.engine.cognition.turn.execute import ExecuteWitness

    ew = ExecuteWitness()  # no context at all
    # None result + confirmation-style tool + garbage args — must not raise.
    await ew._register_evidence(
        tool_name="web_research",
        tool_args={},
        tool_result={"result": None},
    )
