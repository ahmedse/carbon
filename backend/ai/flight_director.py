"""
Flight Director — in-loop supervisor (Phase 25-B).

Additive supervision layered over the ReAct loop:

  * ``WorkingMemoryLedger`` — parses created entities out of tool outputs and
    validates reference args against read-only host GETs, rewriting stale ids
    that unambiguously map to an earlier-created entity.
  * ``contract_gate`` — deterministic artifact-noun coverage check plus
    per-step acceptance-criteria suggestions (never blocks; records only).
  * ``prepare_step`` — per-step prep: corrected tool args, extra
    instructions, escalation model override.
  * ``on_step_completed`` — ledger update + worker-fidelity guard.

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

logger = logging.getLogger("carbon.ai.flight_director")

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
