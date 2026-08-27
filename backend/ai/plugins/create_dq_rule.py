"""``create_dq_rule`` — reference "specific-process" plugin (Sprint 12-C).

Turns the generic ``call_host_api`` bridge into a **named, reusable process**:

    User: "validate the email field, here are some examples"
    Agent (create_dq_rule tool):
      1. build a v1 rule definition from the argued fields
      2. structurally validate it (pure Python — no ``dq`` import)
      3. dry-run evaluate deterministic rules against sample rows
         → ``{passed, explanation, failed_rows}`` (NOTHING written)
      4. stage the write via ``ctx.host_api.create_pending_execution()``
         (POST /carbon-api/dq/rules/, JWT → host RBAC applies) and return
         ``requires_confirmation=True`` — the host executes it only on confirm.

Guardrails honored (non-negotiable):

  * **RULE_18** — reached only through ``CarbonIntelligence``; never calls a
    provider or Django view directly.
  * **RULE_20** — zero upward imports: this module imports nothing from
    ``dq``/``catalog``/``mdm``/``emissions``/``accounts``/``core``.  The host
    write goes through ``ctx.host_api`` (the user's JWT → the host's own RBAC
    and field-assignment validation apply).
  * **RULE_21** — ``requires_confirmation=True``; the write is *staged*, never
    executed here.  Execution is the host's ``confirm_execution`` path.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from ai.engine.agent.plugins import ToolPlugin

logger = logging.getLogger("carbon.ai.plugins.create_dq_rule")

# Local mirrors of the dq rule-schema vocabulary (kept in-sync by the dq tests,
# not imported — RULE_20 forbids an upward import into dq).
_RULE_TYPES = {
    "not_null", "unique", "allowed_values", "range", "regex",
    "reference_integrity", "threshold", "nl_check",
}
_LEVELS = {"field", "business"}
_DIMENSIONS = {
    "completeness", "validity", "accuracy", "consistency",
    "timeliness", "uniqueness", "integrity", "reasonability",
}
_SEVERITIES = {"info", "warn", "error"}
_THRESHOLD_OPERATORS = {"gte", "gt", "lte", "lt", "eq", "neq"}
# Deterministic rules can be dry-run evaluated against sample rows in pure
# Python; NL/anomaly/integrity rules are structural-only.
_DETERMINISTIC_TYPES = {"not_null", "unique", "allowed_values", "range", "regex"}

_LEVEL_MAP = {"field": "field_validation", "business": "business_rule"}


# ── Pure-Python helpers (mirror dq.rule_schema; no upward import) ─────────


def _validate_definition(d: dict) -> list[dict]:
    """Return a list of ``{field, code, message}`` errors; empty = valid."""
    errors: list[dict] = []

    if not isinstance(d, dict):
        return [{"field": "_root", "code": "invalid_type",
                 "message": "definition must be a JSON object"}]

    if d.get("schema_version") != 1:
        errors.append({"field": "schema_version", "code": "invalid_value",
                       "message": "schema_version must be 1"})

    name = d.get("name")
    if not name or not isinstance(name, str) or not name.strip():
        errors.append({"field": "name", "code": "required",
                       "message": "name is required and must be a non-empty string"})

    if d.get("level") not in _LEVELS:
        errors.append({"field": "level", "code": "invalid_value",
                       "message": f"level must be one of {sorted(_LEVELS)}"})

    if d.get("dimension") not in _DIMENSIONS:
        errors.append({"field": "dimension", "code": "invalid_value",
                       "message": f"dimension must be one of {sorted(_DIMENSIONS)}"})

    rule_type = d.get("type")
    if rule_type not in _RULE_TYPES:
        errors.append({"field": "type", "code": "invalid_value",
                       "message": f"type must be one of {sorted(_RULE_TYPES)}"})

    if d.get("severity") not in _SEVERITIES:
        errors.append({"field": "severity", "code": "invalid_value",
                       "message": f"severity must be one of {sorted(_SEVERITIES)}"})

    if not isinstance(d.get("active", True), bool):
        errors.append({"field": "active", "code": "invalid_type",
                       "message": "active must be a boolean"})

    params = d.get("params", {})
    if not isinstance(params, dict):
        errors.append({"field": "params", "code": "invalid_type",
                       "message": "params must be a JSON object"})
        return errors

    if rule_type == "allowed_values":
        if "values" in params:
            vals = params["values"]
            if not isinstance(vals, list) or len(vals) == 0:
                errors.append({"field": "params.values", "code": "invalid_value",
                               "message": "values must be a non-empty list"})
        if "reference_set" in params and (not isinstance(params["reference_set"], int) or params["reference_set"] <= 0):
            errors.append({"field": "params.reference_set", "code": "invalid_type",
                           "message": "reference_set must be a positive integer"})
        if "values" not in params and "reference_set" not in params:
            errors.append({"field": "params", "code": "required",
                           "message": "allowed_values requires 'values' or 'reference_set'"})

    elif rule_type == "range":
        if "min" not in params and "max" not in params:
            errors.append({"field": "params", "code": "required",
                           "message": "range requires at least one of min or max"})
        # range is an inclusive [min, max] bound with no comparison operator;
        # comparisons (e.g. "greater than 0") belong to ``threshold``.
        if "operator" in params:
            errors.append({"field": "params.operator", "code": "invalid_value",
                           "message": "range does not support operator; use type 'threshold' with operator gt/gte/lt/lte for inequality comparisons"})
        for key in ("min", "max"):
            if key in params:
                try:
                    float(params[key])
                except (TypeError, ValueError):
                    errors.append({"field": f"params.{key}", "code": "invalid_type",
                                   "message": f"{key} must be numeric"})

    elif rule_type == "regex":
        pattern = params.get("pattern", "")
        if not pattern or not isinstance(pattern, str):
            errors.append({"field": "params.pattern", "code": "required",
                           "message": "regex requires a non-empty pattern string"})
        else:
            try:
                re.compile(pattern)
            except re.error as exc:
                errors.append({"field": "params.pattern", "code": "invalid_value",
                               "message": f"regex pattern does not compile: {exc}"})

    elif rule_type == "reference_integrity":
        rs_id = params.get("reference_set_id")
        if rs_id is None:
            errors.append({"field": "params.reference_set_id", "code": "required",
                           "message": "reference_integrity requires reference_set_id (int)"})
        elif not isinstance(rs_id, int) or rs_id <= 0:
            errors.append({"field": "params.reference_set_id", "code": "invalid_type",
                           "message": "reference_set_id must be a positive integer"})

    elif rule_type == "threshold":
        operator = params.get("operator", "gte")
        if operator not in _THRESHOLD_OPERATORS:
            errors.append({"field": "params.operator", "code": "invalid_value",
                           "message": f"operator must be one of {sorted(_THRESHOLD_OPERATORS)}"})
        if "value" not in params:
            errors.append({"field": "params.value", "code": "required",
                           "message": "threshold requires a numeric value"})
        else:
            try:
                float(params["value"])
            except (TypeError, ValueError):
                errors.append({"field": "params.value", "code": "invalid_type",
                               "message": "value must be numeric"})

    elif rule_type == "nl_check":
        prompt = params.get("prompt", "")
        if not prompt or not isinstance(prompt, str):
            errors.append({"field": "params.prompt", "code": "required",
                           "message": "nl_check requires a non-empty prompt string"})

    return errors


def _row_value(row: dict, column: str) -> Any:
    """Best-effort column lookup across common key spellings."""
    if not isinstance(row, dict):
        return None
    if column in row:
        return row[column]
    for key, value in row.items():
        if isinstance(key, str) and key.lower() == column.lower():
            return value
    return None


def _evaluate(definition: dict, sample_rows: list, column: str) -> dict:
    """Deterministic dry-run evaluation. Returns a preview dict."""
    rule_type = definition.get("type")
    params = definition.get("params", {}) or {}
    failed_rows: list[int] = []

    if rule_type == "not_null":
        for i, row in enumerate(sample_rows):
            v = _row_value(row, column)
            if v is None or (isinstance(v, str) and not v.strip()):
                failed_rows.append(i)

    elif rule_type == "unique":
        seen = {}
        for i, row in enumerate(sample_rows):
            v = _row_value(row, column)
            if v in seen:
                failed_rows.append(i)
                if seen[v] not in failed_rows:
                    failed_rows.append(seen[v])
            else:
                seen[v] = i
        failed_rows = sorted(set(failed_rows))

    elif rule_type == "allowed_values":
        allowed = set(params.get("values", []))
        for i, row in enumerate(sample_rows):
            if _row_value(row, column) not in allowed:
                failed_rows.append(i)

    elif rule_type == "range":
        lo = params.get("min")
        hi = params.get("max")
        for i, row in enumerate(sample_rows):
            v = _row_value(row, column)
            try:
                num = float(v)
            except (TypeError, ValueError):
                failed_rows.append(i)
                continue
            if lo is not None and num < float(lo):
                failed_rows.append(i)
            elif hi is not None and num > float(hi):
                failed_rows.append(i)

    elif rule_type == "regex":
        pattern = params.get("pattern", "")
        try:
            rx = re.compile(pattern)
        except re.error:
            return {"passed": None, "evaluable": False,
                    "explanation": "regex pattern does not compile"}
        for i, row in enumerate(sample_rows):
            v = _row_value(row, column)
            if v is None or not rx.search(str(v)):
                failed_rows.append(i)

    passed = len(failed_rows) == 0
    return {
        "passed": passed,
        "evaluable": True,
        "failed_rows": failed_rows,
        "failed_count": len(failed_rows),
        "sample_count": len(sample_rows),
        "explanation": (
            f"{len(failed_rows)} of {len(sample_rows)} sample row(s) violate the rule"
            if failed_rows else "all sample rows satisfy the rule"
        ),
    }


def build_definition(args: dict) -> tuple[dict, list[dict]]:
    """Build a v1 rule definition from tool args; return (definition, errors)."""
    definition: dict[str, Any] = {
        "schema_version": 1,
        "name": (args.get("name") or "").strip(),
        "level": args.get("level", "field"),
        "dimension": args.get("dimension", "validity"),
        "type": args.get("rule_type", ""),
        "severity": args.get("severity", "error"),
        "active": bool(args.get("is_active", True)),
    }
    params = args.get("params") or {}
    if isinstance(params, dict):
        definition["params"] = params
    if args.get("description"):
        definition["description"] = args["description"]
    if args.get("nl_check"):
        definition.setdefault("params", {})["prompt"] = args["nl_check"]
    return definition, _validate_definition(definition)


def _binding_errors(rule_type: str, args: dict) -> list[dict]:
    """Return binding-target errors for deterministic rules.

    Deterministic rules (``not_null``, ``unique``, ``allowed_values``,
    ``range``, ``regex``) evaluate a specific column, so they must bind to a
    real field — ``data_table`` + ``data_field`` ids. The host POST maps
    exactly those two to a ``RuleFieldAssignment``; without them the rule is
    created bound to nothing (a phantom rule). Fail-visible with a targeted
    clarifying question instead of staging an unusable rule silently.

    Business/``nl_check``/``reference_integrity``/``threshold`` rules skip
    this check — they either don't need a field or resolve it elsewhere.
    """
    if rule_type not in _DETERMINISTIC_TYPES:
        return []

    errors: list[dict] = []
    if not args.get("data_table"):
        errors.append({
            "field": "data_table",
            "code": "missing_binding",
            "message": (
                "Which table should this rule apply to? Provide data_table "
                "(the DataTable id)."
            ),
        })
    if not args.get("data_field"):
        errors.append({
            "field": "data_field",
            "code": "missing_binding",
            "message": (
                "Which field/column should this rule check? Provide data_field "
                "(the DataField id)."
            ),
        })
    return errors


# ── Plugin ────────────────────────────────────────────────────────────────


class CreateDQRule(ToolPlugin):
    """Propose a data-quality rule, preview it, and create it on confirmation."""

    name = "create_dq_rule"
    description = (
        "Propose and create a data-quality (DQ) rule. Builds a rule definition "
        "from the argued fields, validates it, dry-run evaluates deterministic "
        "rules against optional sample rows, and stages a POST to /dq/rules/ "
        "that only executes after the user confirms. Use when the user asks to "
        "add a rule such as 'validate the email field' or 'flag null names'."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Human-readable rule name."},
            "rule_type": {
                "type": "string",
                "enum": sorted(_RULE_TYPES),
                "description": (
                    "DQ rule type. Use 'range' only for an inclusive [min, max] "
                    "bound. For comparisons like 'greater than 0' or 'less than X', "
                    "use 'threshold' with operator (gt|gte|lt|lte|eq|neq) + value."
                ),
            },
            "level": {
                "type": "string",
                "enum": sorted(_LEVELS),
                "description": "field (write-gate) or business (job) rule.",
            },
            "severity": {
                "type": "string",
                "enum": sorted(_SEVERITIES),
                "description": "info | warn | error.",
            },
            "dimension": {
                "type": "string",
                "enum": sorted(_DIMENSIONS),
                "description": "DAMA DMBOK2 data-quality dimension.",
            },
            "description": {"type": "string", "description": "What this rule checks and why."},
            "column": {"type": "string", "description": "Target column for deterministic rules."},
            "params": {
                "type": "object",
                "description": (
                    "Type-specific params. range: min and/or max (inclusive). "
                    "threshold: operator (gt|gte|lt|lte|eq|neq) + value. "
                    "allowed_values: values (list) or reference_set (int). "
                    "regex: pattern (string). reference_integrity: reference_set_id (int). "
                    "nl_check: prompt (string)."
                ),
            },
            "data_table": {
                "type": "integer",
                "description": (
                    "DataTable id to bind the rule to. REQUIRED for deterministic "
                    "rule types (not_null, unique, allowed_values, range, regex)."
                ),
            },
            "data_field": {
                "type": ["integer", "null"],
                "description": (
                    "DataField id the rule checks. REQUIRED for deterministic "
                    "rule types (not_null, unique, allowed_values, range, regex)."
                ),
            },
            "sample_rows": {
                "type": "array",
                "items": {"type": "object"},
                "description": "Optional sample rows for the dry-run preview.",
            },
            "is_active": {"type": "boolean", "description": "Whether the rule is active."},
        },
        "required": ["name", "rule_type", "level"],
    }
    requires_confirmation = True
    capability = "dq:manage_rules"
    app_identifier = "dq"

    async def execute(self, args: dict, *, ctx) -> dict:
        host_api = ctx.host_api
        if host_api is None:
            return {"error": "Host API executor not available for create_dq_rule"}

        if not getattr(host_api, "user_token", None):
            return {
                "error": (
                    "create_dq_rule requires an authenticated session. Please "
                    "log in and connect your account before creating DQ rules."
                )
            }

        definition, errors = build_definition(args)
        # Intelligence gate (2026-08-27): a deterministic rule evaluates a
        # specific column, so it MUST bind to a real field (data_table +
        # data_field). Without them the host POST creates a rule bound to
        # nothing — a phantom rule. Fail-visible with a targeted
        # clarifying question instead of silently staging an unusable rule.
        errors.extend(_binding_errors(definition.get("type"), args))
        if errors:
            messages = "; ".join(e.get("message", "") for e in errors if e.get("message"))
            return {
                "requires_confirmation": False,
                "error": (
                    f"Proposed DQ rule is incomplete — nothing was written. "
                    + (messages or "the rule definition is invalid.")
                ),
                "validation": {"passed": False, "errors": errors},
                "clarification": {
                    "needed": True,
                    "missing": [e.get("field") for e in errors if e.get("field")],
                },
            }

        preview = self._preview(definition, args)

        body = self._build_post_body(definition, args)
        execution = await host_api.create_pending_execution(
            conversation_id=ctx.conversation_id,
            tool_name=self.name,
            method="POST",
            endpoint="/carbon-api/dq/rules/",
            body=body,
            confirmation_message=(
                f"Create DQ rule '{definition['name']}' ({definition['type']})?"
            ),
        )
        return {
            "requires_confirmation": True,
            "execution_id": execution.id,
            "proposed_rule": definition,
            # The exact denormalized body that will be POSTed to
            # /carbon-api/dq/rules/ on confirmation — lets the UI show the
            # full JSON and lets the user modify it before confirming.
            "proposed_body": body,
            "validation": preview,
        }

    # ── helpers ──────────────────────────────────────────────────────────

    def _preview(self, definition: dict, args: dict) -> dict:
        column = args.get("column") or ""
        sample_rows = args.get("sample_rows") or []
        if definition.get("type") not in _DETERMINISTIC_TYPES or not column:
            return {
                "passed": None,
                "evaluable": False,
                "explanation": (
                    "Deterministic preview requires a column and sample rows; "
                    "structural validation only."
                ),
            }
        if not sample_rows:
            return {"passed": None, "evaluable": False,
                    "explanation": "no sample rows provided"}
        return _evaluate(definition, sample_rows, column)

    def _build_post_body(self, definition: dict, args: dict) -> dict:
        """Build the denormalized host POST body for DQRuleViewSet."""
        level = definition.get("level", "field")
        body: dict[str, Any] = {
            "name": definition["name"],
            "rule_type": definition["type"],
            "rule_level": _LEVEL_MAP.get(level, "field_validation"),
            "severity": definition.get("severity", "error"),
            "dimension": definition.get("dimension", "validity"),
            "is_active": definition.get("active", True),
            "definition": definition,
        }
        if definition.get("description"):
            body["description"] = definition["description"]
        if definition.get("params"):
            body["params"] = definition["params"]

        assignments = []
        if args.get("data_table"):
            assignments.append({
                "data_table": args["data_table"],
                "data_field": args.get("data_field"),
            })
        if assignments:
            body["field_assignments_write"] = assignments
        return body
