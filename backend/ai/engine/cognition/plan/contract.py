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


def _declared_names(raw) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(item) for item in raw if isinstance(item, str) and item.strip()]


def _claimed_fields(step) -> list[str]:
    """Fields a step says its deliverable contains. Empty when it claims none."""
    args = getattr(step, "tool_args", None) or {}
    if not isinstance(args, dict):
        return []
    names: list[str] = []
    for key in ("produces", "columns"):
        names.extend(_declared_names(args.get(key)))
    return names


def _entry_returns(entry: dict | None) -> set[str]:
    if not isinstance(entry, dict):
        return set()
    return set(_declared_names(entry.get("returns")))


def _is_measure(name: str) -> bool:
    """Host-computed workbook measures. Row fields (id / amount) are not."""
    return name in ("average", "median", "min", "max", "total", "headcount", "count")


def _is_closed_aggregate(entry: dict | None) -> bool:
    declared = _entry_returns(entry)
    return "label" in declared and any(_is_measure(n) for n in declared)


def _closed_aggregate_sources(steps: list, catalog: list | None) -> list:
    sources = []
    for step in steps:
        if getattr(step, "tool_name", None) != "call_host_api":
            continue
        api = str((getattr(step, "tool_args", None) or {}).get("api_name") or "")
        if _is_closed_aggregate(_entry(catalog, api)):
            sources.append(step)
    return sources


def _bind_unnamed_export(step, steps: list, catalog: list | None) -> bool:
    """Name columns from closed-aggregate GETs already on the plan."""
    sources = _closed_aggregate_sources(steps, catalog)
    if not sources:
        return False
    columns: list[str] = []
    seen: set[str] = set()
    for other in sources:
        api = str((getattr(other, "tool_args", None) or {}).get("api_name") or "")
        for name in _declared_names((_entry(catalog, api) or {}).get("returns")):
            if name in seen:
                continue
            seen.add(name)
            columns.append(name)
    if not columns:
        return False
    args = dict(getattr(step, "tool_args", None) or {})
    args["columns"] = columns
    step.tool_args = args
    step.depends_on = sorted({s.step_id for s in sources})
    step.tool_name = "export_document"
    step.gap = None
    return True


def _drop_rewired_hops(steps: list, former_ancestors: set[int]) -> None:
    """Drop tool-less hops the export no longer depends on after a bind."""
    referenced: set[int] = set()
    for step in steps:
        referenced.update(getattr(step, "depends_on", None) or [])
    keep = []
    for step in steps:
        hop = (
            step.step_id in former_ancestors
            and not getattr(step, "tool_name", None)
            and step.step_id not in referenced
            and (getattr(step, "agent_role", "") or "") != REVIEW_ROLE
        )
        if not hop:
            keep.append(step)
    steps[:] = keep


def _covered_returns(step, by_id: dict, catalog: list | None) -> set[str]:
    """Fields catalog entries declare on this step and the steps it depends on."""
    covered: set[str] = set()
    pending = [step]
    seen: set[int] = set()
    while pending:
        cur = pending.pop()
        sid = getattr(cur, "step_id", None)
        if sid in seen:
            continue
        seen.add(sid)
        if getattr(cur, "tool_name", None) == "call_host_api":
            api = str((getattr(cur, "tool_args", None) or {}).get("api_name") or "")
            covered |= _entry_returns(_entry(catalog, api))
        for dep in getattr(cur, "depends_on", None) or []:
            parent = by_id.get(dep)
            if parent is not None:
                pending.append(parent)
    return covered


def _drop_export(step) -> None:
    step.gap = step.gap or "declared output"
    if step.tool_name == "export_document":
        step.tool_name = None
        step.tool_args = {}
        step.is_mutation = False


def _guard_sources(steps: list) -> set[int]:
    out: set[int] = set()
    for step in steps:
        guard = getattr(step, "guard", None) or {}
        if isinstance(guard, dict) and guard.get("step") is not None:
            try:
                out.add(int(guard["step"]))
            except (TypeError, ValueError):
                continue
    return out


def _export_ancestors(steps: list) -> set[int]:
    """Every step an export transitively depends on. Taken before exports are dropped."""
    by_id = {s.step_id: s for s in steps}
    wanted: set[int] = set()
    for step in steps:
        if getattr(step, "tool_name", None) != "export_document":
            continue
        pending = list(getattr(step, "depends_on", None) or [])
        while pending:
            sid = pending.pop()
            if sid in wanted:
                continue
            wanted.add(sid)
            parent = by_id.get(sid)
            if parent is not None:
                pending.extend(getattr(parent, "depends_on", None) or [])
    return wanted


def _step_args(step: Any) -> dict:
    if isinstance(step, dict):
        args = step.get("tool_args")
        return args if isinstance(args, dict) else {}
    args = getattr(step, "tool_args", None)
    return args if isinstance(args, dict) else {}


def _step_tool(step: Any) -> str:
    if isinstance(step, dict):
        return str(step.get("tool_name") or "")
    return str(getattr(step, "tool_name", None) or "")


def _step_is_request(step: Any, catalog: list | None = None) -> bool:
    """True when the step is the catalog's request write (kind=request)."""
    args = _step_args(step)
    if args.get("fills_gap"):
        return True
    if _step_tool(step) != "call_host_api":
        return False
    api = str(args.get("api_name") or "")
    entry = _entry(catalog, api)
    return str((entry or {}).get("kind") or "") == "request"


def _request_entry(catalog: list | None) -> dict | None:
    for item in catalog or []:
        if isinstance(item, dict) and str(item.get("kind") or "") == "request":
            return item
    return None


def blocks_create(
    findings: list[Finding] | None,
    steps: list | None = None,
    catalog: list | None = None,
) -> Finding | None:
    """A missing capability is not a plan the user can store. A request write is."""
    if any(_step_is_request(s, catalog) for s in (steps or [])):
        return None
    if any(f.code == "request" for f in (findings or [])):
        return None
    for finding in findings or []:
        if finding.blocks and finding.code in ("output_fit", "capability", "branch"):
            return finding
    return None


def offer_request_write(
    steps: list,
    catalog: list | None,
    *,
    brief: str = "",
    findings: list[Finding] | None = None,
) -> list[Finding]:
    """Append the catalog request write when output-fit blocked and none is present."""
    hits = [f for f in (findings or []) if f.blocks and f.code == "output_fit"]
    if not hits:
        return []
    if any(_step_is_request(s, catalog) for s in steps):
        return []
    entry = _request_entry(catalog)
    name = str((entry or {}).get("name") or "")
    if not name:
        return []
    from ai.engine.cognition.plan.planner import PlanStep

    body = dict((entry or {}).get("default_body") or {})
    title = (brief or "").strip() or str(body.get("title") or "Capability request")
    body["title"] = title[:200]
    body["payload"] = {
        "brief": brief,
        "findings": [f.as_dict() for f in hits],
    }
    next_id = max((s.step_id for s in steps), default=-1) + 1
    deps = sorted({f.step_id for f in hits if f.step_id is not None})
    steps.append(PlanStep(
        next_id,
        str((entry or {}).get("label") or "File a request"),
        "call_host_api",
        {"api_name": name, "fills_gap": True, **body},
        depends_on=deps,
        is_mutation=True,
    ))
    return [Finding(
        "request", next_id,
        "A request write covers the missing capability.",
        blocks=False,
    )]


def output_fit_findings(steps: list, catalog: list | None) -> list[Finding]:
    """I1 output-fit. A file may contain only fields a catalog entry declares.

    An export that names columns is a gap when those names are not in ``returns``.
    An export that names nothing is bound to closed-aggregate ``returns`` already
    on the plan; otherwise it is a gap. A row-list GET never fills an unnamed
    file — that is how a line list became a distribution workbook.
    """
    former_ancestors = _export_ancestors(steps)
    rebound = False
    for step in steps:
        if getattr(step, "tool_name", None) != "export_document":
            continue
        if _claimed_fields(step):
            continue
        if _bind_unnamed_export(step, steps, catalog):
            rebound = True
    if rebound:
        _drop_rewired_hops(steps, former_ancestors)
    by_id = {s.step_id: s for s in steps}
    out: list[Finding] = []
    ancestors = _export_ancestors(steps)
    guards = _guard_sources(steps)
    for step in steps:
        if step.step_id not in ancestors:
            continue
        if (getattr(step, "agent_role", "") or "") == REVIEW_ROLE:
            continue
        if step.step_id in guards:
            continue
        if getattr(step, "tool_name", None):
            continue
        if _claimed_fields(step):
            continue
        out.append(Finding(
            "output_fit",
            step.step_id,
            "This step has no catalog capability.",
        ))
    for step in steps:
        claimed = _claimed_fields(step)
        if step.tool_name != "export_document" and not claimed:
            continue
        covered = _covered_returns(step, by_id, catalog)
        if not claimed:
            _drop_export(step)
            out.append(Finding(
                "output_fit",
                step.step_id,
                "This export does not name the fields it will contain.",
            ))
            continue
        missing = [name for name in claimed if name not in covered]
        if not missing:
            continue
        _drop_export(step)
        out.append(Finding(
            "output_fit",
            step.step_id,
            "No catalog entry declares: " + ", ".join(missing),
        ))
    return out


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


def _coalesce_export_steps(steps: list) -> None:
    """One file-write effect. Format is a set. Sibling exports are the same effect split."""
    from ai.engine.cognition.plan.planner import _union_export_formats

    exports = [s for s in steps if getattr(s, "tool_name", None) == "export_document"]
    if len(exports) < 2:
        return
    keep = exports[0]
    formats = [
        str((getattr(s, "tool_args", None) or {}).get("format") or "")
        for s in exports
    ]
    columns: list[str] = []
    seen: set[str] = set()
    deps: set[int] = set()
    title = ""
    for step in exports:
        args = getattr(step, "tool_args", None) or {}
        for name in _declared_names(args.get("columns")):
            if name in seen:
                continue
            seen.add(name)
            columns.append(name)
        deps.update(getattr(step, "depends_on", None) or [])
        if not title:
            title = str(args.get("title") or "").strip()
    args = dict(getattr(keep, "tool_args", None) or {})
    args["format"] = _union_export_formats(formats)
    if columns:
        args["columns"] = columns
    if title and not str(args.get("title") or "").strip():
        args["title"] = title
    keep.tool_args = args
    keep.depends_on = sorted(deps)
    keep.tool_name = "export_document"
    keep.gap = None
    drop = {s.step_id for s in exports[1:]}
    steps[:] = [s for s in steps if s.step_id not in drop]


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
        _coerce_host_api_steps,
        _strip_invalid_tool_args,
        _unbind_unknown_host_api_steps,
    )

    findings: list[Finding] = []
    for step in steps:
        if bool(getattr(step, "await_user", False)):
            step.tool_name = "ask_clarification"
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
    for step in steps:
        if step.tool_name == "export_document":
            step.is_mutation = True
    _coalesce_export_steps(steps)
    fit = output_fit_findings(steps, api_catalog)
    findings.extend(fit)
    findings.extend(offer_request_write(
        steps, api_catalog, brief=utterance, findings=fit,
    ))
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
