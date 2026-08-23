"""
Phase 25-C — QoS + supervision endpoints: API tests (spec §4).

    GET /carbon-api/ai/plans/{id}/qos/     → {"report": {status, requirements[],
                                              metrics, final_response, supervision}}
    GET /carbon-api/ai/plans/{id}/flight/  → {"supervision": {ledger, repairs,
                                              escalations, fidelity, contract}}

Auth matrix (spec §4): owner 200 · authenticated outsider 403 · unauthenticated
401 · missing plan 404. Outcome copy only (RULE_23) — no engine seams touched;
runs + report rows are created directly.
"""
from __future__ import annotations

import uuid

import pytest

from accounts.models import User
from ai.models.core import AcceptanceReport, Run, RunStep

BASE = "/carbon-api/ai/plans"


def _make_plan(user, brief="Create a water DQ rule", status="completed"):
    return Run.objects.create(
        id=str(uuid.uuid4()),
        instance_id="carbon",
        conversation_id=f"conv-{uuid.uuid4().hex[:8]}",
        host_user_id=str(user.pk),
        user_message=brief,
        status=status,
        plan_json={
            "pattern": "custom",
            "source": "custom",
            "skill_name": None,
            "synthesis_instruction": "Summarize findings.",
            "steps": [
                {
                    "step_id": 0,
                    "intent": "Create a DQ rule",
                    "tool_name": "call_host_api",
                    "tool_args": {"api_name": "create_dq_rule", "body": {}},
                    "depends_on": [],
                },
            ],
        },
        final_response="All requirements met.",
        working_notes={
            "flight": {
                "ledger": [
                    {"kind": "rule", "id": 129, "name": "Water consumption",
                     "step_index": 0},
                ],
                "repairs": [],
                "escalations": 0,
                "fidelity": {"failures": 0, "escalated_steps": []},
                "contract": {
                    "findings": [],
                    "suggested_criteria": {
                        "0": {
                            "type": "created_entity", "kind": "rule",
                            "expect_status": 201,
                        },
                    },
                },
            },
        },
    )


def _make_report(plan, status="met"):
    return AcceptanceReport.objects.create(
        run=plan,
        status=status,
        report_json={
            "requirements": [
                {
                    "step_id": 0,
                    "intent": "Create a DQ rule",
                    "criterion": {
                        "type": "created_entity", "kind": "rule",
                        "expect_status": 201,
                    },
                    "verdict": status,
                    "evidence": {
                        "query": "GET /carbon-api/dq/rules/",
                        "matches": [{"id": 129, "name": "Water consumption"}],
                    },
                    "repairs": [],
                    "escalated": False,
                },
            ],
        },
        metrics_json={
            "retries": 0, "rewrites": 0, "vetoes": 0, "escalations": 0,
            "fidelity_failures": 0, "total_latency_ms": 12.0,
            "total_llm_calls": 3, "steps_total": 1, "steps_met": 1,
            "steps_partial": 0, "steps_missed": 0,
        },
        narrative="All requirements met.",
    )


@pytest.fixture
def user(db):
    return User.objects.create_user(username="flight-api-owner", password="secret123")


@pytest.fixture
def other_user(db):
    return User.objects.create_user(username="flight-api-other", password="secret123")


def _auth(api_client, get_token_for_user, user):
    api_client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(user)}"
    )


# ── GET qos/ ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_qos_returns_report_shape(
    api_client, get_token_for_user, user
):
    """Owner sees the §4 shape: status + requirements (with evidence) + metrics."""
    plan = _make_plan(user)
    _make_report(plan, status="met")
    _auth(api_client, get_token_for_user, user)

    resp = api_client.get(f"{BASE}/{plan.id}/qos/")

    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"report"}
    report = body["report"]
    assert set(report.keys()) == {
        "status", "requirements", "metrics", "final_response", "supervision",
    }
    assert report["status"] == "met"
    assert report["requirements"][0]["verdict"] == "met"
    assert report["requirements"][0]["evidence"]["matches"][0]["id"] == 129
    assert report["metrics"]["steps_met"] == 1
    assert report["final_response"] == "All requirements met."
    # supervision rides along from working_notes.flight (ledger + fidelity)
    assert report["supervision"]["ledger"][0]["kind"] == "rule"
    assert report["supervision"]["fidelity"] == {
        "failures": 0, "escalated_steps": [],
    }


@pytest.mark.django_db
def test_qos_surfaces_partial_with_evidence(
    api_client, get_token_for_user, user
):
    """A partial report (field-set mismatch) surfaces the actual diff."""
    plan = _make_plan(user)
    _make_report(plan, status="partial")
    _auth(api_client, get_token_for_user, user)

    resp = api_client.get(f"{BASE}/{plan.id}/qos/")

    assert resp.status_code == 200
    report = resp.json()["report"]
    assert report["status"] == "partial"
    assert report["requirements"][0]["verdict"] == "partial"


@pytest.mark.django_db
def test_qos_legacy_run_reconstructed_on_the_fly(
    api_client, get_token_for_user, user
):
    """No AcceptanceReport row → deterministic reconstruction from flight state."""
    plan = _make_plan(user)
    RunStep.objects.create(
        run_id=plan.id,
        step_index=0,
        intent="Create a DQ rule",
        tool_name="call_host_api",
        tool_args_json={"api_name": "create_dq_rule", "body": {}},
        depends_on_json=[],
        status="completed",
    )
    _auth(api_client, get_token_for_user, user)

    resp = api_client.get(f"{BASE}/{plan.id}/qos/")

    assert resp.status_code == 200
    report = resp.json()["report"]
    assert report["status"] == "met"
    assert report["requirements"][0]["verdict"] == "met"
    assert (
        report["requirements"][0]["evidence"]["query"]
        == "reconstructed-from-flight-state"
    )
    assert report["metrics"]["steps_total"] == 1
    assert report["final_response"] == "All requirements met."


# ── GET flight/ ──────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_flight_returns_supervision(api_client, get_token_for_user, user):
    plan = _make_plan(user)
    _auth(api_client, get_token_for_user, user)

    resp = api_client.get(f"{BASE}/{plan.id}/flight/")

    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"supervision"}
    supervision = body["supervision"]
    assert set(supervision.keys()) == {
        "ledger", "repairs", "escalations", "fidelity", "contract",
    }
    assert supervision["ledger"][0] == {
        "kind": "rule", "id": 129, "name": "Water consumption", "step_index": 0,
    }
    assert supervision["escalations"] == 0
    assert supervision["contract"]["suggested_criteria"]["0"]["type"] == "created_entity"


# ── Auth matrix ──────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_qos_outsider_forbidden_403(
    api_client, get_token_for_user, user, other_user
):
    plan = _make_plan(other_user)
    _make_report(plan)
    _auth(api_client, get_token_for_user, user)  # outsider

    resp = api_client.get(f"{BASE}/{plan.id}/qos/")

    assert resp.status_code == 403
    assert "error" in resp.json()


@pytest.mark.django_db
def test_flight_outsider_forbidden_403(
    api_client, get_token_for_user, user, other_user
):
    plan = _make_plan(other_user)
    _auth(api_client, get_token_for_user, user)  # outsider

    resp = api_client.get(f"{BASE}/{plan.id}/flight/")

    assert resp.status_code == 403


@pytest.mark.django_db
def test_qos_unauthenticated_401(api_client, user):
    plan = _make_plan(user)
    _make_report(plan)

    resp = api_client.get(f"{BASE}/{plan.id}/qos/")

    assert resp.status_code == 401


@pytest.mark.django_db
def test_flight_unauthenticated_401(api_client, user):
    plan = _make_plan(user)

    resp = api_client.get(f"{BASE}/{plan.id}/flight/")

    assert resp.status_code == 401


@pytest.mark.django_db
def test_qos_missing_plan_404(api_client, get_token_for_user, user):
    _auth(api_client, get_token_for_user, user)

    resp = api_client.get(f"{BASE}/does-not-exist/qos/")

    assert resp.status_code == 404
    assert "not found" in resp.json()["error"]


@pytest.mark.django_db
def test_flight_missing_plan_404(api_client, get_token_for_user, user):
    _auth(api_client, get_token_for_user, user)

    resp = api_client.get(f"{BASE}/does-not-exist/flight/")

    assert resp.status_code == 404
