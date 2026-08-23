"""
Flight Director — in-loop supervisor (Phase 25-B) + acceptance closure (25-C).

Additive supervision layered over the ReAct loop:

  * ``WorkingMemoryLedger`` — parses created entities out of tool outputs and
    validates reference args against read-only host GETs, rewriting stale ids
    that unambiguously map to an earlier-created entity.
  * ``contract_gate`` — deterministic artifact-noun coverage check plus
    per-step acceptance-criteria suggestions (never blocks; records only).
  * ``prepare_step`` — per-step prep: corrected tool args, extra
    instructions, escalation model override.
  * ``on_step_completed`` — ledger update + worker-fidelity guard.
  * ``run_acceptance_checks`` — post-run re-queries (read-only host GETs) of
    every step's acceptance criterion (spec §3.5) with the bounded repair
    loop: ``missed`` → repair instructions with the ACTUAL diff → re-execute
    non-mutation steps (≤ ``AI_FLIGHT_DIRECTOR_MAX_REPAIRS``) → escalate.
  * ``build_acceptance_report`` — idempotent ``AcceptanceReport`` row per run
    (spec §3.6) + outcome summary appended to ``working_notes.flight``.

Every engine hook is guarded on ``flight_director is not None`` in the loop, so
the loop behaves identically when the director is absent (additive-only,
RULE_6). The director itself never blocks a run and never mutates host data on
its own: reference existence checks are read-only GETs, and the fidelity guard
never auto re-runs a mutation step (RULE_21).
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger("carbon.ai.flight_director")

# Engine instance namespace for playbook rows — matches
# ``ai.plans_service.PLAN_INSTANCE_ID`` (single-tenant Carbon).
_PLAYBOOK_INSTANCE_ID = "carbon"

# Reference arg keys whose values are host entity ids the director validates.
_REFERENCE_ARG_KEYS = (
    "rule",
    "rule_id",
    "data_table",
    "table_id",
    "data_field",
    "dq_rule_ids",
    "module_id",
)

# Reference key → ledger kind.
_REFERENCE_KEY_KIND = {
    "rule": "rule",
    "rule_id": "rule",
    "dq_rule_ids": "rule",
    "data_table": "table",
    "table_id": "table",
    "data_field": "field",
    "module_id": "module",
}

# Kinds that have a read-only list endpoint for existence checks. Others are
# validated against the ledger only (no host round-trip, no false positives).
_LISTABLE_KINDS = {"rule", "table"}

# Artifact-noun category words the contract gate scans for in a brief.
_ARTIFACT_NOUNS = (
    "table", "rule", "field", "binding", "report", "export",
)

# Endpoint fragment → ledger kind (for ``call_host_api`` inference).
_ENDPOINT_KIND = (
    ("dq/rules", "rule"),
    ("rule-assignment", "binding"),
    ("rule_assignment", "binding"),
    ("dataschema/tables", "table"),
    ("export", "artifact"),
)


# ── Dataclasses ────────────────────────────────────────────────────────────────


@dataclass
class LedgerEntity:
    """One entity a prior step is known to have created."""
    kind: str
    id: Any
    name: str | None = None
    step_index: int | None = None


@dataclass
class StepPrep:
    """``prepare_step`` output — applied additively to the draft prompt."""
    corrected_tool_args: dict | None = None
    extra_instructions: str | None = None
    model_override: str | None = None
    repair_kind: str | None = None
    repair_detail: str | None = None


@dataclass
class StepFlightVerdict:
    """``on_step_completed`` output — ledger + fidelity verdict."""
    declared: int = 0
    executed: int = 0
    fidelity_failure: bool = False
    requests_rerun: bool = False
    escalated: bool = False
    repair_kind: str | None = None
    repair_detail: str | None = None
    extra_instructions: str | None = None


# ── Helpers ────────────────────────────────────────────────────────────────────


def _parse_json(raw: Any) -> dict | list | None:
    """Parse a tool ``result`` payload (JSON string or dict) to a dict/list."""
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None
    return None


def _kind_from_endpoint(endpoint: str | None) -> str:
    ep = (endpoint or "").lower()
    for fragment, kind in _ENDPOINT_KIND:
        if fragment in ep:
            return kind
    return "host"


def _extract_results(resp: dict) -> list[dict]:
    """Pull the list of result dicts out of a host list response."""
    if not isinstance(resp, dict):
        return []
    data = resp.get("data")
    if isinstance(data, dict):
        results = data.get("results")
        if isinstance(results, list):
            return [r for r in results if isinstance(r, dict)]
    results = resp.get("results")
    if isinstance(results, list):
        return [r for r in results if isinstance(r, dict)]
    return []


# Generic words that never count as "overlap" evidence between an entity name
# and a step intent (they appear in nearly every rule/table/binding phrase).
_REFERENCE_STOPWORDS = frozenset({
    "a", "an", "and", "at", "bind", "binding", "bindings", "check", "checks",
    "create", "created", "data", "field", "fields", "for", "in", "of", "on",
    "or", "rule", "rules", "table", "tables", "the", "to", "with",
})


def _significant_tokens(text: str) -> set[str]:
    """Lowercased alphanumeric tokens, minus numerics/short words/stopwords."""
    tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
    out: set[str] = set()
    for token in tokens:
        if token.isdigit() or len(token) < 2 or token in _REFERENCE_STOPWORDS:
            continue
        out.add(token)
    return out


def _name_overlaps_intent(name: str | None, intent: str | None) -> bool:
    """Word-level overlap: does a created entity's name relate to the intent?

    ``"Water consumption > 0"`` overlaps ``"bind the water consumption rule"``
    (shared tokens ``water`` + ``consumption``), while ``"Scope 2 invoice
    rule"`` does not (only the generic stopword ``rule`` is shared).
    """
    if not name or not intent:
        return False
    name_tokens = _significant_tokens(name)
    if not name_tokens:
        return False
    return bool(name_tokens & _significant_tokens(intent))


class WorkingMemoryLedger:
    """In-loop memory of entities created by prior steps."""

    def __init__(self) -> None:
        self.entities: list[LedgerEntity] = []
        self.repaired_refs: list[dict] = []

    def add(self, kind: str, entity_id: Any, name: str | None = None,
            step_index: int | None = None) -> None:
        if entity_id is None:
            return
        if self.has(kind, entity_id):
            return
        self.entities.append(LedgerEntity(
            kind=kind, id=entity_id, name=name, step_index=step_index,
        ))

    def has(self, kind: str, entity_id: Any) -> bool:
        return any(
            e.kind == kind and str(e.id) == str(entity_id)
            for e in self.entities
        )

    def by_kind(self, kind: str) -> list[LedgerEntity]:
        return [e for e in self.entities if e.kind == kind]

    def record_repair(self, step_index: int, kind: str, stale_id: Any,
                      corrected_id: Any) -> None:
        self.repaired_refs.append({
            "step": step_index,
            "kind": kind,
            "stale_id": stale_id,
            "corrected_id": corrected_id,
        })

    @staticmethod
    def parse_output(tool_output: dict, kind: str | None = None) -> list[tuple[Any, str | None]]:
        """Extract ``(id, name)`` pairs from a tool result dict.

        Handles the common *created-entity* shapes: ``{"id": N}``,
        ``{"data": {"id": N}}``, ``{"status_code": 201, "data": {...}}``,
        ``{"bindings": [{"id": ...}]}``, ``{"table": {...}}`` and
        ``{"artifact_id": ...}``. Read-only list shapes (``results``) are
        deliberately ignored — they describe entities that already exist, not
        entities a prior step created, so they must never pollute the ledger.
        """
        if not isinstance(tool_output, dict):
            return []
        found: list[tuple[Any, str | None]] = []

        def _add(eid: Any, name: str | None = None) -> None:
            if eid is None:
                return
            found.append((eid, name))

        data = tool_output.get("data")
        if isinstance(data, dict):
            _add(data.get("id"), data.get("name") or data.get("title"))

        if "id" in tool_output and not isinstance(tool_output.get("id"), dict):
            _add(tool_output["id"], tool_output.get("name") or tool_output.get("title"))

        bindings = tool_output.get("bindings")
        if isinstance(bindings, list):
            for b in bindings:
                if isinstance(b, dict):
                    _add(b.get("id"), b.get("name"))

        table = tool_output.get("table")
        if isinstance(table, dict):
            _add(table.get("id"), table.get("name") or table.get("title"))

        if "artifact_id" in tool_output:
            _add(tool_output["artifact_id"])

        # De-duplicate by (kind, id).
        seen: set[tuple[str, str]] = set()
        deduped: list[tuple[Any, str | None]] = []
        for eid, name in found:
            key = (kind or "", str(eid))
            if key not in seen:
                seen.add(key)
                deduped.append((eid, name))
        return deduped


# ── Contract gate ──────────────────────────────────────────────────────────────


def _extract_artifact_nouns(brief: str) -> list[str]:
    """Deterministic artifact-noun extraction (category words + quoted names)."""
    text = brief or ""
    lower = text.lower()
    nouns: list[str] = []
    for noun in _ARTIFACT_NOUNS:
        if re.search(rf"\b{re.escape(noun)}s?\b", lower):
            nouns.append(noun)
    for quoted in re.findall(r"[`'\"]([\w_\-]+)[`'\"]", text):
        if quoted.lower() not in {n.lower() for n in nouns}:
            nouns.append(quoted)
    return nouns


def _suggest_criterion(step: Any) -> dict | None:
    """Deterministic acceptance-criterion template for a step (spec §3.4)."""
    tool = step.tool_name
    args = step.tool_args or {}
    if tool == "create_dq_rule":
        return {"type": "created_entity", "kind": "rule", "expect_status": 201}
    if tool == "export_document":
        return {"type": "artifact", "expect_artifact": True}
    # Table-creation shape (create_table): the acceptance criterion is the
    # field list the brief demanded — more informative than a generic 201.
    # The fields ride inside the ``body`` of a call_host_api step.
    fields_args = args.get("fields") or (args.get("body") or {}).get("fields")
    if fields_args:
        field_names = [
            (f.get("name") if isinstance(f, dict) else str(f))
            for f in fields_args
        ]
        return {"type": "table_fields", "fields": field_names}
    if tool == "call_host_api":
        method = str(args.get("method", "")).upper()
        if not method:
            # Verb inference from the catalog api_name — create/bind/… are
            # mutations (POST), list/get/… are reads (GET).
            api_name = str(args.get("api_name") or "").lower()
            if any(v in api_name for v in (
                "create", "add", "bind", "update", "delete", "set", "save",
            )):
                method = "POST"
            elif any(v in api_name for v in (
                "list", "get", "search", "read", "fetch",
            )):
                method = "GET"
        if method == "GET":
            return {"type": "read_ok", "expect_status": 200}
        return {"type": "created_entity", "kind": "host", "expect_status": 201}
    return None  # reasoning step (no tool) → skip


def contract_gate(plan: Any, brief: str) -> dict:
    """Deterministic artifact-noun coverage + per-step criteria suggestions.

    Never blocks — records findings and suggestions for the flight state.
    """
    nouns = _extract_artifact_nouns(brief)
    covered: set[str] = set()
    for step in getattr(plan, "steps", []) or []:
        haystack = f"{step.intent} {json.dumps(step.tool_args or {})}".lower()
        for noun in nouns:
            if noun.lower() in haystack:
                covered.add(noun)

    findings: list[dict] = []
    for noun in nouns:
        if noun not in covered:
            findings.append({"kind": "missing_artifact", "noun": noun, "missing": True})

    suggested_criteria: dict[str, dict] = {}
    for step in getattr(plan, "steps", []) or []:
        crit = _suggest_criterion(step)
        if crit is not None:
            suggested_criteria[str(step.step_id)] = crit

    return {"findings": findings, "suggested_criteria": suggested_criteria}


# ── Acceptance report helpers (spec §3.5–§3.6) ───────────────────────────

# RunStep statuses relevant to acceptance (engine set, no engine import).
_STEP_COMPLETED = "completed"
_STEP_SKIPPED = "skipped"


def _overall_status(results: list[dict]) -> str:
    """Derive the run-level acceptance status (spec §3.5).

    All met → ``met``; any partial → ``partial``; any (unrepaired) missed →
    ``missed``; no requirements → ``met`` (nothing to accept).
    """
    verdicts = [r.get("verdict") for r in results]
    if not verdicts:
        return "met"
    if "partial" in verdicts:
        return "partial"
    if "missed" in verdicts:
        return "missed"
    return "met"


def serialize_acceptance_report(run: Any, row: Any) -> dict:
    """Product-facing acceptance payload (spec §4 — outcome terms only)."""
    report_json = row.report_json or {}
    metrics = row.metrics_json or {}
    supervision = (run.working_notes or {}).get("flight") or {}
    return {
        "status": row.status,
        "requirements": report_json.get("requirements", []),
        "metrics": metrics,
        "final_response": row.narrative or run.final_response,
        "supervision": supervision,
    }


# ── FlightDirector ─────────────────────────────────────────────────────────────


class FlightDirector:
    """In-loop supervisor wired as an additive hook on ``ReActLoop``."""

    def __init__(self, executor=None, run=None) -> None:
        self.executor = executor      # CarbonHostExecutor (async _call_api)
        self.run = run                # Django Run ORM object (may be None in unit tests)
        self.ledger = WorkingMemoryLedger()
        self.fidelity_failures = 0
        self.escalations = 0
        self.escalated_steps: list[int] = []
        self.contract: dict = {}

    def escalation_model(self) -> str:
        """Model used for escalated re-runs (settings-backed, no engine import)."""
        return getattr(settings, "AI_FLIGHT_DIRECTOR_ESCALATION_MODEL", "gpt-4o")

    # ── Reference validation (in-loop) ────────────────────────────────────

    async def _entity_exists(self, kind: str, entity_id: Any) -> bool:
        """Authoritative read-only existence check via the host executor."""
        if kind not in _LISTABLE_KINDS or self.executor is None:
            return False
        try:
            if kind == "rule":
                resp = await self.executor._call_api("GET", "/carbon-api/dq/rules/", {})
            elif kind == "table":
                resp = await self.executor._call_api("GET", "/carbon-api/dataschema/tables/", {})
            else:  # pragma: no cover - guarded by _LISTABLE_KINDS
                return False
            return any(
                str(r.get("id")) == str(entity_id)
                for r in _extract_results(resp)
            )
        except Exception:  # noqa: BLE001 - existence check must never fail the run
            logger.exception("FlightDirector: existence check failed for %s:%s", kind, entity_id)
            return False

    def _resolve_stale_reference(self, kind: str, stale_id: Any,
                                 step: Any, ledger: WorkingMemoryLedger) -> Any:
        """Resolve a stale id to an earlier-created entity when unambiguous.

        Rewrites only when exactly ONE earlier entity of ``kind`` exists AND
        its name overlaps the step intent (no false positive on pre-existing
        or ambiguous ids).
        """
        candidates = [
            e for e in ledger.by_kind(kind) if str(e.id) != str(stale_id)
        ]
        if len(candidates) != 1:
            return None
        entity = candidates[0]
        if _name_overlaps_intent(entity.name, step.intent):
            return entity.id
        return None

    async def _validate_ref(self, kind: str, ref_id: str, step: Any,
                            ledger: WorkingMemoryLedger,
                            original_value: Any = None) -> tuple[Any, dict | None]:
        """Return ``(possibly_corrected_id, repair_info_or_None)``."""
        if ledger.has(kind, ref_id):
            return ref_id, None
        if kind not in _LISTABLE_KINDS or self.executor is None:
            # Non-listable kinds (field/module/binding) — ledger-only
            # validation. No host round-trip → no false positives (spec §3.2).
            return ref_id, None
        exists = await self._entity_exists(kind, ref_id)
        if exists:
            return ref_id, None  # pre-existing on the host → valid
        replacement = self._resolve_stale_reference(kind, ref_id, step, ledger)
        if replacement is not None:
            ledger.record_repair(
                step.step_id, kind,
                original_value if original_value is not None else ref_id,
                replacement,
            )
            return replacement, {
                "kind": "stale_reference",
                "step": step.step_id,
                "ref": f"{kind}:{ref_id}",
                "corrected_to": replacement,
            }
        return ref_id, {
            "kind": "stale_reference_unresolved",
            "step": step.step_id,
            "ref": f"{kind}:{ref_id}",
            "instruction": (
                f"the referenced {kind} id {ref_id} is invalid — list current "
                f"{kind}s and use the real id of the entity created in a prior step"
            ),
        }

    async def prepare_step(self, step: Any, ledger: WorkingMemoryLedger,
                           attempts: int = 0) -> StepPrep:
        """Validate reference args + build step prep (corrected args, guidance).

        Reference keys (``rule``/``data_table``/``dq_rule_ids``/…) are walked
        recursively so ids nested inside a ``call_host_api`` ``body`` are
        corrected just like top-level args — the real stale-id binding was
        staged with ``{"body": {"rule": 125, "data_table": T}}``.
        """
        corrected = json.loads(json.dumps(step.tool_args or {}))
        instructions: list[str] = []
        repairs: list[dict] = []
        ref_keys = set(_REFERENCE_ARG_KEYS)

        async def _walk(node: Any) -> None:
            if isinstance(node, dict):
                for key, value in list(node.items()):
                    if key in ref_keys:
                        kind = _REFERENCE_KEY_KIND.get(key)
                        if kind is None:
                            continue
                        if isinstance(value, list):
                            new_vals: list[Any] = []
                            for v in value:
                                if isinstance(v, (int, str)) and not isinstance(v, bool):
                                    new_v, rep = await self._validate_ref(
                                        kind, str(v), step, ledger,
                                        original_value=v,
                                    )
                                    if rep:
                                        repairs.append(rep)
                                        if rep.get("instruction"):
                                            instructions.append(rep["instruction"])
                                    # Only apply an actual rewrite; otherwise
                                    # keep the ORIGINAL value/type so valid
                                    # int ids are not stringified (false change).
                                    if rep and rep.get("corrected_to") is not None:
                                        new_vals.append(rep["corrected_to"])
                                    else:
                                        new_vals.append(v)
                                else:
                                    new_vals.append(v)
                            node[key] = new_vals
                        elif isinstance(value, (int, str)) and not isinstance(value, bool):
                            new_v, rep = await self._validate_ref(
                                kind, str(value), step, ledger,
                                original_value=value,
                            )
                            if rep:
                                repairs.append(rep)
                                if rep.get("instruction"):
                                    instructions.append(rep["instruction"])
                            if rep and rep.get("corrected_to") is not None:
                                node[key] = rep["corrected_to"]
                            # else: leave the original value untouched
                    elif isinstance(value, (dict, list)):
                        await _walk(value)
            elif isinstance(node, list):
                for item in node:
                    if isinstance(item, (dict, list)):
                        await _walk(item)

        await _walk(corrected)
        changed = corrected != (step.tool_args or {})

        return StepPrep(
            corrected_tool_args=corrected if changed else None,
            extra_instructions=" ".join(filter(None, instructions)) or None,
            model_override=self.escalation_model() if attempts >= 1 else None,
            repair_kind=repairs[0]["kind"] if repairs else None,
            repair_detail=json.dumps(repairs) if repairs else None,
        )

    # ── Ledger + fidelity (in-loop) ───────────────────────────────────────

    def _infer_kind(self, tool_name: str | None, result: dict | None,
                    step: Any) -> str:
        tool = (tool_name or step.tool_name or "").lower()
        if "dq_rule" in tool or tool == "create_dq_rule":
            return "rule"
        if "table" in tool:
            return "table"
        if "export" in tool or "artifact" in tool:
            return "artifact"
        # ``call_host_api`` steps carry the catalog ``api_name`` in their args —
        # map it so a created rule/table is keyed by the same kind the
        # reference validator expects (the raw result dict has no endpoint).
        api_name = str((step.tool_args or {}).get("api_name") or "").lower()
        if "rule-assign" in api_name or "bind" in api_name:
            return "binding"
        if "rule" in api_name:
            return "rule"
        if "table" in api_name:
            return "table"
        if "export" in api_name or "artifact" in api_name:
            return "artifact"
        endpoint = ""
        if isinstance(result, dict):
            endpoint = str(result.get("endpoint") or result.get("path") or "")
        if not endpoint:
            endpoint = str((step.tool_args or {}).get("endpoint") or "")
        return _kind_from_endpoint(endpoint)

    def _escalate(self, step: Any, verdict: StepFlightVerdict, detail: str) -> None:
        verdict.escalated = True
        verdict.requests_rerun = False
        verdict.repair_kind = "escalated"
        verdict.repair_detail = detail
        self.escalations += 1
        if step.step_id not in self.escalated_steps:
            self.escalated_steps.append(step.step_id)

    def on_step_completed(self, step: Any, draft: Any, execution: Any,
                          result: Any, ledger: WorkingMemoryLedger,
                          attempts: int = 0) -> StepFlightVerdict:
        """Update the ledger from executed tools + run the fidelity guard."""
        # 1. Ledger update from every completed tool.
        for tool in (execution.completed_tools or []):
            if tool.get("error"):
                continue
            parsed = _parse_json(tool.get("result"))
            if not isinstance(parsed, dict):
                continue
            kind = self._infer_kind(tool.get("tool_name"), parsed, step)
            for eid, name in ledger.parse_output(parsed, kind=kind):
                ledger.add(kind, eid, name=name, step_index=step.step_id)

        declared = len(draft.tool_calls or [])
        executed = len(execution.completed_tools or [])
        verdict = StepFlightVerdict(declared=declared, executed=executed)

        if step.tool_name is None:
            return verdict  # reasoning step — no fidelity contract

        # 2. Worker-fidelity guard (spec §3.3).
        if declared == 0 and executed == 0:
            verdict.fidelity_failure = True
            self.fidelity_failures += 1
            if not step.is_mutation and attempts == 0:
                verdict.requests_rerun = True
                verdict.repair_kind = "no_op"
                verdict.extra_instructions = (
                    f"call {step.tool_name} — do not answer in prose"
                )
            else:
                self._escalate(
                    step, verdict,
                    f"declared 0 calls for tool {step.tool_name}",
                )
            return verdict

        if declared > executed:
            verdict.fidelity_failure = True
            self.fidelity_failures += 1
            if step.is_mutation:
                # RULE_21 — never auto re-run a mutation on fidelity failure.
                self._escalate(
                    step, verdict,
                    f"mutation fidelity: {declared} declared vs {executed} executed",
                )
            elif attempts == 0:
                verdict.requests_rerun = True
                verdict.repair_kind = "fidelity"
                names = [
                    tc.get("function", {}).get("name", "?")
                    for tc in (draft.tool_calls or [])
                ]
                verdict.extra_instructions = (
                    f"{declared - executed} declared action(s) did not run: "
                    f"{', '.join(names)}. Execute them all in this turn."
                )
            else:
                self._escalate(
                    step, verdict,
                    f"fidelity persisted after re-run: {declared} vs {executed}",
                )
            return verdict

        return verdict

    # ── State serialization ───────────────────────────────────────────────

    def state(self) -> dict:
        """Supervision state persisted to ``working_notes.flight``."""
        return {
            "ledger": [
                {"kind": e.kind, "id": e.id, "name": e.name,
                 "step_index": e.step_index}
                for e in self.ledger.entities
            ],
            "repairs": list(self.ledger.repaired_refs),
            "escalations": self.escalations,
            "fidelity": {
                "failures": self.fidelity_failures,
                "escalated_steps": list(self.escalated_steps),
            },
            "contract": self.contract,
        }

    # ── Acceptance criteria resolution (spec §3.4) ───────────────────────

    def _criterion_for_step(self, step: Any) -> dict | None:
        """Resolve the acceptance criterion for a step.

        Explicit ``acceptance_criteria`` supplied by the planner/user (either
        in the step's ``tool_args`` or merged into the persisted
        ``plan_json.steps[i]``) override the deterministic templates from
        §3.4; a reasoning step (no tool) has no criterion and is skipped.
        """
        explicit = (step.tool_args or {}).get("acceptance_criteria")
        if explicit is not None:
            return explicit
        if self.run is not None:
            try:
                for s in (self.run.plan_json or {}).get("steps", []):
                    if not isinstance(s, dict):
                        continue
                    if str(s.get("step_id")) == str(step.step_id):
                        ac = s.get("acceptance_criteria")
                        return ac if ac is not None else _suggest_criterion(step)
            except Exception:  # noqa: BLE001 - criteria resolution never fails the run
                pass
        return _suggest_criterion(step)

    def _kind_from_step(self, step: Any) -> str:
        """Best-effort ledger-kind for a step when the criterion says ``host``."""
        tool = (step.tool_name or "").lower()
        if "dq_rule" in tool or tool == "create_dq_rule":
            return "rule"
        if "table" in tool:
            return "table"
        api_name = str((step.tool_args or {}).get("api_name") or "").lower()
        if "rule-assign" in api_name or "bind" in api_name or "assign" in api_name:
            return "binding"
        if "rule" in api_name:
            return "rule"
        if "table" in api_name:
            return "table"
        if "export" in api_name or "artifact" in api_name:
            return "artifact"
        if "list" in api_name or "get" in api_name or "search" in api_name:
            return "read"
        return "host"

    @staticmethod
    @staticmethod
    async def _status_for_step(step: Any, step_statuses: dict | None,
                               run: Any) -> str | None:
        """Step status from the caller-supplied map, else a read-only ORM read."""
        if step_statuses is not None:
            return step_statuses.get(step.step_id)
        try:
            from asgiref.sync import sync_to_async
            from ai.models.core import RunStep
            get_status = sync_to_async(
                lambda: RunStep.objects.get(
                    run_id=run.id, step_index=step.step_id
                ).status
            )
            return await get_status()
        except Exception:  # noqa: BLE001 - best-effort status lookup
            return None

    # ── Acceptance checks (spec §3.5) ─────────────────────────────────────

    async def run_acceptance_checks(
        self,
        plan: Any,
        run: Any,
        ledger: WorkingMemoryLedger,
        executor: Any,
        step_statuses: dict | None = None,
        step_runner=None,
    ) -> list[dict]:
        """Post-run acceptance verification for a plan (spec §3.4–§3.5).

        Re-queries read-only host state through the executor for every step
        that has an acceptance criterion and returns one requirement result
        per checked step::

            {step_id, intent, criterion, verdict: met|partial|missed,
             evidence, repairs, escalated}

        A ``missed`` criterion on a NON-mutation step is repaired through the
        injectable ``step_runner`` (async ``(step, criterion, instructions)
        -> dict``) up to ``AI_FLIGHT_DIRECTOR_MAX_REPAIRS`` attempts; a step
        that still fails is escalated (``escalations`` +1, flagged). Mutation
        steps are NEVER auto re-run (RULE_21) — their misses surface as
        ``missed`` for human review. Steps the user declined (``skipped``) are
        excluded from acceptance.
        """
        max_repairs = getattr(settings, "AI_FLIGHT_DIRECTOR_MAX_REPAIRS", 2)
        results: list[dict] = []
        for step in getattr(plan, "steps", []) or []:
            if step_statuses is not None:
                status = step_statuses.get(step.step_id)
                if status == _STEP_SKIPPED:
                    continue  # user-declined consent step — not an acceptance miss
            criterion = self._criterion_for_step(step)
            if criterion is None:
                continue  # reasoning step — no acceptance contract
            check = await self._check_criterion(
                step, criterion, run, ledger, executor, step_statuses
            )
            verdict = check["verdict"]
            repairs: list[dict] = []
            escalated = False
            if verdict == "missed":
                if step.is_mutation or step_runner is None:
                    # RULE_21 (mutation) / no safe re-execution seam — the miss
                    # surfaces as ``missed``; it is never auto-re-run.
                    pass
                else:
                    for attempt in range(max_repairs):
                        instructions = self._repair_instructions(
                            step, criterion, check
                        )
                        outcome = await step_runner(step, criterion, instructions)
                        repairs.append({
                            "attempt": attempt + 1,
                            "instructions": instructions,
                            "outcome": outcome,
                        })
                        recheck = await self._check_criterion(
                            step, criterion, run, ledger, executor,
                            step_statuses,
                        )
                        check = recheck
                        verdict = recheck["verdict"]
                        if verdict == "met":
                            break
                    if verdict != "met":
                        # Repair exhausted → escalate for human review.
                        self._escalate(
                            step, StepFlightVerdict(),
                            f"acceptance missed after {len(repairs)} repair attempt(s)",
                        )
                        escalated = True
                        verdict = "partial"
            results.append({
                "step_id": step.step_id,
                "intent": step.intent,
                "criterion": criterion,
                "verdict": verdict,
                "evidence": check.get("evidence", {}),
                "repairs": repairs,
                "escalated": escalated,
            })
        return results

    async def _check_criterion(self, step: Any, criterion: dict, run: Any,
                               ledger: WorkingMemoryLedger, executor: Any,
                               step_statuses: dict | None) -> dict:
        ctype = criterion.get("type")
        if ctype == "created_entity":
            return await self._check_created_entity(
                step, criterion, ledger, executor, step_statuses
            )
        if ctype == "table_fields":
            return await self._check_table_fields(
                step, criterion, ledger, executor
            )
        if ctype == "artifact":
            return await self._check_artifact(step, criterion, run)
        if ctype == "read_ok":
            return await self._check_read_ok(step, criterion, step_statuses, run)
        # Unknown criterion type — never blocks closure.
        return {"verdict": "met", "evidence": {"query": "no-op", "matches": True}}

    async def _check_created_entity(self, step: Any, criterion: dict,
                                    ledger: WorkingMemoryLedger,
                                    executor: Any,
                                    step_statuses: dict | None) -> dict:
        """Re-query host state and assert the created entity exists.

        Evidence = the read-only query + the matched host rows. When the
        criterion kind is ``host`` the step's api_name resolves the real kind
        (rule/table/binding/…) so the check re-queries the right endpoint.
        """
        kind = criterion.get("kind") or "host"
        effective = self._kind_from_step(step) if kind == "host" else kind
        step_entities = [
            e for e in ledger.entities
            if str(e.step_index) == str(step.step_id)
            and (effective == "host" or e.kind == effective)
        ]

        if effective in _LISTABLE_KINDS:
            query = (
                "GET /carbon-api/dq/rules/"
                if effective == "rule"
                else "GET /carbon-api/dataschema/tables/"
            )
            rows: list[dict] = []
            if executor is not None:
                try:
                    if effective == "rule":
                        resp = await executor._call_api(
                            "GET", "/carbon-api/dq/rules/", {}
                        )
                    else:
                        resp = await executor._call_api(
                            "GET", "/carbon-api/dataschema/tables/", {}
                        )
                    rows = _extract_results(resp)
                except Exception:  # noqa: BLE001 - acceptance never fails the run
                    logger.exception(
                        "acceptance re-query failed kind=%s step=%s",
                        effective, step.step_id,
                    )
                    rows = []
            if step_entities:
                ids = {str(e.id) for e in step_entities}
                matched = [
                    r for r in rows if str(r.get("id")) in ids
                ]
                if matched:
                    return {"verdict": "met",
                            "evidence": {"query": query, "matches": matched}}
                return {"verdict": "missed",
                        "evidence": {"query": query, "matches": []}}
            # No ledger id — best-effort name-overlap against fresh host rows.
            if rows:
                candidates = [
                    r for r in rows
                    if _name_overlaps_intent(
                        str(r.get("name") or r.get("title") or ""), step.intent
                    )
                ]
                if candidates:
                    return {"verdict": "met",
                            "evidence": {"query": query, "matches": candidates}}
            return {"verdict": "missed",
                    "evidence": {"query": query, "matches": []}}

        # Non-listable kinds (binding/artifact/host) — no generic list GET.
        # Best available evidence: the in-run ledger + the step's outcome.
        status = await self._status_for_step(step, step_statuses, run)
        if step_entities or status == _STEP_COMPLETED:
            return {"verdict": "met", "evidence": {
                "query": "ledger+step_status",
                "matches": (
                    [{"kind": e.kind, "id": e.id} for e in step_entities]
                    or [{"step_id": step.step_id, "status": status}]
                ),
            }}
        return {"verdict": "missed", "evidence": {
            "query": "ledger+step_status", "matches": [],
        }}

    async def _check_table_fields(self, step: Any, criterion: dict,
                                  ledger: WorkingMemoryLedger,
                                  executor: Any) -> dict:
        """Assert the EXACT field set the brief demanded (water lesson).

        Mismatch (missing OR extra fields) → ``partial`` with the actual
        diff; a table that does not exist → ``missed``.
        """
        planned = [str(f) for f in (criterion.get("fields") or [])]
        table_entities = [
            e for e in ledger.entities
            if e.kind == "table" and str(e.step_index) == str(step.step_id)
        ]
        table_id = table_entities[0].id if table_entities else None
        if table_id is None:
            args = step.tool_args or {}
            table_id = (
                (args.get("body") or {}).get("data_table")
                or args.get("data_table")
                or (args.get("body") or {}).get("table_id")
            )
        query = (
            f"GET /carbon-api/dataschema/tables/detail/?id={table_id}"
            if table_id is not None
            else "GET /carbon-api/dataschema/tables/detail/ (no table id)"
        )
        actual_names: list[str] = []
        if table_id is not None and executor is not None:
            try:
                resp = await executor._call_api(
                    "GET", "/carbon-api/dataschema/tables/detail/",
                    {"id": table_id},
                )
                data = (resp or {}).get("data") or {}
                actual_names = [
                    str(f.get("name")) for f in (data.get("fields") or [])
                    if isinstance(f, dict) and f.get("name")
                ]
            except Exception:  # noqa: BLE001 - acceptance never fails the run
                logger.exception(
                    "acceptance table detail query failed id=%s", table_id
                )
        if table_id is None or not actual_names:
            return {"verdict": "missed", "evidence": {
                "query": query,
                "matches": {"planned": planned, "actual": actual_names},
                "diff": {
                    "missing": sorted(set(planned)),
                    "extra": [],
                    "table_id": table_id,
                },
            }}
        planned_set = set(planned)
        actual_set = set(actual_names)
        missing = sorted(planned_set - actual_set)
        extra = sorted(actual_set - planned_set)
        if not missing and not extra:
            return {"verdict": "met", "evidence": {
                "query": query,
                "matches": {"planned": planned, "actual": actual_names},
                "diff": {"missing": [], "extra": [], "table_id": table_id},
            }}
        return {"verdict": "partial", "evidence": {
            "query": query,
            "matches": {"planned": planned, "actual": actual_names},
            "diff": {
                "missing": missing, "extra": extra, "table_id": table_id,
            },
        }}

    @staticmethod
    async def _check_artifact(step: Any, criterion: dict, run: Any) -> dict:
        """Assert at least one durable ``RunArtifact`` row for the step."""
        from asgiref.sync import sync_to_async
        from ai.models.core import RunArtifact

        artifacts = await sync_to_async(
            lambda: list(
                RunArtifact.objects.filter(
                    run_id=run.id, step_index=step.step_id
                )
            )
        )()
        if artifacts:
            return {"verdict": "met", "evidence": {
                "query": "RunArtifact(run_id, step_index)",
                "matches": [{"id": a.id, "name": a.name} for a in artifacts],
            }}
        return {"verdict": "missed", "evidence": {
            "query": "RunArtifact(run_id, step_index)", "matches": [],
        }}

    @staticmethod
    async def _check_read_ok(step: Any, criterion: dict,
                             step_statuses: dict | None, run: Any) -> dict:
        status = await FlightDirector._status_for_step(
            step, step_statuses, run
        )
        if status == _STEP_COMPLETED:
            return {"verdict": "met", "evidence": {
                "query": "step.status",
                "matches": {"status": status},
            }}
        return {"verdict": "missed", "evidence": {
            "query": "step.status",
            "matches": {"status": status},
        }}

    def _repair_instructions(self, step: Any, criterion: dict, check: dict) -> str:
        """Deterministic repair guidance built from the ACTUAL check diff."""
        evidence = check.get("evidence") or {}
        diff = evidence.get("diff") or {}
        missing = diff.get("missing") or []
        extra = diff.get("extra") or []
        parts = [f"requirement not met for step '{step.intent}'"]
        if missing:
            parts.append(f"missing: {', '.join(str(m) for m in missing)}")
        if extra:
            parts.append(f"unexpected: {', '.join(str(m) for m in extra)}")
        if evidence.get("matches") == [] and not diff:
            kind = criterion.get("kind") or "entity"
            if kind == "host":
                # Resolve the generic ``host`` kind to the real kind so the
                # guidance names what is actually missing (rule/table/binding).
                kind = self._kind_from_step(step)
            parts.append(f"no matching {kind} found on the host")
        return " — ".join(parts)

    @staticmethod
    def _ledger_from_state(flight_state: dict) -> WorkingMemoryLedger:
        """Rebuild a working-memory ledger from persisted flight state."""
        ledger = WorkingMemoryLedger()
        for e in (flight_state or {}).get("ledger") or []:
            if not isinstance(e, dict):
                continue
            ledger.add(
                e.get("kind"), e.get("id"),
                name=e.get("name"), step_index=e.get("step_index"),
            )
        for r in (flight_state or {}).get("repairs") or []:
            if isinstance(r, dict):
                ledger.repaired_refs.append(dict(r))
        return ledger

    # ── Acceptance report closure (spec §3.6) ────────────────────────────

    def build_acceptance_report(self, run: Any, results: list[dict],
                                metrics: dict) -> dict:
        """Write the durable ``AcceptanceReport`` row (idempotent per run).

        ``report_json`` carries the per-requirement results; ``metrics_json``
        the aggregate metrics; ``narrative`` the run's ``final_response``;
        ``status`` is derived from the per-requirement verdicts. Reuses the
        existing row when one is present so re-closure never duplicates.
        """
        from ai.models.core import AcceptanceReport

        status = _overall_status(results)
        narrative = run.final_response or ""
        report_json = {"requirements": results}

        # Append an outcome summary to the flight supervision state.
        try:
            notes = dict(run.working_notes or {})
            flight = dict(notes.get("flight") or {})
            flight["acceptance"] = {
                "status": status,
                "requirements_total": len(results),
                "requirements_met": sum(
                    1 for r in results if r.get("verdict") == "met"
                ),
                "requirements_partial": sum(
                    1 for r in results if r.get("verdict") == "partial"
                ),
                "requirements_missed": sum(
                    1 for r in results if r.get("verdict") == "missed"
                ),
            }
            notes["flight"] = flight
            run.working_notes = notes
            run.save(update_fields=["working_notes", "updated_at"])
        except Exception:  # noqa: BLE001 - closure persistence never fails the run
            logger.exception(
                "flight acceptance summary persistence failed run=%s", run.id
            )

        row = (
            AcceptanceReport.objects.filter(run_id=run.id)
            .order_by("-created_at")
            .first()
        )
        if row is None:
            row = AcceptanceReport.objects.create(
                run_id=run.id,
                status=status,
                report_json=report_json,
                metrics_json=metrics,
                narrative=narrative,
            )
        else:
            row.status = status
            row.report_json = report_json
            row.metrics_json = metrics
            row.narrative = narrative
            row.save(update_fields=[
                "status", "report_json", "metrics_json", "narrative",
            ])
        logger.info(
            "acceptance report written run=%s status=%s requirements=%d",
            run.id, status, len(results),
        )
        return serialize_acceptance_report(run, row)


# ── Grow loop: outcome → learning + playbook (spec §3.6) ────────────────

# Terminal run states — mirrors ``ai.feedback.skill_flywheel``: learning only
# fires after the run is final, so the retry loop never double-enqueues.
_TERMINAL_STATUSES = ("completed", "failed")

# Deterministic guidance text per learning pattern — the content written to
# ``PlaybookBlock``. Kept stable so re-detection of the same pattern on a
# later run bumps the block version with identical guidance (the lesson is
# re-proven, not silently changed).
_PATTERN_GUIDANCE = {
    "planner: always emit acceptance_criteria": (
        "Every plan step that performs a tool action must declare an explicit "
        "acceptance_criteria (created_entity / table_fields / artifact / "
        "read_ok) so the run's outcome can be verified after execution "
        "instead of assumed."
    ),
    "worker: never stop before all declared calls run": (
        "A worker step that declares tool calls must execute every declared "
        "call in the same turn — stopping early is a fidelity failure that "
        "escalates the step for human review."
    ),
    "planner: resolve created ids from prior step outputs": (
        "When a step references an entity created by an earlier step, resolve "
        "the id from the earlier step's output ledger — never a stale or "
        "hard-coded id."
    ),
}


def _detect_patterns(report: dict, flight_state: dict | None = None) -> list[tuple[str, str]]:
    """Deterministic ``(pattern, target)`` detections (spec §3.6).

    Three ordered matchers — no LLM, no randomness, unit-testable:
      1. any requirement recorded WITHOUT ``acceptance_criteria`` →
         ``("planner: always emit acceptance_criteria", "playbook")``
      2. ``metrics.fidelity_failures > 0`` (fallback: the persisted flight
         state's ``fidelity.failures``) →
         ``("worker: never stop before all declared calls run", "playbook")``
      3. non-empty ``repaired_refs`` from the flight ledger (fallback: the
         report's ``supervision.repairs``) →
         ``("planner: resolve created ids from prior step outputs",
         "playbook")``
    """
    report = report or {}
    flight = dict(flight_state or {})
    patterns: list[tuple[str, str]] = []

    requirements = report.get("requirements") or []
    if any(
        not isinstance(r, dict) or r.get("criterion") is None
        for r in requirements
    ):
        patterns.append(("planner: always emit acceptance_criteria", "playbook"))

    metrics = report.get("metrics") or {}
    fidelity_failures = int(metrics.get("fidelity_failures") or 0)
    if fidelity_failures <= 0:
        fidelity_failures = int(
            ((flight.get("fidelity") or {}).get("failures") or 0)
        )
    if fidelity_failures > 0:
        patterns.append(("worker: never stop before all declared calls run", "playbook"))

    repaired_refs = flight.get("repairs")
    if not repaired_refs:
        repaired_refs = ((report.get("supervision") or {}).get("repairs") or [])
    if repaired_refs:
        patterns.append(("planner: resolve created ids from prior step outputs", "playbook"))

    return patterns


def _apply_playbook_block(pattern: str, guidance: str, run_id: str):
    """Upsert a ``flight_director`` playbook block (version N+1 if exists).

    New block → version 1. An existing block with the same title → version+1
    with ``content`` + ``provenance`` updated. ``provenance`` records the run
    that produced the lesson.
    """
    from ai.models.core import PlaybookBlock

    existing = (
        PlaybookBlock.objects.filter(
            instance_id=_PLAYBOOK_INSTANCE_ID,
            block_type="flight_director", title=pattern,
        )
        .order_by("-version")
        .first()
    )
    if existing is None:
        return PlaybookBlock.objects.create(
            instance_id=_PLAYBOOK_INSTANCE_ID,
            block_type="flight_director",
            title=pattern,
            content=guidance,
            version=1,
            provenance=run_id,
        )
    existing.version = (existing.version or 1) + 1
    existing.content = guidance
    existing.provenance = run_id
    existing.is_active = True
    existing.save(update_fields=[
        "version", "content", "provenance", "is_active", "updated_at",
    ])
    return existing


def enqueue_learning_from_report(report: dict, flight_state: dict | None = None,
                                 run: Any = None) -> list[dict]:
    """Deterministic outcome→learning for a finalized run (spec §3.6).

    Matches the report (from ``FlightDirector.build_acceptance_report``) and
    the persisted flight state against the three deterministic patterns and
    applies each one: upsert a ``PlaybookBlock(block_type="flight_director",
    title=pattern, version=N+1 if exists, provenance=run.id)`` and mark the
    ``LearningOutcome`` ``applied`` with ``applied_at``.

    Idempotent: the ``(run, pattern)`` unique constraint means a second call
    for the same (run, pattern) is a no-op. Terminal-status guard mirrors
    ``feed_run_feedback`` — non-terminal runs (``paused``/``stopped``/…) and
    runs with none of the three signals create nothing. Learning errors never
    propagate (one pattern's failure does not block the rest) — the caller
    also wraps this in try/except so a plan run is never failed by learning.

    Returns a list of applied-outcome dicts ``{"pattern", "target",
    "outcome_id", "applied": True}`` (empty when nothing was learned).
    """
    from ai.models.core import LearningOutcome

    if run is None:
        logger.info("flight learning: no run provided — no-op")
        return []
    if run.status not in _TERMINAL_STATUSES:
        logger.info(
            "flight learning: run %s not terminal (%s) — no-op",
            run.id, run.status,
        )
        return []

    try:
        detections = _detect_patterns(report, flight_state)
    except Exception:  # noqa: BLE001 - learning never fails the run
        logger.exception("flight learning: pattern detection failed run=%s", run.id)
        return []

    outcomes: list[dict] = []
    for pattern, target in detections:
        try:
            guidance = _PATTERN_GUIDANCE.get(pattern, pattern)
            payload = {
                "pattern": pattern,
                "target": target,
                "guidance": guidance,
                "provenance": run.id,
                "source": "acceptance_report",
            }
            outcome, created = LearningOutcome.objects.get_or_create(
                run=run, pattern=pattern,
                defaults={
                    "target": target,
                    "payload_json": payload,
                    "status": "queued",
                },
            )
            if not created:
                logger.info(
                    "flight learning: %r already recorded for run %s — no-op",
                    pattern, run.id,
                )
                continue
            _apply_playbook_block(pattern, guidance, str(run.id))
            outcome.status = "applied"
            outcome.applied_at = timezone.now()
            outcome.save(update_fields=["status", "applied_at"])
            outcomes.append({
                "pattern": pattern,
                "target": target,
                "outcome_id": outcome.id,
                "applied": True,
            })
        except Exception:  # noqa: BLE001 - one pattern's failure never blocks the rest
            logger.exception(
                "flight learning: apply failed for %r run=%s", pattern, run.id
            )
    logger.info(
        "flight learning: run=%s applied=%s",
        run.id, [o["pattern"] for o in outcomes],
    )
    return outcomes
