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

    When no board exists for this plan, upserts one from the run so Canvas
    never stays on the create-time Planned seed while the header says Completed.
    """
    from accounts.models import User
    from ai.models import AIArtifact
    from ai.models.core import RunArtifact, RunStep

    run_id = str(getattr(run, "id", "") or "")
    if not run_id:
        return 0

    rows = list(RunStep.objects.filter(run_id=run_id).order_by("step_index"))
    # Prefer durable RunSteps; fall back to plan_json steps so a board still
    # shows the intended path before steps are materialised.
    if not rows:
        plan = getattr(run, "plan_json", None) or {}
        seed = layers_from_plan(plan if isinstance(plan, dict) else {})
        step_payload = list((seed.get("job_map") or {}).get("steps") or [])
    else:
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

    terminal = {"completed", "failed", "skipped"}
    settled = sum(1 for s in step_payload if (s.get("status") or "") in terminal)
    total = len(step_payload) or 1
    progress = int(round(100 * settled / total)) if step_payload else 0

    awaiting = next(
        (s for s in step_payload if (s.get("status") or "") == "awaiting_approval"),
        None,
    )
    failed = any((s.get("status") or "") == "failed" for s in step_payload)
    all_done = step_payload and settled == len(step_payload)
    run_status = str(getattr(run, "status", "") or "")

    if awaiting:
        live_status = "blocked"
        blockers = [
            f"Consent required: step {awaiting.get('id')} — {awaiting.get('title') or awaiting.get('tool') or ''}"
        ]
        pending_consent = {
            "step_id": awaiting.get("id"),
            "tool": awaiting.get("tool"),
            "intent": awaiting.get("title"),
        }
    elif failed and all_done:
        live_status = "failed"
        blockers = []
        pending_consent = None
    elif all_done or run_status in ("completed", "completed_with_gaps"):
        live_status = "completed" if run_status != "completed_with_gaps" else "partial"
        blockers = []
        pending_consent = None
        progress = 100 if all_done or run_status.startswith("completed") else progress
    elif settled > 0 or run_status == "running":
        live_status = "running"
        blockers = []
        pending_consent = None
    else:
        live_status = "planned"
        blockers = []
        pending_consent = None

    # Evidence: step summaries + deliverable names.
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
    deliverables = list(
        RunArtifact.objects.filter(run_id=run_id).order_by("created_at").values_list(
            "name", flat=True
        )[:12]
    )
    final_text = (getattr(run, "final_response", None) or "").strip()

    def _apply_layers(layers: dict) -> dict:
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
        ev = dict(layers.get("evidence") or {})
        tables = [t for t in (ev.get("tables") or []) if t.get("title") != "Step outputs"]
        if evidence_rows:
            tables = [
                {
                    "title": "Step outputs",
                    "columns": ["Step", "Tool", "Result"],
                    "rows": evidence_rows[:12],
                }
            ] + tables
        if deliverables:
            tables = [
                {
                    "title": "Deliverables",
                    "columns": ["File"],
                    "rows": [[n] for n in deliverables],
                }
            ] + [t for t in tables if t.get("title") != "Deliverables"]
        ev["tables"] = tables
        if live_status in ("completed", "partial") and not ev.get("headline"):
            ev["headline"] = (
                f"Run finished · {settled}/{total} steps settled"
                + (f" · {len(deliverables)} file(s)" if deliverables else "")
            )
        if final_text and not ev.get("prose"):
            ev["prose"] = final_text[:2000]
        layers["evidence"] = ev
        if live_status in ("completed", "partial", "failed"):
            outcome = dict(layers.get("outcome") or {})
            if final_text:
                outcome["summary"] = final_text[:800]
            elif not outcome.get("summary"):
                outcome["summary"] = (
                    f"Plan {run_id[:8]}… {live_status} ({settled}/{total} steps)."
                )
            layers["outcome"] = outcome
        return layers

    patched = 0
    for art in AIArtifact.objects.filter(artifact_type=ARTIFACT_TYPE).order_by(
        "-created_at"
    )[:80]:
        content = dict(art.content_json or {})
        if str(content.get("plan_id") or "") != run_id:
            continue
        if content.get("mode") not in (MODE_AGENT, None, ""):
            # Only Agent maps track execution; Chat briefs stay advisory.
            if content.get("mode") == MODE_CHAT:
                continue
        layers = _apply_layers(dict(content.get("layers") or {}))
        content["layers"] = layers
        content["mode"] = MODE_AGENT
        art.content_json = content
        art.save(update_fields=["content_json"])
        patched += 1
        if patched >= 3:
            break

    if patched:
        return patched

    # No board for this plan — create one so Canvas is never a stale orphan.
    conv_id = getattr(run, "conversation_id", None)
    host_uid = getattr(run, "host_user_id", None)
    if not conv_id or not host_uid:
        return 0
    try:
        user = User.objects.filter(pk=host_uid).first()
        if user is None:
            return 0
        brief = str(
            (getattr(run, "user_message", None) or "")
            or ((getattr(run, "plan_json", None) or {}).get("brief") if isinstance(getattr(run, "plan_json", None), dict) else "")
            or "Agent Job Map"
        )
        layers = _apply_layers(
            layers_from_plan(
                getattr(run, "plan_json", None)
                if isinstance(getattr(run, "plan_json", None), dict)
                else {"brief": brief, "steps": []}
            )
        )
        # Prefer RunStep-derived path over create-time collapsed plan.
        if step_payload:
            layers["job_map"] = {
                **(layers.get("job_map") or {}),
                "steps": step_payload,
                "tools": sorted({s["tool"] for s in step_payload if s.get("tool")}),
            }
        payload = build_payload(
            mode=MODE_AGENT,
            ask=brief,
            layers=layers,
            plan_id=run_id,
            conversation_id=str(conv_id),
            title=(brief[:80] or "Agent Job Map"),
        )
        upsert_job_map_artifact(
            user=user,
            conversation_id=str(conv_id),
            title=(brief[:80] or "Agent Job Map"),
            payload=payload,
        )
        return 1
    except Exception:  # noqa: BLE001 — canvas must never break the run
        logger.debug("ops_canvas ensure job map failed", exc_info=True)
        return 0


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
    """Create or update a job_map artifact on the conversation via CarbonIntelligence.

    When ``payload.plan_id`` is set, replace only the Agent map for **that**
    plan — never clobber another plan's board on the same conversation
    (that left Canvas stuck on Planned while the header showed Completed).
    """
    from ai.intelligence import CarbonIntelligence
    from ai.models import AIArtifact

    ci = CarbonIntelligence()
    existing = None
    plan_id = str((payload or {}).get("plan_id") or "")
    if replace_existing and conversation_id:
        qs = AIArtifact.objects.filter(
            conversation_id=conversation_id,
            artifact_type=ARTIFACT_TYPE,
            created_by=user,
        ).order_by("-created_at")
        if plan_id:
            for cand in qs[:40]:
                content = cand.content_json or {}
                if str(content.get("plan_id") or "") == plan_id:
                    if content.get("mode") in (MODE_AGENT, None, ""):
                        existing = cand
                        break
        else:
            existing = qs.first()

    # Stamp canvas_id into outcome after we know the id.
    if existing is not None:
        content = dict(payload)
        layers = dict(content.get("layers") or {})
        outcome = dict(layers.get("outcome") or {})
        outcome["canvas_id"] = str(existing.id)
        layers["outcome"] = outcome
        content["layers"] = layers
        content["conversation_id"] = conversation_id
        if plan_id:
            content["plan_id"] = plan_id
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
