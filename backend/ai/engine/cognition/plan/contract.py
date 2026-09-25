"""One plan contract (ADR-0052).

Typed findings. A repair is logged and non-blocking. What cannot be repaired
blocks the plan. This module is the only save-time authority: the planner
does not run the older repair passes on their own.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Finding:
    code: str
    step_id: int | None
    detail: str
    blocks: bool = True

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "step_id": self.step_id,
            "detail": self.detail,
            "blocks": self.blocks,
        }


def blocking(findings: list[Finding] | None) -> list[Finding]:
    return [f for f in (findings or []) if f.blocks]


REVIEW_ROLE = "critic"

REVIEW_INSTRUCTION = (
    "You are the reviewer for this step. Check the prior step results against the "
    "original request. End your answer with one JSON object on its own line: "
    '{"verdict": "pass" or "fail", "findings": [{"code": "...", "detail": "..."}]}. '
    "Say fail when a result is missing, empty, or does not answer the request."
)


def review_findings(steps: list) -> list[Finding]:
    """A review step reads and judges. It never calls a tool, and it needs something to judge."""
    out: list[Finding] = []
    for step in steps:
        if (getattr(step, "agent_role", "") or "") != REVIEW_ROLE:
            continue
        if getattr(step, "tool_name", None):
            out.append(Finding(
                "review", step.step_id,
                f"A review step cannot call {step.tool_name}.",
            ))
        elif not (getattr(step, "depends_on", None) or []):
            out.append(Finding(
                "review", step.step_id, "A review step has no step to review.",
            ))
    return out


def review_verdict(text: str) -> tuple[str, list[dict]]:
    """``(pass|fail, findings)`` from the last verdict object in a review. ``("", [])`` when absent."""
    import json

    decoder = json.JSONDecoder()
    body = text or ""
    index = body.rfind("{")
    while index >= 0:
        try:
            obj, _ = decoder.raw_decode(body[index:])
        except ValueError:
            obj = None
        if isinstance(obj, dict) and obj.get("verdict") in ("pass", "fail"):
            findings = [f for f in (obj.get("findings") or []) if isinstance(f, dict)]
            return str(obj["verdict"]), findings
        index = body.rfind("{", 0, index)
    return "", []


def catalog_mutation(tool_name: str | None, entry: dict | None) -> bool:
    """I2. The catalog (or the export tool) decides. The model does not."""
    if (tool_name or "") == "export_document":
        return True
    if not isinstance(entry, dict):
        return False
    if entry.get("requires_confirmation"):
        return True
    method = str(entry.get("method") or "GET").upper()
    return method not in ("GET", "HEAD", "OPTIONS")


def _entry(catalog: list | None, name: str) -> dict | None:
    for item in catalog or []:
        if isinstance(item, dict) and str(item.get("name") or "") == name:
            return item
    return None


def _depends_on(step: Any, other_id: int, by_id: dict) -> bool:
    pending = list(getattr(step, "depends_on", None) or [])
    seen: set[int] = set()
    while pending:
        sid = pending.pop()
        if sid in seen:
            continue
        seen.add(sid)
        if sid == other_id:
            return True
        parent = by_id.get(sid)
        if parent is not None:
            pending.extend(getattr(parent, "depends_on", None) or [])
    return False


def _exclusive(a: Any, b: Any) -> bool:
    ga = getattr(a, "guard", None) or {}
    gb = getattr(b, "guard", None) or {}
    if not isinstance(ga, dict) or not isinstance(gb, dict):
        return False
    if ga.get("step") is None or ga.get("step") != gb.get("step"):
        return False
    if ga.get("field") != gb.get("field"):
        return False
    return ga.get("value") != gb.get("value")


def _is_effect(step: Any) -> bool:
    return bool(getattr(step, "is_mutation", False) or getattr(step, "gap", None))


def branch_findings(steps: list) -> list[Finding]:
    """I4. Two effects neither of which depends on the other need exclusive guards."""
    by_id = {s.step_id: s for s in steps}
    effects = [s for s in steps if _is_effect(s)]
    out: list[Finding] = []
    seen: set[tuple[int, int]] = set()
    for i, a in enumerate(effects):
        for b in effects[i + 1:]:
            key = (a.step_id, b.step_id)
            if key in seen:
                continue
            seen.add(key)
            if _depends_on(a, b.step_id, by_id) or _depends_on(b, a.step_id, by_id):
                continue
            if _exclusive(a, b):
                continue
            out.append(Finding(
                "branch",
                a.step_id,
                f"Steps {a.step_id} and {b.step_id} are both effects and neither "
                "depends on the other, with no exclusive guard.",
            ))
    return out


def apply_plan_contract(
    steps: list,
    *,
    api_catalog: list | None,
    catalog_names: set[str] | None,
    utterance: str = "",
    executors: set[str] | None = None,
    skill_names: set[str] | None = None,
) -> list[Finding]:
    """Repair what is mechanical, reject what is not. Mutates ``steps``."""
    from ai.engine.cognition.plan.planner import (
        _canonicalize_host_steps,
        _coerce_export_steps,
        _coerce_host_api_steps,
        _ensure_export_deliverable,
        _strip_invalid_tool_args,
        _unbind_unknown_host_api_steps,
    )

    findings: list[Finding] = []
    names = catalog_names if catalog_names is not None else {
        str(e.get("name") or "") for e in (api_catalog or []) if isinstance(e, dict)
    }
    _coerce_host_api_steps(steps, names, utterance=utterance)
    if executors is not None:
        for step in steps:
            if step.tool_name and step.tool_name not in executors:
                findings.append(Finding(
                    "capability", step.step_id,
                    f"Unknown tool {step.tool_name}.",
                ))
                step.tool_name = None
                step.tool_args = {}
            if step.tool_name == "invoke_skill":
                skill = str((step.tool_args or {}).get("skill_name") or "")
                if skill_names is not None and skill not in skill_names:
                    step.gap = skill or "unregistered skill"
                    step.tool_name = None
                    step.tool_args = {}
                    findings.append(Finding(
                        "gap", step.step_id, f"No skill {skill}.", blocks=False,
                    ))
    _strip_invalid_tool_args(steps)
    unbound = _unbind_unknown_host_api_steps(steps, names)
    by_id = {s.step_id: s for s in steps}
    for sid in unbound:
        step = by_id.get(sid)
        if step is None:
            continue
        step.gap = step.gap or step.intent or "no capability"
        findings.append(Finding(
            "gap", sid, "No catalog capability for this step.",
        ))
    _canonicalize_host_steps(steps, api_catalog, utterance)
    for step in steps:
        if step.tool_name != "call_host_api":
            step.is_mutation = catalog_mutation(step.tool_name, None)
            continue
        api = str((step.tool_args or {}).get("api_name") or "")
        entry = _entry(api_catalog, api)
        step.is_mutation = catalog_mutation(step.tool_name, entry)
        if entry is None and api:
            step.gap = api
            step.tool_name = None
            step.tool_args = {}
            step.is_mutation = False
            findings.append(Finding(
                "capability", step.step_id, f"No catalog entry {api}.",
            ))
    # Export last, once, so an earlier pass cannot drop it and a later one put it back.
    _coerce_export_steps(steps)
    _ensure_export_deliverable(utterance, steps)
    for step in steps:
        if step.tool_name == "export_document":
            step.is_mutation = True
    findings.extend(review_findings(steps))
    findings.extend(branch_findings(steps))
    return findings


def declared_call_mismatch(step_tool_name: str | None, step_tool_args: dict | None, call: dict) -> str:
    """I6. Empty string when the call is the declaration. Else the rejected name."""
    import json

    declared = str(step_tool_name or "").strip()
    if not declared or not isinstance(call, dict):
        return ""
    fn = call.get("function") or {}
    name = str(fn.get("name") or "").strip()
    expected = str((step_tool_args or {}).get("api_name") or "").strip()
    if declared == "call_host_api" and expected and name == expected:
        return ""
    if name != declared:
        return name or "?"
    if declared != "call_host_api" or not expected:
        return ""
    raw = fn.get("arguments") or "{}"
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else dict(raw or {})
    except (json.JSONDecodeError, TypeError, ValueError):
        return name
    got = str((parsed or {}).get("api_name") or "").strip()
    if got != expected:
        return got or name
    return ""


def evidence_rows(depends_on: list | None, statuses: dict | None) -> list[dict]:
    """I3 consent card. One row per dependency: ok only when it completed with an effect."""
    rows = []
    for sid in depends_on or []:
        row = (statuses or {}).get(sid) or {}
        status = str(row.get("status") or "missing")
        failure = str(row.get("failure_class") or "")
        rows.append({
            "step_id": sid,
            "status": status,
            "failure_class": failure,
            "ok": status == "completed" and not failure,
        })
    return rows


def evidence_blocked(step: Any, results: list) -> Finding | None:
    """I3. A write or export whose dependency did not take effect."""
    if not getattr(step, "is_mutation", False):
        return None
    bad = set()
    for result in results or []:
        cls = str(getattr(result, "failure_class", "") or "")
        if cls in ("no_effect", "invalid_args", "missing_binding", "blocked_dependency", "permanent"):
            bad.add(getattr(result, "step_id", None))
        elif getattr(result, "error", None) and not getattr(result, "paused", False):
            bad.add(getattr(result, "step_id", None))
    hit = [d for d in (getattr(step, "depends_on", None) or []) if d in bad]
    if not hit:
        return None
    return Finding(
        "evidence",
        getattr(step, "step_id", None),
        f"Waiting on step {hit[0]}, which did not complete.",
    )


def _parsed(value: Any) -> Any:
    import json

    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError, ValueError):
            return None
    return value


def guard_value(payload: Any, field: str) -> tuple[bool, Any]:
    """``(found, value)`` for a guard field in a step output or an operator pick."""
    if not isinstance(payload, dict):
        return False, None
    for holder in (payload.get("guard_values"), payload, _parsed(payload.get("result"))):
        if isinstance(holder, dict) and field in holder:
            return True, holder.get(field)
    return False, None


def guard_outcome(step: Any, outputs: dict) -> str:
    """I4 at run time. ``run``, ``skip``, or ``pause``."""
    guard = getattr(step, "guard", None)
    if not isinstance(guard, dict) or guard.get("step") is None:
        return "run"
    found, value = guard_value(outputs.get(guard.get("step")), str(guard.get("field") or ""))
    if not found:
        return "pause"
    return "run" if value == guard.get("value") else "skip"


def guard_choice(step: Any) -> dict:
    """The typed question an unresolved guard asks. The operator answers for the source step."""
    guard = getattr(step, "guard", None) or {}
    field = str(guard.get("field") or "")
    value = guard.get("value")
    values = [True, False] if isinstance(value, bool) else [value]
    return {
        "kind": "guard",
        "key": field,
        "step": guard.get("step"),
        "options": [{"value": v, "label": f"{field} = {v}"} for v in values],
    }


def error_status(output: Any) -> int:
    """HTTP error status carried inside a returned tool output, else 0."""
    if not isinstance(output, dict):
        return 0
    for holder in (output, _parsed(output.get("result"))):
        if not isinstance(holder, dict):
            continue
        status = holder.get("status") if "status" in holder else holder.get("status_code")
        if isinstance(status, int) and status >= 400:
            return status
    return 0


def output_finding(step: Any, result: Any) -> Finding | None:
    """A call that returned but did not answer: an error status inside a success envelope."""
    if getattr(result, "error", None) or getattr(result, "paused", False):
        return None
    if getattr(step, "tool_name", None) != "call_host_api":
        return None
    status = error_status(getattr(result, "tool_output", None))
    if not status:
        return None
    return Finding(
        "output",
        getattr(step, "step_id", None),
        f"The host answered {status}, so the step has no result.",
    )
