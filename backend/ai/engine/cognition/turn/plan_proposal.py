"""A proposed plan is a typed object. The client paints it; the text restates it.

The plan the user reviews is the plan that is stored, so approving it cannot
approve something else (ADR-0052 I6). Nothing here writes: a proposal is a
decomposition that has not been persisted yet.
"""
from __future__ import annotations

KIND = "plan_proposal"

# A one-step read is a question the turn can answer, not a task worth a plan.
MIN_TASK_STEPS = 2

_ARG_PREVIEW_MAX = 4


def _step_effect(step: dict) -> bool:
    return bool(step.get("is_mutation")) or str(step.get("tool_name") or "") == "export_document"


def is_task_plan(plan: dict | None) -> bool:
    """True when a decomposition is a task. A single bound read is not."""
    steps = [s for s in ((plan or {}).get("steps") or []) if isinstance(s, dict)]
    if not steps:
        return False
    if len(steps) >= MIN_TASK_STEPS:
        return True
    return _step_effect(steps[0])


def revised_brief(prior: str, change: str) -> str:
    """The open draft's brief with the user's revision appended, for the planner to redo."""
    prior = " ".join((prior or "").split())
    change = " ".join((change or "").split())
    if not prior or not change or change == prior:
        return change or prior
    return f"{prior}\nRevision: {change}"


def apply_format_revision(plan: dict | None, change: str) -> dict | None:
    """Widen an existing export's format set. ``None`` when the change names no format.

    The open draft's steps stay. A format add is not a new decomposition.
    """
    from ai.engine.cognition.plan.planner import _named_export_atoms, _union_export_formats

    atoms = _named_export_atoms(change)
    if not atoms:
        return None
    raw = [s for s in ((plan or {}).get("steps") or []) if isinstance(s, dict)]
    exports = [s for s in raw if str(s.get("tool_name") or "") == "export_document"]
    if not exports:
        return None
    keep_id = exports[0].get("step_id")
    steps = []
    for step in raw:
        if str(step.get("tool_name") or "") == "export_document" and step.get("step_id") != keep_id:
            continue
        item = dict(step)
        if item.get("step_id") == keep_id:
            args = dict(item.get("tool_args") or {}) if isinstance(item.get("tool_args"), dict) else {}
            args["format"] = _union_export_formats(
                [str(args.get("format") or "")] + atoms,
            )
            item["tool_args"] = args
            item["tool_name"] = "export_document"
            item["gap"] = None
        steps.append(item)
    return {**dict(plan or {}), "steps": steps}


def _args_preview(step: dict) -> list[dict]:
    """The bound arguments worth showing, as label/value pairs."""
    args = step.get("tool_args") if isinstance(step.get("tool_args"), dict) else {}
    body = args.get("body") if isinstance(args.get("body"), dict) else {}
    out: list[dict] = []
    for holder in (body, args):
        for key, value in holder.items():
            if key.startswith("_") or key == "body":
                continue
            if value in (None, "", [], {}):
                continue
            if not isinstance(value, (str, int, float, bool)):
                continue
            out.append({"name": str(key), "value": str(value)})
            if len(out) == _ARG_PREVIEW_MAX:
                return out
    return out


def _findings_for(step_id, findings: list | None) -> list[dict]:
    out = []
    for finding in findings or []:
        as_dict = finding.as_dict() if hasattr(finding, "as_dict") else finding
        if not isinstance(as_dict, dict) or as_dict.get("step_id") != step_id:
            continue
        out.append({
            "code": str(as_dict.get("code") or ""),
            "detail": str(as_dict.get("detail") or ""),
            "blocks": bool(as_dict.get("blocks", True)),
        })
    return out


def proposal_payload(
    plan: dict | None,
    *,
    brief: str = "",
    findings: list | None = None,
) -> dict | None:
    """``None`` unless this decomposition is a reviewable task."""
    if not is_task_plan(plan):
        return None
    steps = []
    for step in (plan or {}).get("steps") or []:
        if not isinstance(step, dict):
            continue
        step_id = step.get("step_id")
        step_findings = _findings_for(step_id, findings)
        gap = str(step.get("gap") or "")
        reason = next(
            (f["detail"] for f in step_findings if f.get("blocks") and f.get("detail")),
            "",
        ) or gap
        steps.append({
            "step_id": step_id,
            "intent": str(step.get("intent") or ""),
            "tool": str(step.get("tool_name") or ""),
            "args": _args_preview(step),
            "effect": _step_effect(step),
            "gap": gap,
            "reason": reason,
            "blocked": bool(gap) or any(f["blocks"] for f in step_findings),
            "findings": step_findings,
        })
    return {
        "kind": KIND,
        "plan_id": str((plan or {}).get("id") or ""),
        "status": str((plan or {}).get("status") or ""),
        "brief": " ".join((brief or "").split()),
        "steps": steps,
        "blocked_count": sum(1 for s in steps if s["blocked"]),
        "blocks_create": any(
            f.get("blocks") and f.get("code") in ("output_fit", "capability", "branch")
            for s in steps
            for f in s["findings"]
        ) and not any(
            (isinstance(raw.get("tool_args"), dict) and raw["tool_args"].get("fills_gap"))
            or any(f.get("code") == "request" for f in _findings_for(raw.get("step_id"), findings))
            for raw in ((plan or {}).get("steps") or [])
            if isinstance(raw, dict)
        ),
    }
