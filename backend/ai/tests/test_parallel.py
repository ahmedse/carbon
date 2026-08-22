"""W6-D — Parallel phase execution proof (F-26).

Drives approved plans with a ``strategy: "parallel"`` phase through the REAL
ReActLoop (same seam pattern as ``test_artifact_e2e.py``: real loop, real
executor dispatch, real plugin registry, ``AI_STORE_BACKEND=django``) and
asserts:

1. Parallel phase → every step reaches a terminal status (completed) and each
   writes its OWN ``RunStep`` row + artifact (no cross-step writes).
2. A failing step does NOT corrupt sibling step rows — siblings still complete
   and persist their artifacts while the failing step lands as ``failed``.
3. Parallel fan-out does NOT bypass the consent gate — a mutation step in a
   parallel wave still pauses (``awaiting_approval`` + confirmation token) and
   the run halts at the wave boundary while already-completed siblings keep
   their persisted rows.
"""
from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings

from ai.models.core import Run, RunArtifact, RunStep
from ai.plans_service import PlansService
from ai.store import reset_store

User = get_user_model()

EXPORT_ARGS = {
    "title": "W6D Study",
    "format": "docx",
    "content": "# Findings\n\n- Approved emissions 1.2 kt.",
    "table": {"headers": ["Metric", "Value"], "rows": [["CO2e", "1200"]]},
}


class _FakeDraftWitness:
    """One deterministic tool call per step.

    - Steps whose intent contains ``FAIL_STEP`` emit malformed JSON arguments
      so the real executor surfaces a tool error (deterministic failure).
    - ``export_document`` steps get valid self-contained args.
    - Reasoning steps (no tool) emit no calls.
    """

    def __init__(self, *args, **kwargs):
        pass

    async def draft(self, **kwargs):
        tools = kwargs.get("tools") or []
        prompt = kwargs.get("user_message") or ""
        if not tools:
            return SimpleNamespace(text="reasoning step", tool_calls=[])
        name = tools[0]["function"]["name"]
        if "FAIL_STEP" in prompt:
            arguments = "{definitely-not-json"
        elif name == "export_document":
            args = dict(EXPORT_ARGS)
            args["title"] = f"W6D-{uuid.uuid4().hex[:6]}"
            arguments = json.dumps(args)
        else:
            arguments = "{}"
        return SimpleNamespace(
            text=f"calling {name}",
            tool_calls=[
                {
                    "id": f"call_{uuid.uuid4().hex[:8]}",
                    "type": "function",
                    "function": {"name": name, "arguments": arguments},
                }
            ],
        )


class _FakeCriticWitness:
    """Consent-gate critic: vetoes mutations without a confirmation token,
    passes everything else — mirrors the real critic's mutation contract."""

    def __init__(self, *args, **kwargs):
        pass

    async def review(self, **kwargs):
        if kwargs.get("is_mutation") and not kwargs.get("confirmation_token"):
            return SimpleNamespace(
                verdict="veto",
                flags=["mutation_not_confirmed"],
                veto_reason="Mutation requires user confirmation",
            )
        return SimpleNamespace(verdict="pass", flags=[])


def _export_step(step_id, *, intent=None, is_mutation=False):
    return {
        "step_id": step_id,
        "intent": intent or f"Export report {step_id}",
        "tool_name": "export_document",
        "tool_args": dict(EXPORT_ARGS, title=f"W6D-{step_id}"),
        "depends_on": [],
        "is_mutation": is_mutation,
        "agent_role": "worker",
    }


def _make_parallel_run(user, steps, phases) -> Run:
    """Seed an approved plan whose steps sit in one (parallel) phase."""
    run = Run.objects.create(
        id=str(uuid.uuid4()),
        instance_id="carbon",
        conversation_id=f"conv-{uuid.uuid4().hex[:8]}",
        host_user_id=str(user.pk),
        user_message="Run the parallel export plan.",
        status="approved",
        plan_json={
            "pattern": "custom",
            "source": "custom",
            "skill_name": None,
            "synthesis_instruction": "Summarize.",
            "steps": steps,
            "phases": phases,
        },
    )
    for s in steps:
        RunStep.objects.create(
            run_id=run.id,
            step_index=int(s["step_id"]),
            intent=s.get("intent", ""),
            tool_name=s.get("tool_name"),
            tool_args_json=s.get("tool_args") or {},
            depends_on_json=s.get("depends_on") or [],
            status="pending",
        )
    return run


def _parallel_phase(step_ids):
    return [
        {
            "phase_id": 0,
            "name": "export-wave",
            "goal": "Export all reports concurrently",
            "strategy": "parallel",
            "step_ids": step_ids,
        }
    ]


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="w6d-parallel-worker", password="secret123"
    )


@pytest.fixture
def run_cleanup():
    ids: list[str] = []
    yield ids
    RunStep.objects.filter(run_id__in=ids).delete()
    RunArtifact.objects.filter(run_id__in=ids).delete()
    Run.objects.filter(id__in=ids).delete()


def _drive(user, run, tmp_path) -> list[dict]:
    """Drive the real loop through the service frames path (incl. retry layer)."""
    with override_settings(
        AI_STORE_BACKEND="django", MEDIA_ROOT=str(tmp_path)
    ):
        reset_store()
        try:
            with _engine_patches(user):
                return list(PlansService()._run_plan_frames_sync(user, run.id))
        finally:
            reset_store()


def _drive_once(user, run, tmp_path) -> None:
    """Drive ONE engine run (no service retry layer) — for failure-path tests.

    A persistently failing step would otherwise trigger the service's bounded
    retry loop (up to 3 re-runs with backoff), which re-executes the whole
    plan and duplicates artifacts — muddying the sibling-isolation proof. The
    engine-level single run is the precise W6-D claim: within one parallel
    wave, a failing step leaves its siblings' rows and artifacts intact.
    """
    import asyncio

    from ai.engine_runtime import (
        _build_chat_user_info,
        _carbon_instance_config,
    )

    with override_settings(
        AI_STORE_BACKEND="django", MEDIA_ROOT=str(tmp_path)
    ):
        reset_store()
        try:
            svc = PlansService()
            plan = svc._rebuild_plan(run)
            instance_config = _carbon_instance_config(str(user.pk))
            user_info = _build_chat_user_info(str(user.pk))
            conversation_id = run.conversation_id or f"plan-{run.id}"
            # The engine resume path requires the Run row to be ``paused``
            # (the frames wrapper arms this before re-entering the engine).
            run.status = "paused"
            run.save(update_fields=["status", "updated_at"])
            with _engine_patches(user):
                asyncio.run(
                    svc._execute_plan_once(
                        run,
                        plan,
                        str(user.pk),
                        conversation_id,
                        instance_config,
                        user_info,
                    )
                )
        finally:
            reset_store()


class _engine_patches:
    """Context manager applying the engine seams both drivers share."""

    def __init__(self, user):
        self.user = user
        self._stack = None

    def __enter__(self):
        import contextlib

        self._stack = contextlib.ExitStack()
        self._stack.enter_context(
            patch("ai.engine.cognition.turn.draft.DraftWitness", _FakeDraftWitness)
        )
        self._stack.enter_context(
            patch("ai.engine.cognition.turn.critic.CriticWitness", _FakeCriticWitness)
        )
        self._stack.enter_context(
            patch(
                "ai.engine.llm.prompts.build_chat_prompt",
                AsyncMock(return_value="W6D system prompt"),
            )
        )
        self._stack.enter_context(
            patch(
                "ai.engine_runtime._carbon_instance_config",
                lambda user_pk: {
                    "display_name": "Carbon",
                    "description": "W6D parallel proof",
                },
            )
        )
        self._stack.enter_context(
            patch(
                "ai.engine_runtime._build_chat_user_info",
                lambda user_pk: {
                    "username": self.user.username,
                    "display_name": self.user.username,
                    "email": "",
                    "roles": [],
                },
            )
        )
        return self

    def __exit__(self, *exc):
        self._stack.close()
        return False


# ── Gate 1: parallel phase → all steps terminal + own rows ────────────────


@pytest.mark.django_db(transaction=True)
def test_parallel_phase_all_steps_terminal(user, tmp_path, run_cleanup):
    steps = [_export_step(0), _export_step(1), _export_step(2)]
    run = _make_parallel_run(user, steps, _parallel_phase([0, 1, 2]))
    run_cleanup.append(run.id)

    frames = _drive(user, run, tmp_path)

    step_rows = list(RunStep.objects.filter(run_id=run.id).order_by("step_index"))
    assert len(step_rows) == 3, step_rows
    assert {s.status for s in step_rows} == {"completed"}, [
        (s.step_index, s.status) for s in step_rows
    ]

    artifacts = list(RunArtifact.objects.filter(run_id=run.id))
    assert len(artifacts) == 3, artifacts
    assert {a.step_index for a in artifacts} == {0, 1, 2}
    for a in artifacts:
        assert a.size_bytes > 0, a.name

    # Each step serialized with its artifact + output_type
    payload = PlansService().get_plan(user, run.id)
    assert payload["status"] == "completed", payload["status"]
    for s in payload["steps"]:
        assert s["output_type"] == "artifact", (s["step_id"], s.get("tool_output"))
        assert len(s["artifacts"]) == 1, s["step_id"]

    # Frames: three completed step_results + completed done frame
    step_results = [f for f in frames if f["type"] == "step_result"]
    assert len(step_results) == 3, frames
    assert all(f["status"] == "completed" for f in step_results), step_results
    assert any(
        f["type"] == "done" and f["status"] == "completed" for f in frames
    ), frames


# ── Gate 2: failing step does not corrupt sibling rows ────────────────────


@pytest.mark.django_db(transaction=True)
def test_parallel_failing_step_does_not_corrupt_siblings(
    user, tmp_path, run_cleanup
):
    steps = [
        _export_step(0),
        _export_step(1),
        _export_step(2, intent="FAIL_STEP: explode on purpose"),
    ]
    run = _make_parallel_run(user, steps, _parallel_phase([0, 1, 2]))
    run_cleanup.append(run.id)

    _drive_once(user, run, tmp_path)

    step_rows = {
        s.step_index: s
        for s in RunStep.objects.filter(run_id=run.id).order_by("step_index")
    }
    assert len(step_rows) == 3, step_rows
    # Siblings completed and kept their artifacts
    for idx in (0, 1):
        assert step_rows[idx].status == "completed", (
            idx,
            step_rows[idx].status,
            step_rows[idx].error,
        )
    # Failing step surfaced honestly
    assert step_rows[2].status == "failed", (
        step_rows[2].status,
        step_rows[2].tool_output_json,
    )
    assert "Invalid JSON" in (step_rows[2].error or ""), step_rows[2].error

    artifacts = list(RunArtifact.objects.filter(run_id=run.id))
    assert len(artifacts) == 2, artifacts
    assert {a.step_index for a in artifacts} == {0, 1}
    for a in artifacts:
        assert a.size_bytes > 0, a.name

    # Run honestly failed (one step errored) but sibling rows intact
    run.refresh_from_db()
    assert run.status == "failed", run.status


# ── Gate 3: parallel fan-out does NOT bypass the consent gate ─────────────


@pytest.mark.django_db(transaction=True)
def test_parallel_consent_gate_intact(user, tmp_path, run_cleanup):
    steps = [
        _export_step(0),                                # non-mutation
        _export_step(1, is_mutation=True),              # mutation → consent
    ]
    run = _make_parallel_run(user, steps, _parallel_phase([0, 1]))
    run_cleanup.append(run.id)

    frames = _drive(user, run, tmp_path)

    step_rows = {
        s.step_index: s
        for s in RunStep.objects.filter(run_id=run.id).order_by("step_index")
    }
    assert len(step_rows) == 2, step_rows
    # Non-mutation sibling in the same wave completed and persisted its row
    assert step_rows[0].status == "completed", (
        step_rows[0].status,
        step_rows[0].error,
    )
    # Mutation step gated — awaiting_approval with a stored confirmation token
    assert step_rows[1].status == "awaiting_approval", (
        step_rows[1].status,
        step_rows[1].tool_output_json,
    )
    assert step_rows[1].confirmation_token, "no confirmation token stored"

    # Only the completed sibling has an artifact (mutation never executed)
    artifacts = list(RunArtifact.objects.filter(run_id=run.id))
    assert len(artifacts) == 1, artifacts
    assert artifacts[0].step_index == 0, artifacts[0].step_index

    payload = PlansService().get_plan(user, run.id)
    assert payload["status"] == "paused", payload["status"]
    assert any(
        f["type"] == "done" and f["status"] == "paused" for f in frames
    ), frames
    assert any(f["type"] == "step_confirm" for f in frames), frames


# ── Gate 4: consent gate halts the WHOLE run (W6-F regression) ────────────
# The loop's consent-gate ``break`` used to exit only the fold-back ``for``,
# so the outer ``while remaining:`` "never-stall" fallback kept executing
# steps AFTER the gate and ``_finalize_run`` clobbered the paused status to
# failed/completed — which blocked ``confirm_step``'s ``status == paused``
# guard and let later mutation steps run without consent. The pause must halt
# the entire run at the gate.


@pytest.mark.django_db(transaction=True)
def test_consent_gate_halts_entire_run_no_steps_after_gate_execute(
    user, tmp_path, run_cleanup
):
    steps = [
        _export_step(0),                                   # completes first
        _export_step(1, is_mutation=True),                 # mutation → gate
        _export_step(2),                                   # MUST stay pending
    ]
    steps[1]["depends_on"] = [0]
    steps[2]["depends_on"] = [1]
    run = _make_parallel_run(user, steps, [])
    run_cleanup.append(run.id)

    frames = _drive(user, run, tmp_path)

    step_rows = {
        s.step_index: s
        for s in RunStep.objects.filter(run_id=run.id).order_by("step_index")
    }
    assert len(step_rows) == 3, step_rows
    # Step 0 (pre-gate) completed; step 1 gated with a stored token
    assert step_rows[0].status == "completed", step_rows[0].status
    assert step_rows[1].status == "awaiting_approval", (
        step_rows[1].status,
        step_rows[1].tool_output_json,
    )
    assert step_rows[1].confirmation_token, "no confirmation token stored"
    # Step 2 NEVER executed — the run halted at the gate
    assert step_rows[2].status == "pending", (
        step_rows[2].status,
        step_rows[2].tool_output_json,
    )

    # Only the pre-gate step has an artifact (neither gated nor later steps ran)
    artifacts = list(RunArtifact.objects.filter(run_id=run.id))
    assert len(artifacts) == 1, artifacts
    assert artifacts[0].step_index == 0, artifacts[0].step_index

    # Run row stays PAUSED (not clobbered to failed) so confirm_step works
    run.refresh_from_db()
    assert run.status == "paused", run.status
    payload = PlansService().get_plan(user, run.id)
    assert payload["status"] == "paused", payload["status"]
    assert any(
        f["type"] == "done" and f["status"] == "paused" for f in frames
    ), frames
