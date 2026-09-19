"""Ops Canvas / Job Map — ADR-0041 typed durable board (closed kit).

Stored as ``AIArtifact`` with ``artifact_type="job_map"``. Payload lives in
``content_json`` under a stable schema (``kind=job_map``, five layers).
Never free HTML/JS from the model.
"""
from __future__ import annotations

import logging
import secrets
from typing import Any

logger = logging.getLogger("carbon.ai.ops_canvas")

ARTIFACT_TYPE = "job_map"
SCHEMA_VERSION = 1

# Modes
MODE_CHAT = "chat"
MODE_AGENT = "agent"


def empty_layers(*, mode: str = MODE_CHAT, ask: str = "", contract: str = "") -> dict:
    """Canonical empty Job Map layers (ADR-0041 §3)."""
    return {
        "intent": {
            "ask": ask or "",
            "success_criteria": "",
            "contract": contract
            or ("advisory" if mode == MODE_CHAT else "agent"),
        },
        "job_map": {
            "steps": [],
            "entities": [],
            "capabilities": [],
            "tools": [],
        },
        "live_run": {
            "progress_pct": 0,
            "status": "idle",
            "qos": None,
            "blockers": [],
            "pending_consent": None,
        },
        "evidence": {
            "tables": [],
            "charts": [],
            "sources": [],
            "caveats": [],
            "headline": "",
            "prose": "",
        },
        "outcome": {
            "summary": "",
            "sor_links": [],
            "canvas_id": "",
        },
    }


def build_payload(
    *,
    mode: str,
    ask: str = "",
    layers: dict | None = None,
    related_object: dict | None = None,
    plan_id: str | None = None,
    conversation_id: str | None = None,
    objective_id: str | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    """Assemble a Job Map content_json payload."""
    base_layers = empty_layers(mode=mode, ask=ask)
    if layers:
        for key in base_layers:
            if isinstance(layers.get(key), dict):
                base_layers[key] = {**base_layers[key], **layers[key]}
    return {
        "kind": "job_map",
        "version": SCHEMA_VERSION,
        "mode": mode if mode in (MODE_CHAT, MODE_AGENT) else MODE_CHAT,
        "title": title or (ask[:120] if ask else "Job Map"),
        "layers": base_layers,
        "related_object": related_object,
        "plan_id": plan_id,
        "conversation_id": conversation_id,
        "objective_id": objective_id,
        "share": {"token": None, "shared_at": None, "visibility": "private"},
    }


def should_emit_chat_brief(
    *,
    tool_count: int = 0,
    has_envelope: bool = False,
    multi_hop: bool = False,
    user_asked_map: bool = False,
) -> bool:
    """When-to-canvas for Chat (ADR-0041 §6) — skip short lookups."""
    if user_asked_map:
        return True
    if tool_count >= 2:
        return True
    if multi_hop and has_envelope:
        return True
    return False


def layers_from_plan(plan: dict | None) -> dict:
    """Map a plan JSON into Job Map ``job_map`` + ``live_run`` seeds."""
    plan = plan or {}
    steps_out: list[dict] = []
    raw_steps = plan.get("steps") or plan.get("phases") or []
    if isinstance(raw_steps, list):
        for i, step in enumerate(raw_steps):
            if not isinstance(step, dict):
                continue
            sid = step.get("id")
            if sid is None:
                sid = step.get("step_id", i)
            steps_out.append(
                {
                    "id": str(sid),
                    "title": str(
                        step.get("title")
                        or step.get("intent")
                        or step.get("name")
                        or step.get("description")
                        or f"Step {i + 1}"
                    )[:200],
                    "tool": str(step.get("tool") or step.get("tool_name") or ""),
                    "status": str(step.get("status") or "pending"),
                    "deps": list(step.get("depends_on") or step.get("deps") or []),
                }
            )
    brief = str(plan.get("brief") or plan.get("title") or plan.get("goal") or "")
    return {
        "intent": {
            "ask": brief,
            "success_criteria": str(
                plan.get("acceptance_criteria")
                or plan.get("synthesis_instruction")
                or ""
            ),
            "contract": "agent",
        },
        "job_map": {
            "steps": steps_out,
            "entities": list(plan.get("entities") or []),
            "capabilities": list(plan.get("required_capabilities") or []),
            "tools": sorted(
                {
                    s["tool"]
                    for s in steps_out
                    if s.get("tool")
                }
            ),
        },
        "live_run": {
            "progress_pct": 0,
            "status": "planned",
            "qos": None,
            "blockers": [],
            "pending_consent": None,
        },
    }


def sync_agent_job_map_from_run(run) -> int:
    """Refresh Agent Job Map steps + live_run from durable RunStep rows.

    Called as steps advance so the canvas tracks plan execution (not Chat).
    Matches artifacts by ``content_json.plan_id == run.id``. Returns patched count.
    """
    from ai.models import AIArtifact
    from ai.models.core import RunStep

    run_id = str(getattr(run, "id", "") or "")
    if not run_id:
        return 0

    rows = list(RunStep.objects.filter(run_id=run_id).order_by("step_index"))
    terminal = {"completed", "failed", "skipped"}
    settled = sum(1 for r in rows if (r.status or "") in terminal)
    total = len(rows) or 1
    progress = int(round(100 * settled / total)) if rows else 0

    awaiting = next(
        (r for r in rows if (r.status or "") == "awaiting_approval"),
        None,
    )
    failed = any((r.status or "") == "failed" for r in rows)
    all_done = rows and settled == len(rows)

    if awaiting:
        live_status = "blocked"
        blockers = [f"Consent required: step {awaiting.step_index} — {awaiting.intent or awaiting.tool_name or ''}"]
        pending_consent = {
            "step_id": awaiting.step_index,
            "tool": awaiting.tool_name,
            "intent": awaiting.intent,
        }
    elif failed and all_done:
        live_status = "failed"
        blockers = []
        pending_consent = None
    elif all_done:
        live_status = "completed"
        blockers = []
        pending_consent = None
        progress = 100
    elif settled > 0:
        live_status = "running"
        blockers = []
        pending_consent = None
    else:
        live_status = "planned"
        blockers = []
        pending_consent = None

    step_payload = [
        {
            "id": str(r.step_index),
            "title": str(r.intent or r.tool_name or f"Step {r.step_index}")[:200],
            "tool": str(r.tool_name or ""),
            "status": str(r.status or "pending"),
            "deps": list(r.depends_on_json or []),
        }
        for r in rows
    ]

    # Evidence: pull tool outputs briefly from completed steps.
    evidence_rows = []
    for r in rows:
        if (r.status or "") != "completed":
            continue
        out = r.tool_output_json
        if isinstance(out, dict) and out:
            evidence_rows.append(
                [
                    str(r.step_index),
                    str(r.tool_name or ""),
                    str(out.get("summary") or out.get("ok") or "ok")[:120],
                ]
            )

    patched = 0
    for art in AIArtifact.objects.filter(artifact_type=ARTIFACT_TYPE).order_by(
        "-created_at"
    )[:80]:
        content = dict(art.content_json or {})
        if content.get("plan_id") != run_id:
            continue
        if content.get("mode") != MODE_AGENT:
            continue
        layers = dict(content.get("layers") or {})
        job = dict(layers.get("job_map") or {})
        if step_payload:
            job["steps"] = step_payload
            job["tools"] = sorted({s["tool"] for s in step_payload if s.get("tool")})
        layers["job_map"] = job
        live = dict(layers.get("live_run") or {})
        live["progress_pct"] = progress
        live["status"] = live_status
        live["blockers"] = blockers
        live["pending_consent"] = pending_consent
        layers["live_run"] = live
        if evidence_rows:
            ev = dict(layers.get("evidence") or {})
            ev["tables"] = [
                {
                    "title": "Step outputs",
                    "columns": ["Step", "Tool", "Result"],
                    "rows": evidence_rows[:12],
                }
            ] + [t for t in (ev.get("tables") or []) if t.get("title") != "Step outputs"]
            if live_status == "completed" and not ev.get("headline"):
                ev["headline"] = f"Run finished · {settled}/{total} steps settled"
            layers["evidence"] = ev
        if live_status == "completed":
            outcome = dict(layers.get("outcome") or {})
            if not outcome.get("summary"):
                outcome["summary"] = (
                    f"Plan {run_id[:8]}… completed ({settled}/{total} steps)."
                )
            layers["outcome"] = outcome
        content["layers"] = layers
        art.content_json = content
        art.save(update_fields=["content_json"])
        patched += 1
        if patched >= 3:
            break
    return patched


def layers_from_envelope_and_tools(
    *,
    ask: str,
    envelope: dict | None,
    tool_trace: list | None,
    contract: str = "advisory",
) -> dict:
    """Chat Job Brief layers from synthesis envelope + tool_trace."""
    env = envelope if isinstance(envelope, dict) else {}
    tools: list[str] = []
    steps: list[dict] = []
    for i, tr in enumerate(tool_trace or []):
        if not isinstance(tr, dict):
            continue
        name = str(tr.get("tool") or tr.get("tool_name") or tr.get("tool_id") or "")
        if name:
            tools.append(name)
        steps.append(
            {
                "id": f"t{i}",
                "title": str(tr.get("step_label") or name or f"Tool {i + 1}")[:200],
                "tool": name,
                "status": "done",
                "deps": [],
            }
        )
    return {
        "intent": {
            "ask": ask,
            "success_criteria": "",
            "contract": contract,
        },
        "job_map": {
            "steps": steps,
            "entities": [],
            "capabilities": [],
            "tools": sorted(set(tools)),
        },
        "live_run": {
            "progress_pct": 100 if steps else 0,
            "status": "complete" if steps else "idle",
            "qos": None,
            "blockers": [],
            "pending_consent": None,
        },
        "evidence": {
            "tables": list(env.get("tables") or []),
            "charts": list(env.get("charts") or []),
            "sources": list(env.get("sources") or []),
            "caveats": list(env.get("caveats") or []),
            "headline": str(env.get("headline") or ""),
            "prose": str(env.get("prose") or "")[:2000],
        },
        "outcome": {
            "summary": str(env.get("headline") or env.get("prose") or "")[:500],
            "sor_links": [],
            "canvas_id": "",
        },
    }


def upsert_job_map_artifact(
    *,
    user,
    conversation_id: str,
    title: str,
    payload: dict,
    message_id: str | None = None,
    visibility: str = "private",
    replace_existing: bool = True,
) -> dict[str, Any]:
    """Create or update a job_map artifact on the conversation via CarbonIntelligence."""
    from ai.intelligence import CarbonIntelligence
    from ai.models import AIArtifact

    ci = CarbonIntelligence()
    existing = None
    if replace_existing and conversation_id:
        existing = (
            AIArtifact.objects.filter(
                conversation_id=conversation_id,
                artifact_type=ARTIFACT_TYPE,
                created_by=user,
            )
            .order_by("-created_at")
            .first()
        )

    # Stamp canvas_id into outcome after we know the id.
    if existing is not None:
        content = dict(payload)
        layers = dict(content.get("layers") or {})
        outcome = dict(layers.get("outcome") or {})
        outcome["canvas_id"] = str(existing.id)
        layers["outcome"] = outcome
        content["layers"] = layers
        content["conversation_id"] = conversation_id
        return ci.update_artifact(
            user,
            str(existing.id),
            title=title[:255],
            content_json=content,
            visibility=visibility,
        )

    created = ci.create_artifact(
        user=user,
        conversation_id=conversation_id,
        title=title[:255],
        artifact_type=ARTIFACT_TYPE,
        content_json=payload,
        message_id=message_id,
        visibility=visibility,
    )
    # Patch canvas_id now that we have an id.
    aid = str(created.get("id") or "")
    if aid:
        content = dict(created.get("content_json") or payload)
        layers = dict(content.get("layers") or {})
        outcome = dict(layers.get("outcome") or {})
        outcome["canvas_id"] = aid
        layers["outcome"] = outcome
        content["layers"] = layers
        try:
            return ci.update_artifact(user, aid, content_json=content)
        except Exception:  # noqa: BLE001 — best-effort stamp
            logger.debug("ops_canvas canvas_id stamp failed", exc_info=True)
    return created


def patch_live_run_qos(
    *,
    conversation_id: str | None,
    plan_id: str | None,
    acceptance: dict | None,
    progress_pct: int | None = None,
    status: str | None = None,
) -> int:
    """Mirror FlightDirector acceptance into Job Map ``live_run`` (best-effort).

    Prefer ``content_json.plan_id == plan_id``; fall back to conversation-scoped
    Agent maps. Returns count of rows patched.
    """
    from ai.models import AIArtifact

    if not acceptance and progress_pct is None and status is None:
        return 0

    candidates = list(
        AIArtifact.objects.filter(artifact_type=ARTIFACT_TYPE)
        .order_by("-created_at")[:120]
    )
    patched = 0
    for art in candidates:
        content = dict(art.content_json or {})
        art_plan = content.get("plan_id")
        same_conv = (
            conversation_id
            and str(art.conversation_id) == str(conversation_id)
        )
        if plan_id and art_plan == plan_id:
            match = True
        elif plan_id and same_conv and not art_plan:
            match = True
        elif not plan_id and same_conv:
            match = True
        else:
            match = False
        if not match:
            continue

        layers = dict(content.get("layers") or {})
        live = dict(layers.get("live_run") or {})
        acc = acceptance or {}
        live["qos"] = {
            "acceptance_status": acc.get("status"),
            "requirements_total": acc.get("requirements_total"),
            "requirements_met": acc.get("requirements_met"),
            "requirements_partial": acc.get("requirements_partial"),
            "requirements_missed": acc.get("requirements_missed"),
        }
        if status:
            live["status"] = status
        elif acc.get("status") == "met":
            live["status"] = "completed"
            live["progress_pct"] = 100
        elif acc.get("status"):
            live["status"] = str(acc.get("status"))
        if progress_pct is not None:
            live["progress_pct"] = int(progress_pct)
        layers["live_run"] = live
        content["layers"] = layers
        art.content_json = content
        art.save(update_fields=["content_json"])
        patched += 1
        if plan_id and patched >= 3:
            break
    return patched


def issue_share_token(artifact_row) -> str:
    """Generate a share token on the artifact content_json (owner-gated elsewhere)."""
    content = dict(artifact_row.content_json or {})
    share = dict(content.get("share") or {})
    token = secrets.token_urlsafe(24)
    from django.utils import timezone

    share["token"] = token
    share["shared_at"] = timezone.now().isoformat()
    share["visibility"] = "shared"
    content["share"] = share
    artifact_row.content_json = content
    artifact_row.visibility = "shared"
    artifact_row.save(update_fields=["content_json", "visibility"])
    return token


def get_by_share_token(token: str):
    """Resolve a shared job_map by token (read-only snapshot)."""
    from ai.models import AIArtifact

    if not token or len(token) < 16:
        return None
    for art in AIArtifact.objects.filter(
        artifact_type=ARTIFACT_TYPE, visibility="shared"
    ).order_by("-created_at")[:200]:
        share = (art.content_json or {}).get("share") or {}
        if share.get("token") == token:
            return art
    return None
