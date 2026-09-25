"""
SkillAwarePlanner — Agentic multi-step plan decomposition using skills.

PR-20: This planner searches the SkillRegistry for matching skills and produces
a Plan with tool-centric PlanSteps (tool_name + tool_args from TOOL_EXECUTORS).
Falls back to LLM decomposition if no skill matches, and to single-step for
simple queries. Distinct from the SQL-focused MultiStepPlanner.
"""
from ai.engine.cognition.phrase_tables import T
from ai.engine.pack_vocab import V
import json
import logging
import re
from dataclasses import dataclass, field

from ai.engine.core.config import get_settings

logger = logging.getLogger("pulse.cognition.plan.planner")


# ── Dataclasses ────────────────────────────────────────────────────────────────

@dataclass
class PlanStep:
    """One step in a multi-step agentic plan — NOT SQL, but tool-name + args."""
    step_id: int
    intent: str                     # natural-language description
    tool_name: str | None = None    # key in agent.tools.TOOL_EXECUTORS
    tool_args: dict = field(default_factory=dict)
    skill_name: str | None = None   # non-null if step came from a skill
    depends_on: list[int] = field(default_factory=list)
    is_mutation: bool = False
    dry_run_supported: bool = False
    agent_role: str = "orchestrator"   # AGENT_ROLES value — who executes this step
    instructions: str | None = None  # W6-E F-28: service-owned steering metadata
                                     # (edited while paused; honored on resume)
    gap: str | None = None           # I5: intent with no capability. Not a host call.
    guard: dict | None = None        # I4: {step, field, value}. Exclusive with a sibling.


@dataclass
class PlanPhase:
    """A named stage of a plan grouping steps under a strategy.

    ``strategy`` is "sequential" (steps run one at a time, in order) or
    "parallel" (independent steps run concurrently). ``step_ids`` reference
    PlanStep.step_id values in this phase. Phases give the plan a workflow
    shape beyond a flat step list — visible in chat proposals and the Tasks
    panel DAG.
    """
    phase_id: int = 0
    name: str = ""
    goal: str = ""
    strategy: str = "sequential"      # "sequential" | "parallel"
    step_ids: list[int] = field(default_factory=list)


@dataclass
class Plan:
    """A decomposed agentic plan — consumed by ReActLoop."""
    pattern: str                    # "root_cause" | "comparative" | … | "custom"
    steps: list[PlanStep]
    synthesis_instruction: str
    source: str                     # "skill" | "llm_decompose" | "single_step"
    skill_name: str | None = None
    needs_confirmation: bool = False
    phases: list[PlanPhase] = field(default_factory=list)  # workflow stages
    findings: list = field(default_factory=list)  # ADR-0052 plan-contract findings


# ── Keyword scoring ────────────────────────────────────────────────────────────

def _score_skill(skill, utterance_lower: str) -> float:
    V("t_score_a_skill_against_the_utterance")
    name_lower = skill.name.lower()
    desc_lower = (skill.description or "").lower()
    utterance_tokens = set(utterance_lower.replace("_", " ").split())

    # Direct name match is strongest signal
    if name_lower in utterance_lower or name_lower.replace("_", " ") in utterance_lower:
        score = 0.95
    else:
        name_tokens = set(name_lower.replace("_", " ").split()) - {
            "a", "an", "the", "of", "to", "and", "or", "for", "in", "on", "by",
            "run", "check", "get", "list",
        }
        name_hits = len(name_tokens & utterance_tokens)
        if name_hits > 0:
            score = min(0.55 + name_hits * 0.12, 0.9)
        else:
            # Description overlap — capped soft so weak desc hits never auto-route
            desc_tokens = set(desc_lower.replace("_", " ").split()) - {
                "a", "an", "the", "of", "to", "and", "or", "for", "in", "on", "by",
            }
            desc_hits = len(desc_tokens & utterance_tokens)
            if desc_hits >= 3:
                score = min(0.35 + desc_hits * 0.05, 0.49)
            else:
                score = 0.0

    # Learnt-signal boost (W4-D): skills with a proven success record rank
    # above cold matches at equal keyword overlap. Pure read — never writes.
    if getattr(skill, "success_rate", 0) and getattr(skill, "usage_count", 0):
        boost = min(0.1, 0.05 + 0.05 * float(skill.success_rate))
        if skill.usage_count >= 3 and skill.success_rate >= 0.75:
            boost = min(0.15, boost + 0.05)
        return min(score + boost, 0.99)
    return score


# Explicit "make this a Tasks-panel plan" — Chat PLAN FIRST / plan_task owns these.
# Must NOT skill-match into invoke_skill / silent ReAct.
_TASK_CREATION_MARKERS = T("plan/planner.py::_TASK_CREATION_MARKERS")


def _wants_explicit_task_creation(
    utterance: str,
    *,
    process_mode: str | None = None,
) -> bool:
    V("t_true_when_the_user_wants_a")
    if not utterance:
        return False
    from ai.engine.cognition.plan.process_dial import (
        is_plan_dial_turn,
        strip_pulse_mode_prefix,
    )

    if is_plan_dial_turn(utterance, process_mode):
        return True
    lower = strip_pulse_mode_prefix(utterance).lower()
    return any(m in lower for m in _TASK_CREATION_MARKERS)


# ── LLM decompose prompt (agentic tool format, not SQL) ────────────────────────

_DECOMPOSE_AGENT_PROMPT = V("t_task_plan_decompose_tool_catalog_rules")


# ── Pattern signals (reused from the SQL planner, simplified) ──────────────────

# Sequential / explicit "do several things" signals.
_MULTI_SIGNALS: list[str] = [
    " and then ", " after that ", " followed by ",
    " also ", " additionally ", " as well as ",
    "root cause", "what if",
    " both ", " each ", "multi-step", "multiple steps",
    ", and ",
    "last quarter", "last month", "last year", "year to date", "ytd",
    "by supplier", "by module", "by category", "across modules", "across suppliers",
    "top 5", "top 10", "show me", "give me",
]

# Explicit requests to plan / convert a conversation into a task. These are the
# strongest signal that the user wants decomposition, NOT a prose answer.
_PLAN_SIGNALS: list[str] = [
    "plan a ", "plan the ", "plan this", "plan an ", "plan my ",
    "make a plan", "create a plan", "draft a plan", "build a plan",
    "set up a task", "create a task", "make a task", "turn this into a task",
    "convert this into a task", "convert what we talk", "as a task",
    "break it down", "break this down", "decompose",
]

# Task verbs that imply a multi-step job (stemmed so inflections match:
# "compar" → compare/comparing/comparison/comparative; "analy" → analyze/analysis).
_TASK_VERB_STEMS: list[str] = [
    "compar", "study", "audit", "investigate", "research", "analyz", "analy",
    "assess", "evaluate", "reconcile", "benchmark", "orchestrat", "workflow",
    "summar", "aggregat", "calculat", "forecast", "trend",
    "breakdown", "distribut", "correlat",
]

# ── Deterministic mutation classification ─────────────────────────────────
# A step that writes host state (files, DB rows, host APIs) MUST carry
# is_mutation=True so the ReAct loop's pre-execution consent gate pauses it
# (RULE_21 — never auto-mutate). The LLM's decompose output is advisory only:
# it routinely marks mutation steps is_mutation=False (the export step in the
# Sprint-18 E2E was marked False and would have run without consent). Mutation
# is a CAPABILITY FACT of the tool, not a reasoning output — so the planner
# overrides it deterministically here.
#
# Tools excluded: those with their own tool-level staging
# (requires_confirmation=True) — call_host_api (non-GET), create_dq_rule,
# learn_fact, forget_fact, run_ops_workflow — already gate at execution time;
# marking them is_mutation here would double-gate. export_document writes
# files with requires_confirmation=False, so it relies on this gate.
_MUTATION_TOOL_NAMES = T("plan/planner.py::_MUTATION_TOOL_NAMES")

# Imperative action verbs — two or more distinct verbs in one brief strongly
# signal a multi-action job ("create … reuse or create … and bind …").
_ACTION_VERBS: list[str] = [
    "create", "bind", "validate", "check", "reuse", "build", "add",
    "update", "delete", "remove", "import", "export", "ingest", "attach",
    "link", "apply", "run", "populate", "finalize",
    "compute", "report", "commit", "compare", "retrieve", "fetch",
]


def _is_agent_discuss_turn(utterance: str) -> bool:
    """True on the FE-seeded Agent → Discuss turn (refine / outcome talk).

    ``buildDiscussDraft.js`` writes the plan id into that one message. The id
    is the signal — not the English sentences around it — so a pasted brief
    stays prose-only (no skill match / invoke_skill / ReAct). Later turns do
    not need this: they read the typed ``plan_revision`` question on
    ConversationState (``turn/plan_revision.py``).
    """
    if not utterance:
        return False
    from ai.engine.cognition.turn.plan_revision import _uuid_in

    return bool(_uuid_in(utterance))


def _looks_agent_multi_step(utterance: str) -> bool:
    """Does this utterance likely benefit from multi-step decomposition?

    True when the user (a) explicitly asks to plan / convert into a task,
    (b) names a multi-step job verb (compare, audit, study, …), (c) uses a
    sequential connective, or (d) stacks two or more imperative action verbs.
    A bare factual question ("what is X?") stays single-step so it answers
    with prose instead of burning an LLM decompose.
    Agent Discuss turns never look multi-step (prose refine only).
    """
    if _is_agent_discuss_turn(utterance):
        return False
    lower = utterance.lower()
    if any(s in lower for s in _MULTI_SIGNALS):
        return True
    if any(s in lower for s in _PLAN_SIGNALS):
        return True
    if any(stem in lower for stem in _TASK_VERB_STEMS):
        return True
    # Two or more distinct action verbs ⇒ a multi-action job, not a bare query.
    return sum(1 for v in _ACTION_VERBS if v in lower) >= 2


# ── Tool-args schema validation (Fix 2 — phantom-success guard) ────────────────
# The LLM decompose step routinely hallucinates tool arguments (2026-08-27:
# create_dq_rule with rule_type="general", a value outside the plugin's enum).
# Tool NAMES are validated elsewhere; the args were not — so a poisoned step
# reached the executor, the tool errored/nulled, and the step was still marked
# "completed". Validate ``tool_args`` against the plugin ``input_schema`` and
# drop the tool call when the args are structurally invalid (the step degrades
# to reasoning rather than emitting a broken tool call).


def _plugin_input_schemas() -> dict[str, dict]:
    """Map registered plugin tool name → its ``input_schema`` (JSON Schema)."""
    try:
        from ai.engine.agent.plugins import registered_plugins
        return {p.name: (p.input_schema or {}) for p in registered_plugins()}
    except Exception:  # noqa: BLE001 - validation is best-effort, never fatal
        return {}


def _schema_field_violations(prop: dict, value, path: str) -> list[str]:
    """Validate one value against the catalog's small JSON-Schema subset."""
    violations: list[str] = []

    enum = prop.get("enum")
    if enum is not None and value not in enum:
        allowed = ", ".join(repr(e) for e in enum)
        violations.append(f"{path}: invalid value {value!r} (allowed: {allowed})")

    ptype = prop.get("type")
    if ptype is None:
        return violations

    types = ptype if isinstance(ptype, list) else [ptype]
    ok = False
    for t in types:
        if t == "null" and value is None:
            ok = True
        elif t == "string" and isinstance(value, str):
            ok = True
        elif t == "integer" and isinstance(value, int) and not isinstance(value, bool):
            ok = True
        elif t == "number" and isinstance(value, (int, float)) and not isinstance(value, bool):
            ok = True
        elif t == "boolean" and isinstance(value, bool):
            ok = True
        elif t == "array" and isinstance(value, list):
            ok = True
        elif t == "object" and isinstance(value, dict):
            ok = True
    if not ok:
        violations.append(
            f"{path}: expected {'/'.join(types)}, got {type(value).__name__}"
        )
        return violations

    if isinstance(value, list) and isinstance(prop.get("items"), dict):
        for index, item in enumerate(value):
            violations.extend(
                _schema_field_violations(prop["items"], item, f"{path}[{index}]")
            )
    if isinstance(value, dict):
        nested_props = prop.get("properties") or {}
        for field in prop.get("required") or []:
            if field not in value:
                violations.append(f"missing required field {path}.{field!s}")
        for field, child in value.items():
            child_prop = nested_props.get(field)
            if child_prop is None:
                if prop.get("additionalProperties") is False:
                    violations.append(f"unknown field {path}.{field}")
                continue
            violations.extend(
                _schema_field_violations(
                    child_prop, child, f"{path}.{field}"
                )
            )
    return violations


def _schema_violations(schema: dict, args: dict) -> list[str]:
    """Validate ``args`` against a plugin ``input_schema`` (JSON-Schema subset).

    Handles ``type``, ``required`` and ``enum`` — the constructs the plugin
    schemas actually use. Kept deliberately small: it exists to catch planner
    hallucinations, not to replace the plugin's own deeper validation.
    Returns human-readable violation strings (empty = valid).
    """
    if not isinstance(args, dict):
        return ["tool_args must be a JSON object"]

    violations: list[str] = []
    for field in (schema.get("required") or []):
        if field not in args:
            violations.append(f"missing required field {field!r}")

    props = schema.get("properties") or {}
    for field, value in args.items():
        prop = props.get(field)
        if prop is None:
            if schema.get("additionalProperties") is False:
                violations.append(f"unknown field {field!r}")
            continue
        violations.extend(_schema_field_violations(prop, value, field))

    return violations


def _parse_plan_response(raw: str) -> dict | None:
    """Parse a plan object even when the provider wraps JSON in prose/fences."""
    text = (raw or "").strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except (json.JSONDecodeError, TypeError):
        pass

    decoder = json.JSONDecoder()
    for index, character in enumerate(text):
        if character != "{":
            continue
        try:
            parsed, _end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and isinstance(parsed.get("steps"), list):
            return parsed
    return None


def _strip_invalid_tool_args(steps: list[PlanStep]) -> None:
    """Drop the tool on any step whose args violate that tool's input_schema.

    Mutates ``steps`` in place. A step whose args are structurally invalid
    (missing required field, out-of-enum value, wrong type) degrades to a pure
    reasoning step (``tool_name=None``) instead of emitting a poisoned tool
    call — mirroring the existing "unknown tool name" strip.
    """
    schemas = _plugin_input_schemas()
    if not schemas:
        return
    for step in steps:
        if not step.tool_name:
            continue
        schema = schemas.get(step.tool_name)
        if schema is None:
            continue
        violations = _schema_violations(schema, step.tool_args or {})
        if violations:
            logger.warning(
                "Step %d tool=%r has invalid args (%s) — dropping the tool "
                "call so the step degrades to reasoning",
                step.step_id, step.tool_name, "; ".join(violations),
            )
            step.tool_name = None
            step.tool_args = {}
            step.is_mutation = False  # a reasoning step cannot write anything


# Intent signals that a step should PRODUCE a downloadable document, not just
# reason in prose. Requires a concrete format/export signal so a plain
# "summarize the findings" synthesis step is never coerced by accident.
_EXPORT_DOC_INTENT = re.compile(
    r"\b(?:word|docx|excel|xlsx|spreadsheet|workbook|downloadable|pdf|png|chart|pack)\b"
    r"|\b(?:export|download)\b[^.]*\b(?:report|document|workbook|spreadsheet|file|findings|brief|pack)\b"
    r"|\b(?:board[- ]ready|deliverable)\b[^.]*\b(?:report|brief|workbook|document|pack)\b"
    r"|\b(?:report|briefing)\b[^.]*\b(?:word|excel|docx|xlsx|spreadsheet|pdf|png)\b",
    re.IGNORECASE,
)

_EXPORT_UTTERANCE = re.compile(
    r"\b(?:word|docx|excel|xlsx|spreadsheet|workbook|\.docx|\.xlsx|pdf|\.pdf|png|chart|pack)\b"
    r"|\b(?:export|downloadable|board[- ]ready)\b"
    r"|\bas\s+(?:a\s+)?(?:word|excel|spreadsheet|workbook|pdf|png|pack)\b",
    re.IGNORECASE,
)


def _infer_export_format(text: str) -> str:
    """Pick export_document format from intent / brief text."""
    t = text or ""
    wants_pack = bool(re.search(r"\bpack\b|\ball\s+(?:four|formats)\b", t, re.I))
    if wants_pack:
        return "pack"
    wants_pdf = bool(re.search(r"\bpdf\b|\.pdf\b", t, re.I))
    wants_png = bool(re.search(r"\bpng\b|\bchart\b|\.png\b", t, re.I))
    wants_word = bool(re.search(r"\b(?:word|docx|\.doc)\b", t, re.I))
    wants_excel = bool(re.search(r"\b(?:excel|xlsx|spreadsheet|workbook|\.xls)\b", t, re.I))
    kinds = []
    if wants_word:
        kinds.append("docx")
    if wants_excel:
        kinds.append("xlsx")
    if wants_pdf:
        kinds.append("pdf")
    if wants_png:
        kinds.append("png")
    if len(kinds) >= 3:
        return "pack"
    if kinds == ["docx"]:
        return "docx"
    if kinds == ["xlsx"]:
        return "xlsx"
    if kinds == ["pdf"]:
        return "pdf"
    if kinds == ["png"]:
        return "png"
    if set(kinds) == {"docx", "xlsx"} or not kinds:
        return "both"
    # Mixed pair including pdf/png → pack for a complete deliverable set.
    return "pack"


def _coerce_export_steps(steps: list[PlanStep]) -> None:
    """Route tool-less document-generation steps to the export_document tool.

    Mutates ``steps`` in place. The LLM routinely marks "generate a Word/Excel
    report" as a tool-less reasoning step (``tool_name=None``), which produces
    prose but never a file. Format is inferred from the intent: 'word' → docx,
    'excel'/'workbook'/'spreadsheet' → xlsx, 'pdf'/'png'/'pack' as named,
    otherwise both. Content/table/title are generated by the LLM at execution
    from the prior findings (depends_on).

    A step that already declares its render surface (``tool_args["render"]``,
    e.g. an on-screen envelope/Mermaid chart) is not a document request: the
    word "chart" in its intent must not turn it into a file.
    """
    for step in steps:
        if step.tool_name:
            continue
        if (step.tool_args or {}).get("render"):
            continue
        intent = (step.intent or "").lower()
        if not _EXPORT_DOC_INTENT.search(intent):
            continue
        fmt = _infer_export_format(intent)
        step.tool_name = "export_document"
        args = dict(step.tool_args or {})
        args.setdefault("format", fmt)
        step.tool_args = args
        step.agent_role = "orchestrator"
        logger.info(
            "Coerced step %d to export_document (format=%s) intent=%r",
            step.step_id, fmt, (step.intent or "")[:60],
        )


def _catalog_api_names(instance_config: dict | None) -> set[str]:
    """Exact host API names from brand ``api_catalog`` (not ECF entity types)."""
    catalog = (instance_config or {}).get("api_catalog") or []
    return {ep.get("name") for ep in catalog if isinstance(ep, dict) and ep.get("name")}


def _coerce_host_api_steps(
    steps: list[PlanStep], catalog_names: set[str] | None,
    utterance: str = "",
) -> None:
    V("t_rewrite_mistaken_knowledge_entity_bindings_to")
    if not catalog_names:
        return
    domain = _plan_domain(utterance)
    for step in steps:
        args = dict(step.tool_args or {})
        # tool_name was itself a catalog name (invalid executor key → stripped
        # earlier, or still present if it somehow passed validation).
        if step.tool_name in catalog_names:
            api = step.tool_name
            if api == "create_leave_record" and "submit_my_leave" in catalog_names:
                api = "submit_my_leave"
            if (
                api == "create_attendance_permission"
                and "submit_my_attendance_permission" in catalog_names
            ):
                api = "submit_my_attendance_permission"
            api = _rewrite_domain_api(api, domain, catalog_names)
            step.tool_name = "call_host_api"
            args = {"api_name": api, **{k: v for k, v in args.items() if k != "api_name"}}
            if api == "submit_my_leave" and isinstance(args.get("body"), dict):
                args["body"] = {
                    k: v for k, v in args["body"].items() if k != V("t_employee_4")
                }
            if api == "submit_my_attendance_permission" and isinstance(args.get("body"), dict):
                args["body"] = {
                    k: v
                    for k, v in args["body"].items()
                    if k not in (V("t_employee_4"), "approved")
                }
            step.tool_args = args
            logger.info(
                "Coerced step %d tool_name → call_host_api(api_name=%r)",
                step.step_id, api,
            )
            continue

        if step.tool_name not in ("get_entity_details", "resolve_entity", "call_host_api"):
            continue

        candidate = (
            args.get("api_name")
            or args.get("entity_name")
            or args.get("entity_type")
            or args.get("name")
            or args.get("query")
        )
        if not isinstance(candidate, str) or candidate not in catalog_names:
            # Domain rewrite may still apply when api_name is already set to a
            #  API on a non- brief (candidate still in catalog).
            if (
                step.tool_name == "call_host_api"
                and isinstance(args.get("api_name"), str)
            ):
                rewritten = _rewrite_domain_api(
                    args["api_name"], domain, catalog_names,
                )
                if rewritten != args["api_name"]:
                    args["api_name"] = rewritten
                    step.tool_args = args
                    logger.info(
                        "Coerced step %d domain api → %r",
                        step.step_id, rewritten,
                    )
            continue
        if step.tool_name == "call_host_api" and args.get("api_name") == candidate:
            # Prefer self-service  submit when both catalog entries exist
            # (Agent plans historically bound create_leave_record → /-records/
            # without  → HTTP 400; /me// is the governed self path).
            if (
                candidate == "create_leave_record"
                and "submit_my_leave" in catalog_names
            ):
                candidate = "submit_my_leave"
                body = args.get("body")
                if isinstance(body, dict) and V("t_employee_4") in body:
                    body = {k: v for k, v in body.items() if k != V("t_employee_4")}
                    args["body"] = body
            if (
                candidate == "create_attendance_permission"
                and "submit_my_attendance_permission" in catalog_names
            ):
                candidate = "submit_my_attendance_permission"
                body = args.get("body")
                if isinstance(body, dict):
                    args["body"] = {
                        k: v
                        for k, v in body.items()
                        if k not in (V("t_employee_4"), "approved")
                    }
            rewritten = _rewrite_domain_api(candidate, domain, catalog_names)
            if rewritten != args.get("api_name"):
                args["api_name"] = rewritten
                if rewritten == "submit_my_attendance_permission" and isinstance(
                    args.get("body"), dict,
                ):
                    args["body"] = {
                        k: v
                        for k, v in args["body"].items()
                        if k not in (V("t_employee_4"), "approved")
                    }
                step.tool_args = args
                logger.info(
                    "Coerced step %d api_name → %r",
                    step.step_id, rewritten,
                )
            continue
        step.tool_name = "call_host_api"
        coerced_api = candidate
        if (
            candidate == "create_leave_record"
            and "submit_my_leave" in catalog_names
        ):
            coerced_api = "submit_my_leave"
        if (
            candidate == "create_attendance_permission"
            and "submit_my_attendance_permission" in catalog_names
        ):
            coerced_api = "submit_my_attendance_permission"
        coerced_api = _rewrite_domain_api(coerced_api, domain, catalog_names)
        new_args = {
            "api_name": coerced_api,
            **{k: v for k, v in args.items() if k not in (
                "api_name", "entity_name", "entity_type", "name", "query",
            )},
        }
        if coerced_api == "submit_my_attendance_permission" and isinstance(
            new_args.get("body"), dict,
        ):
            new_args["body"] = {
                k: v
                for k, v in new_args["body"].items()
                if k not in (V("t_employee_4"), "approved")
            }
        step.tool_args = new_args
        logger.info(
            "Coerced step %d → call_host_api(api_name=%r)",
            step.step_id, coerced_api,
        )

def resolve_step_write_bodies(
    steps: list[PlanStep],
    api_catalog,
    utterance: str = "",
) -> None:
    V("t_fill_the_write_slots_the_brief")
    from ai.write_slots import fill_write_body, write_slots_for

    for step in steps:
        if step.tool_name != "call_host_api":
            continue
        args = dict(step.tool_args or {})
        slots = write_slots_for(args.get("api_name"), api_catalog)
        if not slots:
            continue
        body = args.get("body") if isinstance(args.get("body"), dict) else {}
        seed = " ".join(p for p in (utterance, step.intent or "") if p)
        resolved = fill_write_body(body, slots=slots, text=seed)
        if resolved != body:
            args["body"] = resolved
            step.tool_args = args
            logger.info(
                "Resolved step %d write slots for %s (keys=%s)",
                step.step_id, args.get("api_name"), sorted(resolved.keys()),
            )


def _plan_domain(utterance: str) -> str:
    """Classify plan brief domain for API bind guards."""
    u = (utterance or "").casefold()
    if V("t_loan_request") in u or re.search(r"\bloan\b", u):
        if V("t_leave") not in u:
            return V("t_loan_2")
        # Mixed — prefer explicit process id
        if V("t_loan_request") in u and V("t_leave_request") not in u:
            return V("t_loan_2")
    if V("t_employee_onboarding") in u or "onboard" in u:
        return "onboarding"
    if V("t_attendance_permission_2") in u or V("t_attendance_permission") in u or V("t_إذن_حضور") in (utterance or ""):
        return V("t_attendance")
    if V("t_leave_request") in u or re.search(V("t_bleave_b_إجازة_اجازة"), utterance or "", re.I):
        return V("t_leave")
    if V("t_payroll") in u:
        return V("t_payroll")
    if V("t_gosi") in u or "wps" in u or "sif" in u:
        return V("t_gosi")
    return ""


def _rewrite_domain_api(
    api: str, domain: str, catalog_names: set[str],
) -> str:
    V("t_keep_leave_apis_off_loan_onboarding")
    leave_only = {"submit_my_leave", "create_leave_record", "list_my_leave", "get_my_leave_balance"}
    if domain == V("t_loan_2") and api in leave_only:
        if "submit_my_loan" in catalog_names:
            return "submit_my_loan"
        if "list_my_loans" in catalog_names:
            return "list_my_loans"
        if "list_loans" in catalog_names:
            return "list_loans"
    if domain == "onboarding" and api in leave_only:
        if "create_employee" in catalog_names:
            return "create_employee"
        if "list_employees" in catalog_names:
            return "list_employees"
    if domain == V("t_attendance"):
        if api in leave_only or api == "create_attendance_permission":
            if "submit_my_attendance_permission" in catalog_names:
                return "submit_my_attendance_permission"
        if api == "approve_attendance_permission":
            # ESS approve is Correspondence; drop admin PATCH from first-person plans
            if "list_my_attendance_permissions" in catalog_names:
                return "list_my_attendance_permissions"
    return api


def _unbind_unknown_host_api_steps(
    steps: list[PlanStep], catalog_names: set[str] | None,
) -> list[int]:
    """Degrade ``call_host_api`` steps that name no catalog API.

    The decomposer turns conditional prose ("if over band, escalate to
    Finance") into ``call_host_api(action="escalate_to_finance")``. Nothing
    validates that name until the operator clicks Approve, where the host
    executor refuses it. A step whose resolved api_name is not an exact
    catalog entry is not a host write: it becomes a reasoning step
    (``tool_name=None``, ``is_mutation=False``) so it never reaches the
    consent gate. When a secondary key (``action``/``api``/``name``) *does*
    hold a catalog name, promote it to ``api_name`` instead.

    No-op when the catalog is unknown (no instance config) — we cannot judge.
    Returns the step ids that were unbound. Mutates ``steps`` in place.
    """
    if not catalog_names:
        return []
    # Same order as PlansService._step_mutation_api_name.
    host_api_arg_keys = ("api_name", "api", "action", "name")
    unbound: list[int] = []
    for step in steps:
        if step.tool_name != "call_host_api":
            continue
        args = dict(step.tool_args or {})
        resolved: str | None = None
        for key in host_api_arg_keys:
            candidate = args.get(key)
            if isinstance(candidate, str) and candidate.strip() in catalog_names:
                resolved = candidate.strip()
                break
        if resolved is not None:
            if args.get("api_name") != resolved:
                args["api_name"] = resolved
                step.tool_args = args
                logger.info(
                    "Step %d host api promoted from secondary key → %r",
                    step.step_id, resolved,
                )
            continue
        attempted = next(
            (str(args[k]) for k in host_api_arg_keys if args.get(k)), "",
        )
        logger.warning(
            "Step %d call_host_api names no catalog API (%r) — degrading to "
            "reasoning so it cannot reach Approve",
            step.step_id, attempted,
        )
        step.tool_name = None
        step.tool_args = {}
        step.is_mutation = False
        unbound.append(step.step_id)
    return unbound


def skill_has_effect(skill) -> bool:
    """True when ``invoke_skill`` (or plan expansion) would execute something.

    A governed process, a code snippet with code, or a plan skill with at
    least one tool step. Everything else returns its recipe as data.
    """
    kind = str(getattr(skill, "kind", "") or "")
    raw = getattr(skill, "body", None) or "{}"
    try:
        body = json.loads(raw) if isinstance(raw, str) else dict(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        body = {}
    if not isinstance(body, dict):
        return False
    if body.get("process_ref"):
        return True
    if kind == "code_snippet":
        return bool(str(body.get("code") or "").strip())
    if kind == "multi_step_plan":
        return any(
            isinstance(s, dict) and s.get("tool_name")
            for s in body.get("steps") or []
        )
    return False


def _canonicalize_host_steps(
    steps: list[PlanStep], api_catalog: list | None, utterance: str = "",
) -> None:
    """Put every host step in the one shape validation, execution and repair use.

    Also fills a required enum the step's own words name exactly once, and
    points unfilled path ids at the listing step they depend on (``bind``).
    Mutates ``steps`` in place.
    """
    if not api_catalog:
        return
    from ai.engine.cognition.plan.bindings import declare_bindings
    from ai.engine.cognition.plan.catalog_args import enum_fill_from_text, parameter_values
    from ai.engine.cognition.turn.capability import host_surface

    surface = host_surface({"api_catalog": api_catalog})
    by_id = {s.step_id: s for s in steps}
    for step in steps:
        if step.tool_name != "call_host_api" or not isinstance(step.tool_args, dict):
            continue
        name = str(step.tool_args.get("api_name") or "")
        if not name:
            continue
        step.tool_args = surface.host_args(name, step.tool_args)
        schema = surface.schema(name)
        if schema and surface.arg_violations(name, step.tool_args):
            filled = enum_fill_from_text(
                schema,
                parameter_values(step.tool_args, schema),
                f"{step.intent or ''} {utterance or ''}",
            )
            if filled:
                step.tool_args = surface.host_args(name, {**step.tool_args, **filled})
            still = surface.arg_violations(name, step.tool_args)
            if still:
                logger.info(
                    "Step %d %s args still invalid at plan save (%s); the run repairs once",
                    step.step_id, name, "; ".join(still),
                )
    for step in steps:
        declare_bindings(step, by_id, surface)


def _ensure_export_deliverable(utterance: str, steps: list[PlanStep]) -> None:
    """Append an export_document step when the brief asks for a file deliverable.

    Live Agent QA: briefs that said "Word/Excel" still produced no artifacts
    because every step stayed tool-less reasoning. Coercion only rewrites
    existing intents; this adds a terminal deliverable when none exists.
    """
    if not _EXPORT_UTTERANCE.search(utterance or ""):
        return
    if any((s.tool_name or "") == "export_document" for s in steps):
        return
    fmt = _infer_export_format(utterance or "")
    next_id = max((s.step_id for s in steps), default=-1) + 1
    deps = [s.step_id for s in steps]
    steps.append(
        PlanStep(
            step_id=next_id,
            intent=f"Export findings as {fmt.upper()} deliverable",
            tool_name="export_document",
            tool_args={"format": fmt, "title": "Agent report"},
            depends_on=deps[-3:] if len(deps) > 3 else deps,
            is_mutation=True,
            agent_role="orchestrator",
        )
    )
    logger.info("Appended export_document step %d format=%s", next_id, fmt)


# ── Planner ────────────────────────────────────────────────────────────────────

class SkillAwarePlanner:
    """Agentic planner — skill-first, LLM-fallback, single-step-final.

    Workflow:
      1. Search SkillRegistry for matching skills
      2. If a multi_step_plan skill matches → parse its body steps
      3. If utterance looks multi-step → LLM decompose
      4. Else → single-step passthrough
    """

    _MATCH_THRESHOLD = 0.5

    def __init__(self, llm_client=None, model: str = ""):
        self.llm_client = llm_client
        self.model = model

    async def decompose(
        self,
        utterance: str,
        skill_registry,          # SkillRegistry instance
        llm_client=None,
        model: str = "",
        instance_id: str = "",
        user_id: str = "",
        force_decompose: bool = False,
        conversation_state=None,
    ) -> Plan:
        """Decompose utterance into a Plan.

        Args:
            utterance: the user's natural-language request
            skill_registry: SkillRegistry with Session
            llm_client: AsyncOpenAI client (uses self.llm_client if None)
            model: LLM model name (uses self.model if empty)
            instance_id: pulse instance id
            user_id: host user identifier (author_user_id)
            force_decompose: when True, always attempt LLM decomposition
                (explicit "plan this" requests) even if the heuristic signals
                don't fire; single-step remains the failure fallback.
            conversation_state: ADR-0047 ConversationState for StateBlock

        Returns:
            Plan — always non-None; source="single_step" for trivial queries
        """
        client = llm_client or self.llm_client
        model_name = model or self.model or ""

        # Agent → Discuss in Chat: never skill-match or LLM-decompose. The
        # seeded brief/outcome would otherwise route to invoke_skill.
        if _is_agent_discuss_turn(utterance) and not force_decompose:
            logger.info("SkillAwarePlanner: Agent discuss turn — single-step prose")
            return Plan(
                pattern="custom",
                steps=[PlanStep(step_id=0, intent=utterance)],
                synthesis_instruction="Respond directly to the user.",
                source="single_step",
                phases=[PlanPhase(
                    phase_id=0, name="All steps", goal="",
                    strategy="sequential", step_ids=[0],
                )],
            )

        # ── Path B hybrid: personal  /  → process dial spine ────
        # Process owns DAG; write_slots own codes/amounts; LLM must not invent
        # a freeform ESS topology.
        try:
            from asgiref.sync import sync_to_async

            from ai.engine.cognition.plan.process_dial import (
                is_personal_attendance_brief,
                is_personal_leave_brief,
                is_personal_loan_brief,
                materialize_attendance_permission_plan,
                materialize_leave_request_plan,
                materialize_loan_request_plan,
            )

            if is_personal_loan_brief(utterance):
                plan = await sync_to_async(
                    materialize_loan_request_plan, thread_sensitive=True,
                )(utterance)
                logger.info(
                    V("t_skillawareplanner_process_dial_loan_d_steps"),
                    len(plan.steps),
                )
                return plan
            if is_personal_attendance_brief(utterance):
                plan = await sync_to_async(
                    materialize_attendance_permission_plan, thread_sensitive=True,
                )(utterance)
                logger.info(
                    V("t_skillawareplanner_process_dial_attendance_d_step"),
                    len(plan.steps),
                )
                return plan
            if is_personal_leave_brief(utterance):
                plan = await sync_to_async(
                    materialize_leave_request_plan, thread_sensitive=True,
                )(utterance)
                logger.info(
                    V("t_skillawareplanner_process_dial_leave_d_steps"),
                    len(plan.steps),
                )
                return plan
        except Exception:
            logger.exception(
                "process_dial materialization failed — falling through"
            )

        # "I need a task / create a task" → Chat owns plan_task (PLAN FIRST).
        # Never hot-path a loosely matched skill (e.g.  variance) into
        # invoke_skill and fail the turn.
        skip_skill_hotpath = (
            (not force_decompose) and _wants_explicit_task_creation(utterance)
        )

        # ── Step 1: search skills ───────────────────────────────────────────
        skills = await self._search_skills(skill_registry, instance_id, user_id)
        logger.debug(
            "SkillAwarePlanner: found %d skills for instance=%s user=%s",
            len(skills), instance_id, user_id,
        )

        # ── Step 2: score and match ─────────────────────────────────────────
        utterance_lower = utterance.lower()
        scored = [(s, _score_skill(s, utterance_lower)) for s in skills]
        scored.sort(key=lambda pair: pair[1], reverse=True)

        if (
            not skip_skill_hotpath
            and scored
            and scored[0][1] >= self._MATCH_THRESHOLD
        ):
            top_skill, top_score = scored[0]
            logger.info(
                "SkillAwarePlanner: matched skill=%s score=%.2f kind=%s",
                top_skill.name, top_score, top_skill.kind,
            )
            if top_skill.kind == "multi_step_plan":
                plan = self._parse_skill_plan(top_skill)
                if plan and plan.steps:
                    logger.info("SkillAwarePlanner: using skill plan '%s'", top_skill.name)
                    return plan
            elif force_decompose:
                # Agent create/replan MUST LLM-decompose. Collapsing a
                # compute+validate+report brief into one invoke_skill step
                # is the "why single step?!" failure mode.
                logger.info(
                    "SkillAwarePlanner: force_decompose — refusing invoke_skill "
                    "collapse for skill '%s'; LLM decompose instead",
                    top_skill.name,
                )
            else:
                # Non-plan promoted skill (procedure, prompt_template, sql_macro,
                # api_call, code_snippet) — route it to invoke_skill so the matched
                # skill is actually REUSED on the hot path (Pulse 0.2 #3). source
                # must stay "skill" (not "single_step") or the runner would skip
                # the ReAct loop and never execute invoke_skill.
                logger.info(
                    "SkillAwarePlanner: routing non-plan skill '%s' to invoke_skill",
                    top_skill.name,
                )
                return Plan(
                    pattern="custom",
                    steps=[
                        PlanStep(
                            step_id=0,
                            intent=utterance,
                            tool_name="invoke_skill",
                            tool_args={"skill_name": top_skill.name},
                            skill_name=top_skill.name,
                        )
                    ],
                    synthesis_instruction="Invoke the matched skill and present its result.",
                    source="skill",
                    skill_name=top_skill.name,
                    phases=[PlanPhase(
                        phase_id=0, name="All steps", goal="",
                        strategy="sequential", step_ids=[0],
                    )],
                )
        elif skip_skill_hotpath and scored and scored[0][1] >= self._MATCH_THRESHOLD:
            logger.info(
                "SkillAwarePlanner: skipping skill hot-path '%s' (explicit task creation)",
                scored[0][0].name,
            )

        # Explicit task-creation: stay single-step so Chat proposes + plan_task.
        if skip_skill_hotpath:
            logger.info("SkillAwarePlanner: explicit task creation — single-step for plan_task")
            return Plan(
                pattern="custom",
                steps=[PlanStep(step_id=0, intent=utterance)],
                synthesis_instruction="Respond directly to the user.",
                source="single_step",
                phases=[PlanPhase(
                    phase_id=0, name="All steps", goal="",
                    strategy="sequential", step_ids=[0],
                )],
            )

        # ── Step 3: LLM decomposition fallback ──────────────────────────────
        # force_decompose bypasses the utterance heuristic: an explicit
        # "plan this" request must ALWAYS attempt LLM decomposition, even when
        # the brief doesn't hit the keyword signals. The heuristic remains for
        # the free-form chat path (TurnPipelineRunner) where a bare factual
        # question should stay single-step.
        should_decompose = force_decompose or _looks_agent_multi_step(utterance)
        if should_decompose and client is not None:
            plan = await self._llm_decompose(
                utterance, client, model_name,
                instance_id=instance_id, skills=skills, user_id=user_id,
                conversation_state=conversation_state,
            )
            if plan and plan.steps:
                logger.info("SkillAwarePlanner: LLM decomposition returned %d steps", len(plan.steps))
                return plan

        # An explicit task/plan request MUST decompose. Surface the failure
        # rather than masking it with a single-step passthrough that silently
        # does nothing — a failed decomposition is a real problem, not a plan.
        if force_decompose:
            raise ValueError(
                "Task planning failed: the planner could not decompose this "
                "brief into steps (the model returned no usable plan). Retry, "
                "or refine the brief — nothing was created."
            )

        # ── Step 4: single-step passthrough (free-form chat only) ─────────
        logger.debug("SkillAwarePlanner: single-step passthrough for utterance")
        return Plan(
            pattern="custom",
            steps=[PlanStep(step_id=0, intent=utterance)],
            synthesis_instruction="Respond directly to the user.",
            source="single_step",
            phases=[PlanPhase(
                phase_id=0, name="All steps", goal="",
                strategy="sequential", step_ids=[0],
            )],
        )

    # ── helpers ─────────────────────────────────────────────────────────────

    async def _search_skills(self, skill_registry, instance_id: str, user_id: str) -> list:
        """Return all skills available to this user: draft + user_approved + promoted."""
        skills: list = []
        if skill_registry is None:
            return skills
        try:
            # Use search with empty query to get promoted + user's own
            skills = await skill_registry.search(instance_id, user_id, "")
            logger.debug("Skill search returned %d skills", len(skills))
        except Exception:
            logger.exception("Skill search failed")
        return skills

    def _parse_skill_plan(self, skill) -> Plan | None:
        """Parse a multi_step_plan skill body into a Plan."""
        try:
            body = skill.body
            if isinstance(body, str):
                body = json.loads(body)
            steps_data = body.get("steps", [])
            steps = []
            for i, s in enumerate(steps_data):
                step = PlanStep(
                    step_id=s.get("step_id", i),
                    intent=s.get("intent", ""),
                    tool_name=s.get("tool_name"),
                    tool_args=s.get("tool_args", {}),
                    skill_name=skill.name,
                    depends_on=s.get("depends_on", []),
                    is_mutation=s.get("is_mutation", False),
                    dry_run_supported=s.get("dry_run_supported", False),
                    instructions=s.get("instructions"),
                )
                # Deterministic mutation classification (capability fact) —
                # never trust authorial is_mutation for write-capable tools.
                if step.tool_name in _MUTATION_TOOL_NAMES:
                    step.is_mutation = True
                steps.append(step)
            return Plan(
                pattern=body.get("pattern", "custom"),
                steps=steps,
                synthesis_instruction=body.get("synthesis_instruction", ""),
                source="skill",
                skill_name=skill.name,
                needs_confirmation=any(s.is_mutation for s in steps),
                phases=self._parse_phases(body, steps),
            )
        except Exception:
            logger.exception("Failed to parse skill body for '%s'", skill.name)
            return None

    async def _llm_decompose(
        self, utterance: str, llm_client, model: str, instance_id: str = "",
        skills: list | None = None, user_id: str = "",
        conversation_state=None,
    ) -> Plan | None:
        """Use LLM to decompose utterance into agentic steps."""
        from ai.engine.llm.router import route_chat
        from ai.engine.agent.tools import get_tool_executors

        _execs = await get_tool_executors()
        tool_names = sorted(_execs.keys())
        tools_list = "\n".join(f"- {n}" for n in tool_names)

        # Brand host API catalog — without this the model binds live endpoints
        # to get_entity_details (knowledge store) and Agent /balance
        # steps soft-miss (N-AG-LV-01 / SIM-20260919-N10).
        catalog_names: set[str] = set()
        api_catalog: list = []
        cfg: dict = {}
        host_api_list = "- (none configured for this instance)"
        try:
            from ai.engine_runtime import _instance_config

            cfg = _instance_config(instance_id or "", user_id or None) if instance_id else {}
            catalog_names = _catalog_api_names(cfg)
            api_catalog = list((cfg or {}).get("api_catalog") or [])
            if catalog_names:
                catalog_by_name = {
                    str(item.get("name") or ""): item
                    for item in api_catalog
                    if isinstance(item, dict) and item.get("name")
                }
                catalog_lines: list[str] = []
                for name in sorted(catalog_names):
                    item = catalog_by_name.get(name) or {}
                    method = str(item.get("method") or "GET").upper()
                    line = f"- {name} ({method})"
                    parameters = item.get("parameters")
                    if isinstance(parameters, dict) and parameters:
                        line += " params=" + json.dumps(
                            parameters,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                    catalog_lines.append(line)
                host_api_list = "\n".join(catalog_lines)
        except Exception as exc:  # noqa: BLE001 - planning must still run
            logger.warning("api_catalog load failed for plan decompose: %s", exc)
            cfg = {}

        # Only advertise real, registered skills — the LLM must never invent
        # a skill name for invoke_skill (reasoning is the LLM's job, not a
        # skill). If no skills are registered, state that clearly. A skill
        # that only hands back a recipe executes nothing, so it is no step.
        skills = [s for s in (skills or []) if skill_has_effect(s)]
        skill_names = sorted({s.name for s in skills})
        skills_list = (
            "\n".join(f"- {n}" for n in skill_names)
            if skill_names
            else "- (none registered — do NOT use invoke_skill)"
        )
        prompt = _DECOMPOSE_AGENT_PROMPT.format(
            tools_list=tools_list,
            host_api_list=host_api_list,
            skills_list=skills_list,
            task=utterance,
        )

        try:
            from ai.engine.cognition.context_pack import build_context_pack

            pack = build_context_pack(
                conversation_state,
                surface="agent_plan",
                stage="decompose",
                instance_config=cfg if isinstance(cfg, dict) else None,
                user_info={"username": user_id} if user_id else None,
                task_body=prompt,
                user_message=utterance,
                include_history=False,
                include_state=True,
                include_knowledge=False,
                include_memory=False,
            )
            router_result = await route_chat(
                task="cognition",
                instance_id=instance_id,
                conversation_id=f"plan-decompose-{instance_id}",
                messages=[
                    {"role": "system", "content": pack.system_prompt()},
                    {"role": "user", "content": pack.user_prompt() or utterance},
                ],
                temperature=0.1,
            )
            raw = router_result["content"] or ""
        except Exception as e:
            logger.warning("LLM decomposition call failed: %s", e)
            return None

        parsed = _parse_plan_response(raw)
        if parsed is None:
            logger.warning("Failed to parse plan JSON from LLM response")
            return None

        steps_data = parsed.get("steps", [])
        if not isinstance(steps_data, list):
            logger.warning("Plan JSON contains a non-list steps field")
            return None
        steps = []
        for s in steps_data:
            if not isinstance(s, dict):
                continue
            step = PlanStep(
                step_id=s.get("step_id", 0),
                intent=s.get("intent", ""),
                tool_name=s.get("tool_name"),
                tool_args=s.get("tool_args", {}),
                depends_on=s.get("depends_on", []),
                is_mutation=s.get("is_mutation", False),
                dry_run_supported=s.get("dry_run_supported", False),
                agent_role=s.get("agent_role", "orchestrator"),
                instructions=s.get("instructions"),
            )
            steps.append(step)

        from ai.engine.agent.tools import get_tool_executors
        from ai.engine.cognition.plan.contract import apply_plan_contract

        _vexecs = await get_tool_executors()
        _skill_names = {s.name for s in (skills or [])}
        # One contract. The older passes run inside it, once, in one order.
        _contract_findings = apply_plan_contract(
            steps,
            api_catalog=api_catalog,
            catalog_names=catalog_names,
            utterance=utterance,
            executors=set(_vexecs),
            skill_names=_skill_names,
        )
        if _contract_findings:
            logger.info(
                "Plan contract: %s",
                "; ".join(f"{f.code}:{f.step_id}" for f in _contract_findings),
            )

        # Governed slots + grounded dates from the brief (MDM codes, platform
        # clock) — the consent card must not re-ask what the operator stated.
        if api_catalog:
            from asgiref.sync import sync_to_async

            try:
                await sync_to_async(resolve_step_write_bodies, thread_sensitive=True)(
                    steps, api_catalog, utterance,
                )
            except Exception as exc:  # noqa: BLE001 - planning must still run
                logger.warning("write slot resolution failed: %s", exc)

        # Validate / coerce agent roles against AGENT_ROLES.
        from ai.engine.core.models import AGENT_ROLES
        for step in steps:
            if step.agent_role not in AGENT_ROLES:
                step.agent_role = "orchestrator"

        # Phases: prefer explicit phases from the LLM; fall back to a single
        # "All steps" phase so downstream phase-aware rendering always works.
        phases = self._parse_phases(parsed, steps)

        return Plan(
            pattern=parsed.get("pattern", "custom"),
            steps=steps,
            synthesis_instruction=parsed.get("synthesis_instruction", ""),
            source="llm_decompose",
            needs_confirmation=any(s.is_mutation for s in steps),
            phases=phases,
            findings=[f.as_dict() for f in _contract_findings],
        )

    @staticmethod
    def _parse_phases(parsed: dict, steps: list[PlanStep]) -> list[PlanPhase]:
        """Parse ``phases`` from an LLM decomposition result with a safe
        fallback: if the LLM omitted phases (older model / non-compliant
        JSON), derive a minimal single-phase shape from the steps.

        Steps listed in no phase are appended to a trailing "Remaining"
        phase so no step ever disappears from the workflow view.
        """
        raw_phases = parsed.get("phases") or []
        valid_ids = {s.step_id for s in steps}

        phases: list[PlanPhase] = []
        claimed: set[int] = set()
        if isinstance(raw_phases, list):
            for i, p in enumerate(raw_phases):
                if not isinstance(p, dict):
                    continue
                step_ids = [
                    int(sid) for sid in (p.get("step_ids") or [])
                    if isinstance(sid, (int, str)) and str(sid).isdigit()
                ]
                step_ids = [sid for sid in step_ids if sid in valid_ids]
                strategy = p.get("strategy", "sequential")
                if strategy not in ("sequential", "parallel"):
                    strategy = "sequential"
                phases.append(PlanPhase(
                    phase_id=i,
                    name=p.get("name") or f"Phase {i + 1}",
                    goal=p.get("goal") or "",
                    strategy=strategy,
                    step_ids=step_ids,
                ))
                claimed.update(step_ids)

        # Fallback: no phases parsed → one phase holding every step.
        if not phases:
            phases.append(PlanPhase(
                phase_id=0,
                name="All steps",
                goal="",
                strategy="sequential",
                step_ids=sorted(valid_ids),
            ))
            return phases

        # Any steps not claimed by a phase get their own trailing phase.
        unclaimed = sorted(valid_ids - claimed)
        if unclaimed:
            phases.append(PlanPhase(
                phase_id=len(phases),
                name="Remaining",
                goal="",
                strategy="sequential",
                step_ids=unclaimed,
            ))

        return phases
