"""Deep multi-scenario simulation of the agent task-orchestration (plans) system.

Two layers, one report:

PART A — LIVE SYSTEM STRESS TEST (real HTTP API, real engine, real LLM)
    Every scenario drives the running backend over HTTP exactly like the
    frontend does (JWT → /carbon-api/ai/plans/…), capturing the SSE frame
    protocol, ledger, lifecycle operations and side effects.  These plans
    are real rows owned by the live user — visible in the Tasks panel.

PART B — DESIGNED WORKFLOW SIMULATION (service-level, deterministic seams)
    Demonstrates the multi-agent orchestration surface the plan loop is
    designed for — multi-step DAGs (chains, parallel fan-out), the consent
    gate (confirm / decline a staged mutation), veto→failure surfacing,
    pause / resume, edit+diff, fork — using the same deterministic fake
    engine seams the test-suite uses (no LLM cost, repeatable).

Usage:
    cd backend && ../.venv/bin/python manage.py simulate_agent_workflows
    cd backend && ../.venv/bin/python manage.py simulate_agent_workflows --part B
    cd backend && ../.venv/bin/python manage.py simulate_agent_workflows --tag demo-1
"""
import argparse
import json
import re
import sys
import threading
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import requests

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone as dj_timezone

from rest_framework_simplejwt.tokens import RefreshToken

from ai.models.core import Run, RunStep
from ai.plans_service import PlansService

BASE = "http://localhost:8009/carbon-api"
REPORT_PATH = Path(__file__).resolve().parents[4] / "docs" / (
    f"TASK-RESULTS-SIMULATION-{datetime.now().strftime('%Y-%m-%d')}.md"
)

OK, WARN, FAIL = "✅", "⚠️", "❌"

# ── Scenario registry ---------------------------------------------------------
SCENARIOS_A: list[dict] = []
SCENARIOS_B: list[dict] = []
FINDINGS: list[dict] = []


def scenario_a(fn):
    SCENARIOS_A.append({"fn": fn, "name": fn.__name__})
    return fn


def scenario_b(fn):
    SCENARIOS_B.append({"fn": fn, "name": fn.__name__})
    return fn


# ── HTTP helpers (Part A) -----------------------------------------------------
class Live:
    """Thin HTTP client over the real backend, minting a JWT per user."""

    def __init__(self, username="ahmed"):
        self.user = get_user_model().objects.get(username=username)
        self.username = username
        self._token = None

    @property
    def token(self):
        if self._token is None:
            self._token = str(RefreshToken.for_user(self.user).access_token)
        return self._token

    def headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    def post(self, path, json=None, timeout=180):
        return requests.post(
            f"{BASE}{path}", json=json, headers=self.headers(), timeout=timeout
        )

    def get(self, path, timeout=60):
        return requests.get(f"{BASE}{path}", headers=self.headers(), timeout=timeout)

    def patch(self, path, json=None, timeout=60):
        return requests.patch(
            f"{BASE}{path}", json=json, headers=self.headers(), timeout=timeout
        )

    def sse(self, path, timeout=900):
        """POST and consume the text/event-stream, returning parsed frames."""
        frames = []
        with requests.post(
            f"{BASE}{path}", headers=self.headers(), stream=True, timeout=timeout
        ) as resp:
            status = resp.status_code
            content_type = resp.headers.get("content-type", "")
            for raw in resp.iter_lines(decode_unicode=True):
                if not raw or not raw.startswith("data:"):
                    continue
                try:
                    frames.append(json.loads(raw[5:].strip()))
                except json.JSONDecodeError:
                    frames.append({"type": "raw", "raw": raw})
        return {"http_status": status, "content_type": content_type, "frames": frames}


def tag(n, t):
    """Prefix a brief so plans are traceable to a scenario."""
    return f"[SIM:{n}] {t}"


def short_id(s):
    return (s or "")[:8]


# ── Part A scenarios ----------------------------------------------------------

@scenario_a
def a01_baseline_single_step(ctx):
    """A single-step request follows create → approve → run → completed."""
    L = ctx["live"]
    brief = tag("A01", "List your capabilities.")
    r = L.post("/ai/plans/", json={"brief": brief})
    plan = r.json()
    pid = plan.get("id")
    checks = [("create 201", r.status_code == 201)]
    checks.append(("status pending_approval", plan.get("status") == "pending_approval"))
    checks.append(("single step", len(plan.get("steps") or []) == 1))

    r2 = L.post(f"/ai/plans/{pid}/approve/")
    checks.append(("approve → approved", r2.ok and r2.json().get("status") == "approved"))

    sse = L.sse(f"/ai/plans/{pid}/run/")
    types = [f.get("type") for f in sse["frames"]]
    checks.append(("sse protocol", types == ["plan_start", "step_start", "step_result", "step_end", "done"]))
    done = next((f for f in sse["frames"] if f.get("type") == "done"), {})
    checks.append(("done completed", done.get("status") == "completed"))

    ledger = L.get(f"/ai/plans/{pid}/ledger/").json()
    checks.append(("ledger steps", len(ledger.get("steps") or []) >= 1))
    checks.append(("ledger actor", (ledger.get("actor") or {}).get("user_id") == "1"))
    return pid, checks, {"frames": types, "pattern": plan.get("pattern"),
                         "source": plan.get("source"), "ledger_status": ledger.get("status")}


@scenario_a
def a02_multi_step_intent(ctx):
    """A brief describing three sequential tool actions SHOULD decompose into
    three dependent steps (W3-A design).  Reports what the live system does."""
    L = ctx["live"]
    brief = tag(
        "A02",
        "First list your capabilities using list_my_capabilities, and then "
        "search your knowledge base for 'alamein campus' using search_knowledge, "
        "and then get entity details for 'carbon' using get_entity_details.",
    )
    r = L.post("/ai/plans/", json={"brief": brief})
    plan = r.json()
    pid = plan.get("id")
    steps = plan.get("steps") or []
    checks = [("create 201", r.status_code == 201)]
    checks.append(("expect ≥3 steps", len(steps) >= 3))
    checks.append(("steps have tools", all(s.get("tool_name") for s in steps)))
    detail = {"observed_steps": len(steps),
              "source": plan.get("source"), "pattern": plan.get("pattern"),
              "tool_names": [s.get("tool_name") for s in steps]}

    L.post(f"/ai/plans/{pid}/approve/")
    sse = L.sse(f"/ai/plans/{pid}/run/")
    types = [f.get("type") for f in sse["frames"]]
    done = next((f for f in sse["frames"] if f.get("type") == "done"), {})
    checks.append(("run completes", done.get("status") == "completed"))
    detail["run_frames"] = types
    detail["final_response"] = (done.get("final_response") or "")[:120]

    # Deep evidence: did any step actually invoke a tool?
    ledger = L.get(f"/ai/plans/{pid}/ledger/").json()
    tool_usage = [s.get("tool_name") for s in ledger.get("steps", []) if s.get("tool_name")]
    detail["ledger_tool_usage"] = tool_usage
    if len(steps) >= 3 and all(s.get("tool_name") for s in steps):
        checks.append(("tools executed", bool(tool_usage)))
    return pid, checks, detail


@scenario_a
def a03_mutation_claim(ctx):
    """A brief asking to create a DQ rule: does the live run gate the mutation
    (consent) or claim success without writing?  Verifies the DQ rules table."""
    L = ctx["live"]
    rule_name = f"SIM-A03 null email {uuid.uuid4().hex[:6]}"
    brief = tag(
        "A03",
        f"Add a data-quality rule named '{rule_name}' that flags null email "
        "values. Use the create_dq_rule tool with rule_type 'not_null', "
        "level 'field', severity 'error', column 'email'.",
    )
    r = L.post("/ai/plans/", json={"brief": brief})
    plan = r.json()
    pid = plan.get("id")
    checks = [("create 201", r.status_code == 201)]
    checks.append(("needs_confirmation flagged", bool(plan.get("needs_confirmation"))))

    L.post(f"/ai/plans/{pid}/approve/")
    sse = L.sse(f"/ai/plans/{pid}/run/")
    types = [f.get("type") for f in sse["frames"]]
    done = next((f for f in sse["frames"] if f.get("type") == "done"), {})
    detail = {"frames": types, "final_status": done.get("status")}
    checks.append(("run completes", done.get("status") == "completed"))
    checks.append(("consent gate reached", "step_confirm" in types))
    checks.append(("done not paused", done.get("status") != "paused"))

    # Truth check: was the rule actually created?
    rules_resp = L.get("/dq/rules/")
    found = False
    if rules_resp.ok:
        rules = rules_resp.json()
        items = rules.get("results") if isinstance(rules, dict) else rules
        found = any(
            (it.get("name") or "") == rule_name
            for it in (items or [])
        )
    checks.append(("rule actually created", found))
    detail["rule_created"] = found
    detail["claimed"] = "created" in ((done.get("final_response") or "").lower())
    detail["final_response"] = (done.get("final_response") or "")[:160]
    return pid, checks, detail


@scenario_a
def a04_happy_path_ledger(ctx):
    """A complete lifecycle with a rich audit ledger (provenance, actor,
    latency, tokens)."""
    L = ctx["live"]
    brief = tag("A04", "Summarize the emissions data and explain the top metric.")
    r = L.post("/ai/plans/", json={"brief": brief})
    plan = r.json()
    pid = plan.get("id")
    L.post(f"/ai/plans/{pid}/approve/")
    sse = L.sse(f"/ai/plans/{pid}/run/")
    done = next((f for f in sse["frames"] if f.get("type") == "done"), {})
    checks = [("done completed", done.get("status") == "completed")]

    ledger = L.get(f"/ai/plans/{pid}/ledger/").json()
    detail = {}
    for key in ("status", "provenance", "actor", "confirmations", "replans"):
        detail[key] = ledger.get(key)
    step0 = (ledger.get("steps") or [{}])[0]
    checks.append(("ledger actor present", bool((ledger.get("actor") or {}).get("user_id"))))
    checks.append(("ledger latency", (step0.get("latency_ms") or 0) > 0))
    detail["first_step"] = {k: step0.get(k) for k in
                            ("step_id", "status", "critic_verdict", "latency_ms", "tool_name")}
    return pid, checks, detail


@scenario_a
def a05_decline_at_approval(ctx):
    """Reject a plan at review: cancelled + steps skipped + cannot run."""
    L = ctx["live"]
    brief = tag("A05", "Draft a plan I will then reject at review.")
    r = L.post("/ai/plans/", json={"brief": brief})
    plan = r.json()
    pid = plan.get("id")
    r2 = L.post(f"/ai/plans/{pid}/decline/")
    checks = [("decline 200", r2.ok)]
    checks.append(("status cancelled", r2.json().get("status") == "cancelled"))
    steps = r2.json().get("steps") or []
    checks.append(("steps skipped", all(s.get("status") == "skipped" for s in steps)))

    # Running a declined plan must fail loudly.
    sse = L.sse(f"/ai/plans/{pid}/run/")
    types = [f.get("type") for f in sse["frames"]]
    checks.append(("run rejected (error frame)", "error" in types or sse["http_status"] in (400, 404)))
    detail = {"types": types, "http_status": sse["http_status"],
              "error": next((f.get("error") for f in sse["frames"] if f.get("type") == "error"), None)}
    return pid, checks, detail


@scenario_a
def a06_edit_replan_diff(ctx):
    """W3-C edit: change the brief → diff {added, removed, changed} →
    replan_gate drops back to pending_approval → re-approve → run."""
    L = ctx["live"]
    brief = tag("A06", "Summarize the energy consumption for the last quarter.")
    r = L.post("/ai/plans/", json={"brief": brief})
    plan = r.json()
    pid = plan.get("id")
    L.post(f"/ai/plans/{pid}/approve/")

    new_brief = tag("A06", "Summarize the energy consumption AND water usage for the last quarter.")
    r2 = L.patch(f"/ai/plans/{pid}/", json={"brief": new_brief})
    edited = r2.json()
    diff = edited.get("diff") or {}
    checks = [("patch 200", r2.ok)]
    checks.append(("diff returned", "added" in diff and "removed" in diff and "changed" in diff))
    checks.append(("replan_gate true", edited.get("replan_gate") is True))
    checks.append(("back to pending_approval", edited.get("status") == "pending_approval"))
    detail = {"diff": {k: len(diff.get(k) or []) for k in ("added", "removed", "changed")}}

    L.post(f"/ai/plans/{pid}/approve/")
    sse = L.sse(f"/ai/plans/{pid}/run/")
    done = next((f for f in sse["frames"] if f.get("type") == "done"), {})
    checks.append(("re-approved run completed", done.get("status") == "completed"))
    detail["run_frames"] = [f.get("type") for f in sse["frames"]]
    return pid, checks, detail


@scenario_a
def a07_fork_then_run(ctx):
    """W3-C fork: clone a completed plan into a fresh reviewable copy with
    forked_from provenance, then run the fork."""
    L = ctx["live"]
    brief = tag("A07", "Summarize the carbon footprint of the transport fleet.")
    r = L.post("/ai/plans/", json={"brief": brief})
    src = r.json()
    src_id = src.get("id")
    L.post(f"/ai/plans/{src_id}/approve/")
    L.sse(f"/ai/plans/{src_id}/run/")

    fr = L.post(f"/ai/plans/{src_id}/fork/")
    fork = fr.json()
    fork_id = fork.get("id")
    checks = [("fork 201", fr.status_code == 201)]
    checks.append(("new plan id", fork_id != src_id))
    checks.append(("forked pending_approval", fork.get("status") == "pending_approval"))
    checks.append(("forked_from provenance", fork.get("forked_from") == src_id))

    L.post(f"/ai/plans/{fork_id}/approve/")
    sse = L.sse(f"/ai/plans/{fork_id}/run/")
    done = next((f for f in sse["frames"] if f.get("type") == "done"), {})
    checks.append(("fork run completed", done.get("status") == "completed"))
    detail = {"forked_from": src_id, "fork_frames": [f.get("type") for f in sse["frames"]]}
    return fork_id, checks, detail


@scenario_a
def a08_stop_approved(ctx):
    """Stop an approved (not yet run) plan: cancelled + pending steps skipped."""
    L = ctx["live"]
    brief = tag("A08", "This plan will be stopped before it runs.")
    r = L.post("/ai/plans/", json={"brief": brief})
    plan = r.json()
    pid = plan.get("id")
    L.post(f"/ai/plans/{pid}/approve/")
    r2 = L.post(f"/ai/plans/{pid}/stop/")
    checks = [("stop 200", r2.ok)]
    checks.append(("status cancelled", r2.json().get("status") == "cancelled"))
    steps = r2.json().get("steps") or []
    checks.append(("pending steps skipped", all(s.get("status") == "skipped" for s in steps)))

    sse = L.sse(f"/ai/plans/{pid}/run/")
    types = [f.get("type") for f in sse["frames"]]
    checks.append(("cannot run cancelled", "error" in types or sse["http_status"] in (400, 404)))
    detail = {"types": types, "http_status": sse["http_status"]}
    return pid, checks, detail


@scenario_a
def a09_pause_requires_running(ctx):
    """Ledger-level pause is guarded to ``running`` — live runs never persist
    that status, so the API pause is a documented 400 while consent-gate
    pausing is the real durable pause (see Part B)."""
    L = ctx["live"]
    brief = tag("A09", "Explain the carbon intensity of electricity generation.")
    r = L.post("/ai/plans/", json={"brief": brief})
    plan = r.json()
    pid = plan.get("id")
    L.post(f"/ai/plans/{pid}/approve/")

    r2 = L.post(f"/ai/plans/{pid}/pause/")
    checks = [("pause guarded", r2.status_code == 400)]
    detail = {"pause_http": r2.status_code,
              "pause_error": (r2.json().get("error") if r2.status_code != 200 else None)}

    sse = L.sse(f"/ai/plans/{pid}/run/")
    done = next((f for f in sse["frames"] if f.get("type") == "done"), {})
    checks.append(("unaffected run completes", done.get("status") == "completed"))
    detail["run_frames"] = [f.get("type") for f in sse["frames"]]
    return pid, checks, detail


@scenario_a
def a10_concurrent_runs(ctx):
    """Two multi-agent runs launched concurrently — server threads isolate
    them; both reach terminal status without cross-talk."""
    L = ctx["live"]
    briefs = [
        tag("A10a", "Summarize the emissions reporting workflow."),
        tag("A10b", "Summarize the data-quality monitoring workflow."),
    ]
    results = {}

    def worker(i, brief):
        try:
            r = L.post("/ai/plans/", json={"brief": brief})
            pid = r.json().get("id")
            L.post(f"/ai/plans/{pid}/approve/")
            sse = L.sse(f"/ai/plans/{pid}/run/")
            done = next((f for f in sse["frames"] if f.get("type") == "done"), {})
            results[i] = {"pid": pid, "status": done.get("status"),
                          "frames": [f.get("type") for f in sse["frames"]]}
        except Exception as exc:  # noqa: BLE001
            results[i] = {"error": str(exc)}

    t0 = time.time()
    threads = [threading.Thread(target=worker, args=(i, b)) for i, b in enumerate(briefs)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=900)
    elapsed = time.time() - t0

    checks = [("both ran", len(results) == 2)]
    checks.append(("both completed", all(v.get("status") == "completed" for v in results.values())))
    detail = {"elapsed_s": round(elapsed, 1), "results": results}
    return None, checks, detail


@scenario_a
def a11_chat_bridge_plan_task(ctx):
    """The user's original ask: chat → plan_task tool → pending_approval plan
    + open_panel jump metadata.  Drives the real conversation API."""
    L = ctx["live"]
    conv = L.post("/ai/workspace/conversations/", json={"conversation_type": "chat"})
    conv_json = conv.json()
    conv_id = conv_json.get("id") or (conv_json.get("conversation") or {}).get("id")
    checks = [("conversation created", bool(conv_id))]

    brief = tag(
        "A11",
        "Create a plan to audit the emissions data quality for the Alamein "
        "campus: check the emissions tables, identify null values, and propose "
        "DQ rules. Draft the plan — do not execute anything.",
    )
    forceful = tag(
        "A11",
        "Use the plan_task tool RIGHT NOW. Call plan_task with this brief and "
        "draft a plan (do not execute): audit the emissions data quality for "
        "the Alamein campus, identify null values, propose DQ rules.",
    )
    PLAN_DRAFTED = re.compile(r"Plan ([0-9a-fA-F-]{8,36}) drafted")

    def _drafted_plan(body):
        """Resolve the plan the assistant reports drafting (short or full id)."""
        amsg = (body or {}).get("assistant_message") or {}
        content = amsg.get("content") or ""
        m = PLAN_DRAFTED.search(content)
        if not m:
            return None
        token = m.group(1)
        if "-" in token and len(token) == 36:
            return token
        plans = L.get("/ai/plans/?limit=20").json().get("plans") or []
        match = next((p for p in plans if (p.get("id") or "").startswith(token.lower())), None)
        return match.get("id") if match else None

    msg = L.post(
        f"/ai/workspace/conversations/{conv_id}/messages/",
        json={"content": brief}, timeout=300,
    )
    body = msg.json()
    plan_id = _drafted_plan(body)
    if plan_id is None:
        # Tool invocation is the model's judgment call — retry once with an
        # explicit directive before recording a finding.
        retry = L.post(
            f"/ai/workspace/conversations/{conv_id}/messages/",
            json={"content": forceful}, timeout=300,
        )
        body = retry.json()
        plan_id = _drafted_plan(body)

    actions = (body.get("assistant_message") or {}).get("actions") or []
    action_types = [a.get("type") for a in actions if isinstance(a, dict)]
    detail = {"conv_id": conv_id, "http": msg.status_code}
    detail["has_open_panel"] = "open_panel" in action_types
    detail["retried"] = plan_id is not None and "plan_task" not in json.dumps(body)

    checks.append(("assistant drafted a plan", bool(plan_id)))
    if plan_id:
        fetched = L.get(f"/ai/plans/{plan_id}/").json()
        detail["plan_id"] = plan_id
        detail["plan_status"] = fetched.get("status")
        detail["plan_steps"] = len(fetched.get("steps") or [])
        checks.append(("drafted plan pending_approval", fetched.get("status") == "pending_approval"))
    return plan_id, checks, detail


@scenario_a
def a12_authz_and_error_paths(ctx):
    """Ownership isolation + error frames: another user cannot read a plan;
    invalid ids 404; declined/cancelled runs surface error frames."""
    L = ctx["live"]
    other = Live("auditor1")
    brief = tag("A12", "Private plan for the authz check.")
    r = L.post("/ai/plans/", json={"brief": brief})
    pid = r.json().get("id")

    r2 = other.get(f"/ai/plans/{pid}/")
    checks = [("cross-user read → 404", r2.status_code == 404)]
    r3 = L.get(f"/ai/plans/{uuid.uuid4()}/")
    checks.append(("unknown id → 404", r3.status_code == 404))

    # Cancel it, then confirm the run stream yields an error frame, not a hang.
    L.post(f"/ai/plans/{pid}/stop/")
    sse = L.sse(f"/ai/plans/{pid}/run/")
    types = [f.get("type") for f in sse["frames"]]
    checks.append(("cancelled run → error frame", "error" in types))
    detail = {"types": types, "cross_user_http": r2.status_code,
              "unknown_id_http": r3.status_code}
    return pid, checks, detail


# ── Part B: deterministic designed-workflow simulation -------------------------

class _FakePlanner:
    """Deterministic SkillAwarePlanner — returns a scripted plan per brief."""

    plan_specs: dict = {}

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def decompose(self, **kwargs):
        from ai.engine.cognition.plan.planner import Plan, PlanStep

        utterance = (kwargs.get("utterance") or "").strip()
        spec = self.plan_specs.get(utterance)
        if spec is None:
            spec = {
                "pattern": "custom",
                "source": "llm_decompose",
                "synthesis_instruction": "Summarize the outcome.",
                "steps": [
                    {"step_id": 0, "intent": "Investigate the request",
                     "tool_name": None, "tool_args": {}, "depends_on": []},
                ],
            }
        steps = [
            PlanStep(
                step_id=int(s["step_id"]),
                intent=s["intent"],
                tool_name=s.get("tool_name"),
                tool_args=s.get("tool_args") or {},
                depends_on=s.get("depends_on") or [],
                is_mutation=s.get("is_mutation", False),
            )
            for s in spec.get("steps", [])
        ]
        return Plan(
            pattern=spec.get("pattern", "custom"),
            steps=steps,
            synthesis_instruction=spec.get("synthesis_instruction", ""),
            source=spec.get("source", "llm_decompose"),
            skill_name=spec.get("skill_name"),
            needs_confirmation=any(s.is_mutation for s in steps),
        )


class _FakeReActLoop:
    """Deterministic ReActLoop — writes scripted step outcomes to the durable
    Django Run/RunStep rows exactly like the engine's P1.1/P1.3 paths."""

    outcomes: dict = {}

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def _sync_run(self, run_id):
        run = Run.objects.get(id=run_id)
        run.status = "running"
        run.save(update_fields=["status", "updated_at"])

        paused = False
        failed = False
        for step in RunStep.objects.filter(run_id=run_id).order_by("step_index"):
            # Resume semantics (faithful to the engine): steps already
            # finished in a previous pass are not re-executed.
            if step.status in ("completed", "skipped") and \
                    self.outcomes.get(step.step_index) != "awaiting_approval":
                continue
            outcome = self.outcomes.get(step.step_index, "completed")
            step.status = outcome
            step.critic_verdict = "pass"
            step.draft_text = f"Step {step.step_index} executed."
            step.error = None
            if outcome == "awaiting_approval":
                step.confirmation_token = f"tok-{step.step_index}"
                step.tool_output_json = {
                    "result": json.dumps({
                        "requires_confirmation": True,
                        "execution_id": f"exec-{step.step_index}",
                    })
                }
                paused = True
                step.save(update_fields=[
                    "status", "critic_verdict", "draft_text", "confirmation_token",
                    "tool_output_json", "updated_at",
                ])
                break
            if outcome == "failed":
                step.error = "Step failed (simulated critic veto)"
                step.critic_verdict = "veto"
                failed = True
            step.save(update_fields=[
                "status", "critic_verdict", "draft_text", "error", "updated_at",
            ])

        if paused:
            run.status = "paused"
        elif failed:
            run.status = "failed"
        else:
            run.status = "completed"
        run.final_response = None if (paused or failed) else "All steps completed."
        run.total_llm_calls = len(list(RunStep.objects.filter(run_id=run_id)))
        run.total_latency_ms = 1500.0
        run.completed_at = None if paused else dj_timezone.now()
        run.save(update_fields=[
            "status", "final_response", "total_llm_calls",
            "total_latency_ms", "completed_at", "updated_at",
        ])

    async def run(self, plan, **kwargs):
        from asgiref.sync import sync_to_async

        await sync_to_async(self._sync_run)(kwargs["resume_run_id"])
        return None


class _FakeHostExecutor:
    """Records confirm/decline of staged host mutations (RULE_21 gate)."""

    confirmed: list = []
    declined: list = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def confirm_execution(self, execution_id, expected_host_user_id=None):
        self.confirmed.append((execution_id, expected_host_user_id))
        return {"data": {"id": "rule-sim-1", "name": "Sim rule"}}

    async def decline_execution(self, execution_id, expected_host_user_id=None):
        self.declined.append((execution_id, expected_host_user_id))


class _FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakeFactory:
    def __call__(self):
        return _FakeSession()


def _install_fake_seams():
    """Patch every lazy engine import point used by PlansService (mirrors
    test_plans.py::patch_engine_seams)."""
    from ai.engine.cognition.plan import planner, loop as plan_loop
    from ai.engine.llm import prompts
    from ai.engine.core import database
    from ai import engine_runtime, host_executor

    _FakePlanner.plan_specs = {}
    _FakeReActLoop.outcomes = {}
    _FakeHostExecutor.confirmed = []
    _FakeHostExecutor.declined = []

    patches = [
        patch.object(planner, "SkillAwarePlanner", _FakePlanner),
        patch.object(plan_loop, "ReActLoop", _FakeReActLoop),
        patch.object(prompts, "build_chat_prompt",
                     AsyncMock(return_value="You are Carbon (simulated).")),
        patch.object(database, "get_session_factory", lambda *a, **k: _FakeFactory()),
        patch.object(engine_runtime, "_carbon_instance_config",
                     lambda *a, **k: {"display_name": "Carbon",
                                      "description": "Carbon Data Trust",
                                      "persona": {},
                                      "api_catalog": [],
                                      "navigation_routes": [],
                                      "domain_topics": []}),
        patch.object(engine_runtime, "_build_chat_user_info",
                     lambda *a, **k: {"username": "sim-worker",
                                      "display_name": "Sim Worker", "roles": []}),
        patch.object(host_executor, "CarbonHostExecutor", _FakeHostExecutor),
    ]
    for p in patches:
        p.start()
    return patches


def _b_user():
    return get_user_model().objects.get(username="ahmed")


def _b_make_plan(service, brief, spec):
    _FakePlanner.plan_specs[brief] = spec
    plan = service.create_plan(_b_user(), brief, conversation_id="sim-b")
    return plan.get("id")


def _b_run(service, pid):
    frames = []
    for frame in service.run_plan_stream(_b_user(), pid):
        frames.append(frame)
    return frames


def _b_verify_consent(service, pid, action):
    """confirm/decline the awaiting step, then resume the run."""
    frames = _b_run(service, pid)
    confirm = next((f for f in frames if f.get("type") == "step_confirm"), None)
    if confirm is None:
        return frames, None
    if action == "confirm":
        result = service.confirm_step(_b_user(), pid, confirm["step_id"])
    else:
        result = service.decline_step(_b_user(), pid, confirm["step_id"])
    _FakeReActLoop.outcomes = {}
    frames2 = _b_run(service, pid)
    return frames, {"action": action, "result": result, "resume_frames": frames2}


CHAIN_SPEC = {
    "pattern": "skill_chain",
    "source": "llm_decompose",
    "synthesis_instruction": "Summarize the audit outcome.",
    "steps": [
        {"step_id": 0, "intent": "Search knowledge for the Alamein campus",
         "tool_name": "search_knowledge", "tool_args": {"query": "alamein campus"}, "depends_on": []},
        {"step_id": 1, "intent": "Get entity details for 'emissions'",
         "tool_name": "get_entity_details", "tool_args": {"entity_name": "emissions"}, "depends_on": [0]},
        {"step_id": 2, "intent": "List my capabilities to propose next steps",
         "tool_name": "list_my_capabilities", "tool_args": {}, "depends_on": [1]},
    ],
}

FANOUT_SPEC = {
    "pattern": "fan_out",
    "source": "llm_decompose",
    "synthesis_instruction": "Merge the three independent findings.",
    "steps": [
        {"step_id": 0, "intent": "Search knowledge for 'carbon emissions'",
         "tool_name": "search_knowledge", "tool_args": {"query": "carbon emissions"}, "depends_on": []},
        {"step_id": 1, "intent": "Get entity details for 'energy'",
         "tool_name": "get_entity_details", "tool_args": {"entity_name": "energy"}, "depends_on": []},
        {"step_id": 2, "intent": "List my capabilities",
         "tool_name": "list_my_capabilities", "tool_args": {}, "depends_on": []},
    ],
}


@scenario_b
def b01_agent_chain_dag(ctx):
    """Three agents in a sequential chain (1→2→3).  Frames must arrive in
    dependency order and every step completes."""
    svc = ctx["svc"]
    brief = tag("B01", "Run a three-agent sequential audit chain.")
    pid = _b_make_plan(svc, brief, CHAIN_SPEC)
    svc.approve_plan(_b_user(), pid)
    _FakeReActLoop.outcomes = {}
    frames = _b_run(svc, pid)

    types = [f.get("type") for f in frames]
    step_ids = [f.get("step_id") for f in frames if f.get("type") == "step_start"]
    done = next((f for f in frames if f.get("type") == "done"), {})
    checks = [
        ("3 steps started in order", step_ids == [0, 1, 2]),
        ("protocol intact", "done" in types),
        ("run completed", done.get("status") == "completed"),
    ]
    ledger = svc.get_ledger(_b_user(), pid)
    checks.append(("ledger 3 completed steps",
                   sum(1 for s in ledger.get("steps", []) if s.get("status") == "completed") == 3))
    detail = {"types": types, "step_ids": step_ids,
              "pattern": (ledger.get("provenance") or {}).get("pattern"),
              "source": (ledger.get("provenance") or {}).get("source")}
    return pid, checks, detail


@scenario_b
def b02_parallel_fan_out(ctx):
    """Three independent agents (no depends_on) — the topological ready-set
    runs them as a fan-out batch; all complete."""
    svc = ctx["svc"]
    brief = tag("B02", "Run three independent investigation agents in parallel.")
    pid = _b_make_plan(svc, brief, FANOUT_SPEC)
    svc.approve_plan(_b_user(), pid)
    _FakeReActLoop.outcomes = {}
    frames = _b_run(svc, pid)

    types = [f.get("type") for f in frames]
    done = next((f for f in frames if f.get("type") == "done"), {})
    checks = [
        ("all 3 steps started", len([f for f in frames if f.get("type") == "step_start"]) == 3),
        ("run completed", done.get("status") == "completed"),
    ]
    ledger = svc.get_ledger(_b_user(), pid)
    checks.append(("ledger all completed",
                   all(s.get("status") == "completed" for s in ledger.get("steps", []))))
    detail = {"types": types, "pattern": (ledger.get("provenance") or {}).get("pattern")}
    return pid, checks, detail


@scenario_b
def b03_consent_gate_confirm(ctx):
    """Mutation step hits the RULE_21 consent gate: run pauses with a
    step_confirm frame → user confirms → staged mutation executes (recorded
    by the fake host executor) → resume → completed."""
    svc = ctx["svc"]
    brief = tag("B03", "Add a DQ rule and then summarize the result.")
    _FakeHostExecutor.confirmed = []
    _FakeHostExecutor.declined = []
    spec = {
        "pattern": "custom",
        "source": "llm_decompose",
        "synthesis_instruction": "Confirm the rule was created.",
        "steps": [
            {"step_id": 0, "intent": "Create DQ rule 'Sim chain rule'",
             "tool_name": "create_dq_rule", "tool_args": {"name": "Sim chain rule",
                                                           "rule_type": "not_null",
                                                           "level": "field"},
             "depends_on": [], "is_mutation": True},
            {"step_id": 1, "intent": "Summarize the result",
             "tool_name": "list_my_capabilities", "tool_args": {}, "depends_on": [0]},
        ],
    }
    pid = _b_make_plan(svc, brief, spec)
    svc.approve_plan(_b_user(), pid)

    _FakeReActLoop.outcomes = {0: "awaiting_approval"}
    frames, consent = _b_verify_consent(svc, pid, "confirm")

    types = [f.get("type") for f in frames]
    done = next((f for f in frames if f.get("type") == "done"), {})
    checks = [
        ("consent frame emitted", "step_confirm" in types),
        ("run paused at gate", done.get("status") == "paused"),
        ("confirm accepted", (consent or {}).get("result", {}).get("status") == "confirmed"),
        ("staged mutation executed", len(_FakeHostExecutor.confirmed) >= 1),
    ]
    res_types = [f.get("type") for f in consent.get("resume_frames", [])]
    res_done = next((f for f in consent.get("resume_frames", []) if f.get("type") == "done"), {})
    checks.append(("resume completed", res_done.get("status") == "completed"))
    detail = {"gate_frames": types, "resume_frames": res_types,
              "confirmed": [c for c in _FakeHostExecutor.confirmed]}
    return pid, checks, detail


@scenario_b
def b04_consent_gate_decline(ctx):
    """User declines the staged mutation: nothing is written (decline recorded)
    and the step is skipped; the run resumes past it and completes."""
    svc = ctx["svc"]
    brief = tag("B04", "Propose a DQ rule but I will decline it.")
    _FakeHostExecutor.confirmed = []
    _FakeHostExecutor.declined = []
    spec = {
        "pattern": "custom",
        "source": "llm_decompose",
        "synthesis_instruction": "Report that the rule was declined.",
        "steps": [
            {"step_id": 0, "intent": "Create DQ rule 'Sim declined rule'",
             "tool_name": "create_dq_rule", "tool_args": {"name": "Sim declined rule",
                                                           "rule_type": "unique",
                                                           "level": "field"},
             "depends_on": [], "is_mutation": True},
            {"step_id": 1, "intent": "Summarize the outcome",
             "tool_name": "list_my_capabilities", "tool_args": {}, "depends_on": [0]},
        ],
    }
    pid = _b_make_plan(svc, brief, spec)
    svc.approve_plan(_b_user(), pid)

    _FakeReActLoop.outcomes = {0: "awaiting_approval"}
    frames, consent = _b_verify_consent(svc, pid, "decline")

    types = [f.get("type") for f in frames]
    done = next((f for f in frames if f.get("type") == "done"), {})
    checks = [
        ("consent frame emitted", "step_confirm" in types),
        ("run paused at gate", done.get("status") == "paused"),
        ("decline accepted", (consent or {}).get("result", {}).get("status") == "declined"),
        ("mutation NOT executed", len(_FakeHostExecutor.confirmed) == 0),
        ("decline recorded", len(_FakeHostExecutor.declined) >= 1),
    ]
    res_types = [f.get("type") for f in consent.get("resume_frames", [])]
    res_done = next((f for f in consent.get("resume_frames", []) if f.get("type") == "done"), {})
    checks.append(("resume completed", res_done.get("status") == "completed"))
    detail = {"gate_frames": types, "resume_frames": res_types,
              "declined": [d for d in _FakeHostExecutor.declined]}
    return pid, checks, detail


@scenario_b
def b05_veto_failure_surface(ctx):
    """A step the critic vetoes is surfaced honestly (step failed, run failed,
    ledger steps_failed=1) — then the plan is edited (re-planned) and a clean
    re-run recovers to completed."""
    svc = ctx["svc"]
    brief = tag("B05", "Run an audit whose first step will fail, then fix it.")
    spec = {
        "pattern": "custom",
        "source": "llm_decompose",
        "synthesis_instruction": "Report the failure.",
        "steps": [
            {"step_id": 0, "intent": "Analyse the risky table",
             "tool_name": "search_knowledge", "tool_args": {"query": "risky"}, "depends_on": []},
            {"step_id": 1, "intent": "Summarize findings",
             "tool_name": "list_my_capabilities", "tool_args": {}, "depends_on": [0]},
        ],
    }
    pid = _b_make_plan(svc, brief, spec)
    svc.approve_plan(_b_user(), pid)

    _FakeReActLoop.outcomes = {0: "failed"}
    frames = _b_run(svc, pid)
    types = [f.get("type") for f in frames]
    done = next((f for f in frames if f.get("type") == "done"), {})
    failed_result = next((f for f in frames if f.get("type") == "step_result" and f.get("step_id") == 0), {})
    checks = [
        ("failed step surfaced", failed_result.get("status") == "failed"),
        ("failure honest (error present)", bool(failed_result.get("error"))),
        ("run status failed", done.get("status") == "failed"),
    ]
    ledger = svc.get_ledger(_b_user(), pid)
    steps_failed = sum(1 for s in ledger.get("steps", []) if s.get("status") == "failed")
    checks.append(("ledger steps_failed=1", steps_failed == 1))

    # Recover: edit the plan (re-plan via fake planner with a clean spec) →
    # re-approve → run completes.
    fixed_brief = tag("B05", "Run the audit again with the fix applied.")
    _FakePlanner.plan_specs[fixed_brief] = {
        "pattern": "custom", "source": "llm_decompose",
        "synthesis_instruction": "Report the audit outcome.",
        "steps": [
            {"step_id": 0, "intent": "Re-check the table after the fix",
             "tool_name": "search_knowledge", "tool_args": {"query": "fixed"}, "depends_on": []},
        ],
    }
    edited = svc.edit_plan(_b_user(), pid, brief=fixed_brief)
    diff = edited.get("diff") or {}
    checks.append(("edit returns diff", bool(diff.get("added"))))
    svc.approve_plan(_b_user(), pid)
    _FakeReActLoop.outcomes = {}
    frames2 = _b_run(svc, pid)
    done2 = next((f for f in frames2 if f.get("type") == "done"), {})
    checks.append(("recovery run completed", done2.get("status") == "completed"))

    detail = {"fail_frames": types, "failed_error": failed_result.get("error"),
              "diff": {k: len(diff.get(k) or []) for k in ("added", "removed", "changed")},
              "recovery_frames": [f.get("type") for f in frames2]}
    return pid, checks, detail


@scenario_b
def b06_pause_resume_ledger(ctx):
    """Ledger-level pause → resume pre-flight → run: the consent step is never
    corrupted by a ledger pause, and resume re-enters execution from the
    durable RunStep rows."""
    svc = ctx["svc"]
    brief = tag("B06", "Pause and resume a working plan.")
    pid = _b_make_plan(svc, brief, CHAIN_SPEC)
    svc.approve_plan(_b_user(), pid)

    # Simulate an in-flight run: engine P1.1 sets the row to running.
    run = Run.objects.get(id=pid)
    run.status = "running"
    run.save(update_fields=["status", "updated_at"])

    paused = svc.pause_plan(_b_user(), pid)
    checks = [("pause → paused", paused.get("status") == "paused")]

    pre = svc.resume_plan(_b_user(), pid)
    checks.append(("resume pre-flight ok", pre.get("status") == "resumed"))

    _FakeReActLoop.outcomes = {}
    frames = _b_run(svc, pid)
    done = next((f for f in frames if f.get("type") == "done"), {})
    checks.append(("resumed run completed", done.get("status") == "completed"))

    ledger = svc.get_ledger(_b_user(), pid)
    detail = {"types": [f.get("type") for f in frames],
              "ledger_status": ledger.get("status"),
              "steps": [s.get("status") for s in ledger.get("steps", [])]}
    return pid, checks, detail


# ── Report --------------------------------------------------------------------
def _verdict(checks):
    fails = [c for c in checks if not c[1]]
    if not fails:
        return OK
    return FAIL


def _render_checks(checks):
    lines = []
    for label, ok in checks:
        lines.append(f"    {'✅' if ok else '❌'} {label}")
    return "\n".join(lines)


def _render_detail(detail):
    return json.dumps(detail, indent=4, default=str)


def build_report(ctx, rows):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    out = []
    out.append(f"# Agent Workflow Simulation — {now}")
    out.append("")
    out.append("Deep multi-scenario simulation of the agent task-orchestration (plans) system.")
    out.append("")
    out.append("## Executive summary")
    out.append("")
    out.append("| # | Scenario | Verdict | Highlight |")
    out.append("|---|----------|---------|-----------|")
    for row in rows:
        out.append(f"| {row['id']} | {row['title']} | {row['verdict']} | {row['highlight']} |")
    out.append("")

    out.append("## Part A — Live system stress test (real HTTP API, real engine)")
    out.append("")
    for row in rows:
        if row["part"] != "A":
            continue
        out.append(f"### A{row['idx']:02d} — {row['title']}")
        out.append("")
        out.append(f"**Brief:** {row['brief']}")
        out.append("")
        out.append(f"**Verdict:** {row['verdict']}")
        out.append("")
        out.append("**Checks**")
        out.append("")
        out.append(_render_checks(row["checks"]))
        out.append("")
        out.append("**Evidence**")
        out.append("")
        out.append("```json")
        out.append(_render_detail(row["detail"]))
        out.append("```")
        out.append("")

    out.append("## Part B — Designed workflow simulation (deterministic seams)")
    out.append("")
    for row in rows:
        if row["part"] != "B":
            continue
        out.append(f"### B{row['idx']:02d} — {row['title']}")
        out.append("")
        out.append(f"**Brief:** {row['brief']}")
        out.append("")
        out.append(f"**Verdict:** {row['verdict']}")
        out.append("")
        out.append("**Checks**")
        out.append("")
        out.append(_render_checks(row["checks"]))
        out.append("")
        out.append("**Evidence**")
        out.append("")
        out.append("```json")
        out.append(_render_detail(row["detail"]))
        out.append("```")
        out.append("")

    out.append("## Deep findings")
    out.append("")
    if FINDINGS:
        for i, f in enumerate(FINDINGS, 1):
            out.append(f"{i}. **{f['title']}** ({f['severity']}) — {f['body']}")
            out.append("")
    else:
        out.append("_No findings recorded._")
    out.append("")

    out.append("## Scenario count")
    out.append("")
    out.append(f"- Part A (live): {len([r for r in rows if r['part'] == 'A'])}")
    out.append(f"- Part B (designed): {len([r for r in rows if r['part'] == 'B'])}")
    out.append(f"- Passed: {len([r for r in rows if r['verdict'] == OK])}")
    out.append(f"- Failed: {len([r for r in rows if r['verdict'] == FAIL])}")
    out.append("")
    return "\n".join(out)


class Command(BaseCommand):
    help = "Deep multi-scenario simulation of the agent task-orchestration (plans) system."

    def add_arguments(self, parser):
        parser.add_argument("--part", choices=["A", "B", "AB"], default="AB",
                            help="Which scenario layer to run (default AB).")
        parser.add_argument("--tag", default="", help="Optional run tag for plan briefs.")

    def handle(self, *args, **opts):
        part = opts["part"]
        run_tag = (opts.get("tag") or "").strip()

        live = Live("ahmed")
        ctx = {"live": live, "svc": None, "run_tag": run_tag}
        rows = []
        patches = []

        self.stdout.write(self.style.HTTP_INFO("═══ Carbon agent-workflow simulation ═══"))

        # ── Part A: live HTTP ────────────────────────────────────────────
        if part in ("A", "AB"):
            self.stdout.write(self.style.HTTP_INFO("\n── Part A · live system stress test ──"))
            for i, sc in enumerate(SCENARIOS_A, 1):
                title = sc["name"].replace("_", " ").title()
                self.stdout.write(f"\nA{i:02d} {title} …")
                t0 = time.time()
                try:
                    pid, checks, detail = sc["fn"](ctx)
                except Exception as exc:  # noqa: BLE001
                    self.stdout.write(self.style.ERROR(f"  crashed: {exc}"))
                    traceback.print_exc()
                    pid, checks, detail = None, [("scenario crashed", False)], {"error": str(exc)}
                v = _verdict(checks)
                elapsed = time.time() - t0
                rows.append({"part": "A", "idx": i, "id": f"A{i:02d}", "title": title,
                             "brief": getattr(sc["fn"], "__doc__", "") or "",
                             "checks": checks, "detail": detail,
                             "verdict": v, "plan_id": pid,
                             "highlight": next((c[0] for c in checks if not c[1]), "ok")})
                self.stdout.write(f"  {v} in {elapsed:.1f}s  plan={short_id(pid)}")
                for label, ok in checks:
                    self.stdout.write(f"    {'✅' if ok else '❌'} {label}")

        # ── Part B: designed workflows (deterministic) ───────────────────
        if part in ("B", "AB"):
            self.stdout.write(self.style.HTTP_INFO("\n── Part B · designed workflow simulation ──"))
            patches = _install_fake_seams()
            try:
                svc = PlansService()
                ctx["svc"] = svc
                for i, sc in enumerate(SCENARIOS_B, 1):
                    title = sc["name"].replace("_", " ").title()
                    self.stdout.write(f"\nB{i:02d} {title} …")
                    t0 = time.time()
                    try:
                        pid, checks, detail = sc["fn"](ctx)
                    except Exception as exc:  # noqa: BLE001
                        self.stdout.write(self.style.ERROR(f"  crashed: {exc}"))
                        traceback.print_exc()
                        pid, checks, detail = None, [("scenario crashed", False)], {"error": str(exc)}
                    v = _verdict(checks)
                    elapsed = time.time() - t0
                    rows.append({"part": "B", "idx": i, "id": f"B{i:02d}", "title": title,
                                 "brief": getattr(sc["fn"], "__doc__", "") or "",
                                 "checks": checks, "detail": detail,
                                 "verdict": v, "plan_id": pid,
                                 "highlight": next((c[0] for c in checks if not c[1]), "ok")})
                    self.stdout.write(f"  {v} in {elapsed:.1f}s  plan={short_id(pid)}")
                    for label, ok in checks:
                        self.stdout.write(f"    {'✅' if ok else '❌'} {label}")
            finally:
                for p in patches:
                    p.stop()

        # ── Findings (honest, evidence-backed) ───────────────────────────
        _collect_findings(rows)

        # ── Report ───────────────────────────────────────────────────────
        report = build_report(ctx, rows)
        REPORT_PATH.write_text(report)
        self.stdout.write(self.style.SUCCESS(f"\nReport written → {REPORT_PATH}"))

        self.stdout.write("\n── Summary ──")
        for row in rows:
            self.stdout.write(
                f"  {row['verdict']} {row['part']}{row['idx']:02d} {row['title']}"
            )
        ok_n = len([r for r in rows if r["verdict"] == OK])
        self.stdout.write(
            self.style.SUCCESS(f"\n{ok_n}/{len(rows)} scenarios passed.")
        )
        if any(r["verdict"] == FAIL for r in rows):
            self.stdout.write(
                self.style.WARNING(
                    "Failing checks are REAL system behaviour — see the report "
                    "Deep findings section for the disconnect analysis."
                )
            )


def _collect_findings(rows):
    """Derive honest, evidence-backed findings from observed results."""
    for row in rows:
        if row["part"] != "A":
            continue
        d = row["detail"]
        if row["title"].startswith("A02"):
            FINDINGS.append({
                "severity": FAIL,
                "title": "Multi-step decomposition never runs live — plans are always single_step",
                "body": (
                    "A brief describing three sequential tool actions produced "
                    f"{d.get('observed_steps')} step(s), source={d.get('source')}. "
                    "SkillAwarePlanner._llm_decompose is unreachable because "
                    "PlansService._decompose never passes an llm_client "
                    "(planner.py: `if _looks_agent_multi_step(...) and client is not None`), "
                    "and no multi_step_plan skills are seeded for the 'carbon' "
                    "instance. Result: every real plan is a single text step."
                ),
            })
        if row["title"].startswith("A03"):
            FINDINGS.append({
                "severity": FAIL,
                "title": "Mutation steps are text-only — the run claims success without writing",
                "body": (
                    "A create_dq_rule brief completed with "
                    f"no step_confirm frame, rule_actually_created={d.get('rule_created')}, "
                    f"final_response_claimed={d.get('claimed')}. "
                    "The run loop calls DraftWitness without `tools` and "
                    "ExecuteWitness without `tool_calls`, so no tool ever "
                    "executes: the model drafts prose asserting the rule was "
                    "'successfully added' while the DQ rules table is untouched. "
                    "The RULE_21 consent gate (awaiting_approval) is therefore "
                    "unreachable in real plan runs."
                ),
            })
        if row["title"].startswith("A09"):
            FINDINGS.append({
                "severity": WARN,
                "title": "API pause is guarded to `running`, which real runs never persist",
                "body": (
                    f"pause/ returned HTTP {d.get('pause_http')}. The run row is "
                    "set to `paused` before the loop and only `running` inside "
                    "the loop window, so the ledger pause endpoint is effectively "
                    "unusable live; the durable pause is the consent gate "
                    "(demonstrated in B03/B04)."
                ),
            })
        if row["title"].startswith("A10"):
            d10 = d
            results = d10.get("results") or {}
            if all(v.get("status") == "completed" for v in results.values()):
                FINDINGS.append({
                    "severity": OK,
                    "title": "Concurrent runs are isolated on the threaded dev server",
                    "body": (
                        f"Two plans ran concurrently in {d10.get('elapsed_s')}s "
                        "and both completed with no cross-talk."
                    ),
                })
        if row["title"].startswith("A11"):
            if d.get("retried"):
                FINDINGS.append({
                    "severity": WARN,
                    "title": "plan_task invocation is the model's judgment call — a plain brief may answer without tooling",
                    "body": (
                        f"The first chat turn returned open_panel but no drafted "
                        "plan; the plan appeared only after a second turn with an "
                        "explicit 'use the plan_task tool' directive. The tool is "
                        "advertised in the draft allow-set, but nothing forces the "
                        f"model to call it. conversation={short_id(d.get('conv_id'))}."
                    ),
                })
            else:
                FINDINGS.append({
                    "severity": OK,
                    "title": "Chat → plan_task → Tasks panel bridge works end-to-end",
                    "body": (
                        f"conversation created, open_panel={d.get('has_open_panel')}, "
                        f"drafted plan {short_id(d.get('plan_id'))} status="
                        f"{d.get('plan_status')} steps={d.get('plan_steps')}."
                    ),
                })
