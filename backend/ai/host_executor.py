"""In-process Carbon host executor — Django-side transport for Pulse tools.

The vendored engine's :class:`HostAPIExecutor` talks to the host system over
HTTP + per-user JWT.  For the Carbon platform the host API *is* this Django
process, so the transport is in-process:

  * ``create_pending_execution`` stages a ``ToolExecution`` row exactly as the
    engine designs it (status ``pending_confirmation``, RULE_21).
  * ``confirm_execution`` / ``decline_execution`` operate on the staged row
    with the Django Store session (the base class uses raw SQLAlchemy
    ``execute()``, which the Django Store session does not expose).
  * ``_call_api`` dispatches known mutation endpoints directly against the
    platform's serializers — no loopback HTTP, no JWT minting.

The plugin layer (``ai.plugins.create_dq_rule``) stays untouched: it only
needs ``ctx.host_api`` with a truthy ``user_token`` and a ``db`` session, both
of which this class provides.

RULE_20 applies to plugins, not to this host-side adapter: this module is the
Carbon implementation of the executor interface and is allowed to import the
platform's own serializers/models (it plays the same role as the HTTP view
stack would).
"""

from __future__ import annotations

import json
import logging
from decimal import Decimal

from ai.engine.agent.executor import HostAPIExecutor
from ai.engine.core.exceptions import ToolExecutionError

logger = logging.getLogger("carbon.ai.host_executor")


def _json_coerce(obj: object) -> object:
    """json.dumps default — Decimal→float, everything else→str."""
    if isinstance(obj, Decimal):
        return float(obj)
    return str(obj)


#: Worker read-only tools (mirrors ``ai.engine.agent.guardrails._READONLY_TOOLS``).
#: Anything else is treated as read for the worker boundary — the worker's tool
#: set is already filtered, matching the old ``readonly_worker_hook`` "allow it".
_READONLY_WORKER_TOOLS: frozenset[str] = frozenset({
    "search_knowledge",
    "get_entity_details",
    "query_knowledge_graph",
    "get_schema_info",
    "get_relationship_info",
    "get_table_profile",
})


def _worker_is_mutation(name: str, args: dict) -> bool:
    """Classify a worker tool call as a mutation (mirror readonly_worker_hook).

    Read-only tools are never mutations; ``call_host_api`` is a mutation iff it
    carries a body or an explicit mutating ``_method``; any other tool passes
    as read (matching the old hook's "allow it").
    """
    if name in _READONLY_WORKER_TOOLS:
        return False
    if name == "call_host_api":
        has_body = bool(args.get("body"))
        method = str(args.get("_method", "")).upper()
        return has_body or method in {"POST", "PUT", "DELETE", "PATCH"}
    return False


def _canonical_endpoint(endpoint: str) -> str:
    """Normalize an endpoint path for the in-process route table.

    Strips the leading scheme-ish slash(es), any trailing slash, and any
    query string so ``/carbon-api/dataschema/tables/?module_id=31`` maps to
    ``carbon-api/dataschema/tables``.
    """
    path = (endpoint or "").strip()
    if "?" in path:
        path = path.split("?", 1)[0]
    while path.startswith("/"):
        path = path[1:]
    return path.rstrip("/")


#: Hard cap on serialised list rows sent to the LLM.  Above this, the response
#: carries ``truncated=True`` and ``total=<full count>`` so the model can never
#: mistake a partial page for the full population.
_PEOPLE_LIST_PAGE_CAP = 100


def _employee_param_from_query(params: dict | None) -> str:
    """Pull employee identity from common query-param aliases (pk or employee_no)."""
    if not params:
        return ""
    for key in ("employee", "employee_id", "employee_no", "employeeNo"):
        raw = params.get(key)
        if raw is None or raw == "":
            continue
        return str(raw).strip()
    return ""


def _filter_qs_by_employee_param(qs, params: dict | None, *, emp_field: str = "employee"):
    """Narrow an employee-linked queryset by pk or employee_no.

    B1: leave/loan list endpoints must honour ``?employee=`` / ``?employee_no=``
    so a focused-person follow-up never returns the first page of org-wide rows
    (which the model then mislabels as e.g. ``Employee 333``).
    """
    key = _employee_param_from_query(params)
    if not key:
        return qs
    from django.db.models import Q

    # Accept pk or employee_no interchangeably (same contract as get_employee).
    if key.isdigit():
        return qs.filter(
            Q(**{f"{emp_field}_id": int(key)})
            | Q(**{f"{emp_field}__employee_no": key})
        )
    return qs.filter(**{f"{emp_field}__employee_no": key})


def _annotate_employee_identity(results: list, qs) -> list:
    """Attach employee_no + full_name next to the FK id for honest table titles.

    Serializer leaves ``employee`` as a bare pk; without identity fields the
    model invents ``Employee {pk}`` labels (B1 drift).
    """
    if not results:
        return results
    ids = {r.get("employee") for r in results if isinstance(r, dict) and r.get("employee") is not None}
    if not ids:
        return results
    # Prefer already-joined relation when present; else one lookup.
    id_to_identity: dict = {}
    try:
        from people.models import Employee

        for emp in Employee.objects.filter(pk__in=ids).only("id", "employee_no", "full_name"):
            id_to_identity[emp.pk] = {
                "employee_no": emp.employee_no,
                "employee_name": emp.full_name,
            }
    except Exception:  # noqa: BLE001 — enrichment is best-effort
        return results
    enriched = []
    for row in results:
        if not isinstance(row, dict):
            enriched.append(row)
            continue
        clone = dict(row)
        ident = id_to_identity.get(clone.get("employee"))
        if ident:
            clone.setdefault("employee_no", ident["employee_no"])
            clone.setdefault("employee_name", ident["employee_name"])
        enriched.append(clone)
    return enriched

#: After normalization, collapse the tail into an "Other" bucket so the model
#: never receives a 200-row breakdown it can't interpret.
_ANALYTICS_MAX_BUCKETS = 15

#: Synonym maps for free-text categorical fields.
#: canonical_label → frozenset of raw string values that map to it (case-insensitive, stripped).
_FIELD_SYNONYMS: dict[str, dict[str, frozenset]] = {
    "gender": {
        "male":   frozenset({"male", "m", "man", "boy", "males"}),
        "female": frozenset({"female", "f", "woman", "girl", "females"}),
    },
}


def _normalise_value(dimension: str, raw_val) -> str:
    """Return the canonical label for a raw DB value (synonym merging + blank handling)."""
    if raw_val is None or (isinstance(raw_val, str) and not raw_val.strip()):
        return "(blank)"
    synonyms = _FIELD_SYNONYMS.get(dimension, {})
    low = str(raw_val).strip().lower()
    for canonical, values in synonyms.items():
        if low in values:
            return canonical
    return str(raw_val).strip()


def _suggest_chart_type(breakdown: list[dict]) -> str:
    """Return the most informative chart type given the breakdown shape.

    Pie is only useful for balanced proportions (≤8 buckets, no dominant slice).
    A 99% / 1% pie is meaningless — bar shows magnitude far better.
    """
    if not breakdown:
        return "bar"
    max_pct = max((r["pct"] for r in breakdown), default=0)
    n = len(breakdown)
    if max_pct >= 70:
        # One dominant bucket — a single giant pie slice adds zero information
        return "bar"
    if n <= 8:
        return "pie"
    return "bar"

#: Endpoints handled in-process instead of over HTTP.  Values are the names of
#: private ``_<name>_in_process`` coroutines on :class:`CarbonHostExecutor`.
_IN_PROCESS_ENDPOINTS: dict[str, str] = {
    "carbon-api/dq/rules": "dq_rules",
    "carbon-api/dataschema/tables": "tables",
    "carbon-api/dataschema/tables/detail": "table_detail",
    "carbon-api/dq/rule-assignments": "rule_assignments",
    "carbon-api/carbon/factors": "emission_factors",
    "carbon-api/carbon/gwp": "gwp_gases",
    "carbon-api/carbon/periods": "reporting_periods",
    "carbon-api/carbon/calculations/summary": "calculation_summary",
    "carbon-api/carbon/chairman": "chairman_overview",
    # Server-side analytics (aggregation, label resolution, DQ disclosure)
    "carbon-api/people/analytics": "people_analytics",
}


def _people_route(key: str) -> tuple[str, str | None, str | None]:
    """Split a canonical People endpoint into ``(resource, pk, action)``.

    ``carbon-api/people/employees/5``            → ``("employees", "5", None)``
    ``carbon-api/people/payroll-runs/5/compute`` → ``("payroll-runs", "5", "compute")``
    ``carbon-api/people/employees``              → ``("employees", None, None)``
    """
    rest = (key or "")
    prefix = "carbon-api/people"
    if rest == prefix:
        return "", None, None
    if rest.startswith(prefix + "/"):
        rest = rest[len(prefix) + 1:]
    parts = [p for p in rest.split("/") if p]
    resource = parts[0] if parts else ""
    pk = parts[1] if len(parts) > 1 else None
    action = parts[2] if len(parts) > 2 else None
    return resource, pk, action


def _parse_payroll_period_hint(token: str) -> tuple[int, int] | None:
    """Extract (year, month) from planner aliases like ``demo-oct-2026``."""
    from ai.engine.agent.period_alias import parse_period_alias

    return parse_period_alias(token)


def _resolve_payroll_run(qs, pk):
    """Resolve a payroll run by numeric pk OR period alias (demo-oct-2026).

    Planners routinely invent ``run_id: demo-oct-2026`` from the brief; the
    ORM only accepts integer PKs. Map month/year hints onto ``period_start``
    so compute/validate do not crash with ``Field 'id' expected a number``.
    """
    from people.models import PayrollRun
    from ai.engine.agent.period_alias import item_matches_period

    if pk is None or pk == "":
        raise PayrollRun.DoesNotExist("Payroll run id required")
    pk_str = str(pk).strip()
    if pk_str.isdigit():
        return qs.get(pk=int(pk_str))

    hint = _parse_payroll_period_hint(pk_str)
    if hint:
        year, month = hint
        matches = [
            r for r in qs.order_by("-period_start", "-id")[:40]
            if item_matches_period(
                {"period_start": r.period_start.isoformat()}, year, month,
            )
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            preferred = next(
                (r for r in matches if r.status in ("draft", "computed", "validated")),
                matches[0],
            )
            return preferred

    available = list(qs.order_by("-period_start")[:5])
    hint_bits = [
        f"#{r.pk} {r.period_start}→{r.period_end} ({r.status})"
        for r in available
    ]
    raise PayrollRun.DoesNotExist(
        f"No payroll run matches id={pk_str!r}. "
        + (
            f"Available: {'; '.join(hint_bits)}."
            if hint_bits
            else "No payroll runs in scope — create or list payroll-runs first."
        )
    )


def _people_can(user, capability_key: str) -> bool:
    """CBAC gate mirroring ``PeopleAccess`` (global admins bypass)."""
    from people.permissions import is_global_admin

    if is_global_admin(user):
        return True
    from accounts.capabilities import has_capability

    return has_capability(user, capability_key)


def _people_scope(user, qs, org_lookup: str):
    """RULE_12 org scoping — global admins see everything, else visible orgs."""
    from people.permissions import is_global_admin

    if is_global_admin(user):
        return qs
    from accounts.rbac_utils import get_visible_org_units

    ids = [ou.id for ou in get_visible_org_units(user)]
    if not ids:
        return qs.none()
    return qs.filter(**{org_lookup: ids})


# Host-side org-scope lookups for ECF entity_fetch / entity_count (RULE_12).
# Engine descriptors declare the same paths; the host bridge must apply them
# even when the resolver does not pass scope_ids (current resolve_entity path).
_PEOPLE_ENTITY_SCOPE_LOOKUP: dict[str, str] = {
    "people.models.Employee": "org_unit_id__in",
    "people.models.Position": "org_unit_id__in",
    "people.models.PayrollRun": "org_unit_id__in",
    "people.models.LeaveRecord": "employee__org_unit_id__in",
    "people.models.LeaveEntitlement": "employee__org_unit_id__in",
    "people.models.Loan": "employee__org_unit_id__in",
    "people.models.LoanInstallment": "loan__employee__org_unit_id__in",
    "people.models.AttendanceRecord": "employee__org_unit_id__in",
}

# Soft aliases for pre-ReferenceValue CharField filter keys in ECF metrics/resolves.
# Analytics already remaps dimensions; entity_fetch/entity_count must too (A9).
_PEOPLE_ENTITY_FILTER_ALIASES: dict[str, str] = {
    "nationality_code": "nationality__code",
    "employment_type_code": "employment_type__code",
    "contract_type_code": "contract_type__code",
    "gender_code": "gender__code",
}
# Legacy short codes → live ReferenceValue.code (nibras People seed uses KWT).
_PEOPLE_REF_CODE_ALIASES: dict[tuple[str, str], str] = {
    ("nationality__code", "KW"): "KWT",
    ("nationality_code", "KW"): "KWT",
}


def _normalize_people_entity_filters(filters: dict | None) -> dict:
    """Remap legacy ECF filter keys/codes onto live People ORM lookups."""
    if not filters:
        return {}
    out: dict = {}
    for key, value in filters.items():
        nk = _PEOPLE_ENTITY_FILTER_ALIASES.get(key, key)
        if isinstance(value, str):
            value = _PEOPLE_REF_CODE_ALIASES.get((nk, value), value)
            value = _PEOPLE_REF_CODE_ALIASES.get((key, value), value)
        out[nk] = value
    return out


def _people_entity_scope_lookup(model_path: str, instance_config: dict | None = None) -> str | None:
    """Return Django filter key for org scoping a People model path.

    Prefers descriptor ``scope_lookup`` from instance_config when present
    (same source as ECF registry); falls back to the host map so LeaveRecord
    uses ``employee__org_unit_id__in`` even if config is empty.
    """
    for ent in (instance_config or {}).get("entities") or []:
        if not isinstance(ent, dict):
            continue
        if ent.get("model") == model_path and ent.get("scope_lookup"):
            return ent["scope_lookup"]
    return _PEOPLE_ENTITY_SCOPE_LOOKUP.get(model_path)


def _normalize_entity_row(row: dict, model_cls) -> dict:
    """Coerce ORM values() rows into descriptor-friendly dicts.

    - FK attnames (``employee_id``) also exposed under field name (``employee``)
      so label_map / search_fields match descriptor keys.
    - date/datetime/Decimal → str for resolver string scoring.
    """
    from datetime import date, datetime

    out = dict(row)
    for f in model_cls._meta.concrete_fields:
        if getattr(f, "is_relation", False) and f.many_to_one:
            att, name = f.attname, f.name
            if att in out and name not in out:
                out[name] = out[att]
    for k, v in list(out.items()):
        if isinstance(v, datetime):
            out[k] = v.isoformat()
        elif isinstance(v, date):
            out[k] = v.isoformat()
        elif isinstance(v, Decimal):
            out[k] = str(v)
    return out


def _people_analytics(user, params: dict) -> dict:
    """Server-side analytics: GROUP BY ``dimension`` over the scoped Employee set.

    Returns a pre-computed, normalised breakdown the LLM can narrate directly:

    .. code-block:: json

        {
          "dimension": "gender",
          "total": 535,
          "breakdown": [
            {"label": "(blank)", "count": 529, "pct": 98.9},
            {"label": "male",    "count": 5,   "pct": 0.9,
             "merged_from": ["M"]}
          ],
          "caveats": ["98.9% have no gender recorded…"],
          "was_normalized": true,
          "normalization_notes": ["'M' was merged into 'male' (likely a data-entry variant)"],
          "suggested_chart_type": "bar",
          "label_resolved": false
        }

    ``suggested_chart_type`` is determined by data shape, not by the LLM:
    ``"pie"`` for balanced proportions (≤8 buckets, no dominant slice),
    ``"bar"`` otherwise (including any distribution with a >70 % dominant bucket).
    """
    from collections import defaultdict

    from django.db.models import Count
    from people.models import Employee

    ALLOWED_DIMENSIONS = {
        "gender", "is_active", "nationality",
        "employment_type", "contract_type",
        "position", "org_unit", "kuwaitization", "rotation",
    }
    # Soft aliases for pre-ReferenceValue dimension names (CharField *_code era).
    DIMENSION_ALIASES = {
        "nationality_code": "nationality",
        "employment_type_code": "employment_type",
        "contract_type_code": "contract_type",
    }
    FK_LABEL_MAP = {
        "position": ("people.models.Position", "title"),
        "org_unit": ("mdm.models.OrgUnit", "name"),
        # Bucket-1 governed refs (NSR-7B): Employee FKs → ReferenceValue.code
        "gender": ("mdm.models.ReferenceValue", "code"),
        "nationality": ("mdm.models.ReferenceValue", "code"),
        "employment_type": ("mdm.models.ReferenceValue", "code"),
        "contract_type": ("mdm.models.ReferenceValue", "code"),
        "rotation": ("mdm.models.ReferenceValue", "code"),
    }
    BLANK_CAVEAT_PCT = 50.0

    dimension = (params.get("dimension") or "").strip().lower()
    dimension = DIMENSION_ALIASES.get(dimension, dimension)
    if dimension not in ALLOWED_DIMENSIONS:
        return {
            "status_code": 400,
            "data": {
                "detail": (
                    f"Unknown dimension '{dimension}'. "
                    f"Allowed: {', '.join(sorted(ALLOWED_DIMENSIONS | set(DIMENSION_ALIASES)))}"
                )
            },
        }

    qs = _people_scope(user, Employee.objects.all(), "org_unit_id__in")
    total = qs.count()
    if total == 0:
        return {
            "status_code": 200,
            "data": {
                "dimension": dimension,
                "total": 0,
                "breakdown": [],
                "caveats": ["No employees visible to this user."],
                "was_normalized": False,
                "normalization_notes": [],
                "suggested_chart_type": "bar",
                "label_resolved": False,
            },
        }

    raw_counts = (
        qs.values(dimension)
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    # ── Synonym normalisation + FK label resolution ─────────────────────────
    # Merge raw DB values into canonical buckets so "M" and "male" become one row.
    # For ReferenceValue / model FKs: resolve PK → label/code, then synonym-merge.
    bucket_counts: dict[str, int] = defaultdict(int)
    bucket_merged_from: dict[str, list[str]] = defaultdict(list)
    label_resolved = False
    pk_to_label: dict = {}
    was_normalized = False

    if dimension in FK_LABEL_MAP:
        # FK dimensions: resolve PK → human label via a secondary query.
        import importlib
        module_path, label_field = FK_LABEL_MAP[dimension]
        mod_name, cls_name = module_path.rsplit(".", 1)
        mod = importlib.import_module(mod_name)
        model_cls = getattr(mod, cls_name)
        pk_ids = [r[dimension] for r in raw_counts if r[dimension] is not None]
        for obj in model_cls.objects.filter(pk__in=pk_ids).values("pk", label_field):
            pk_to_label[obj["pk"]] = obj[label_field]
        label_resolved = True
        for row in raw_counts:
            raw_val = row[dimension]
            displayed = (
                pk_to_label.get(raw_val) if raw_val is not None else None
            )
            canonical = _normalise_value(dimension, displayed)
            bucket_counts[canonical] += row["count"]
            if displayed and str(displayed).strip() and str(displayed).strip() != canonical:
                bucket_merged_from[canonical].append(str(displayed).strip())
                was_normalized = True
    else:
        for row in raw_counts:
            raw_val = row[dimension]
            canonical = _normalise_value(dimension, raw_val)
            bucket_counts[canonical] += row["count"]
            # Track which raw strings were merged into this canonical bucket.
            displayed = str(raw_val).strip() if raw_val is not None else ""
            if displayed and displayed != canonical:
                bucket_merged_from[canonical].append(displayed)
                was_normalized = True

    # ── Build sorted breakdown, collapse long tail into "Other" ────────────
    sorted_buckets = sorted(bucket_counts.items(), key=lambda kv: -kv[1])
    blank_count = bucket_counts.get("(blank)", 0)

    breakdown: list[dict] = []
    other_count = 0
    other_labels: list[str] = []

    for i, (label, count) in enumerate(sorted_buckets):
        pct = round(count / total * 100, 1)
        row: dict = {"label": label, "count": count, "pct": pct}
        if bucket_merged_from.get(label):
            row["merged_from"] = bucket_merged_from[label]
        if i < _ANALYTICS_MAX_BUCKETS:
            breakdown.append(row)
        else:
            other_count += count
            other_labels.append(label)

    if other_count:
        breakdown.append({
            "label": "Other",
            "count": other_count,
            "pct": round(other_count / total * 100, 1),
            "collapsed_labels": other_labels[:20],  # sample for transparency
        })

    # ── Caveats ─────────────────────────────────────────────────────────────
    caveats: list[str] = []
    blank_pct = round(blank_count / total * 100, 1) if total else 0
    if blank_pct >= BLANK_CAVEAT_PCT:
        caveats.append(
            f"{blank_pct}% of employees have no '{dimension}' recorded — "
            f"this distribution is incomplete and should not be used for compliance reporting."
        )
    if not label_resolved and dimension in FK_LABEL_MAP:
        caveats.append(f"'{dimension}' IDs could not be resolved to labels.")
    if other_count:
        caveats.append(
            f"The breakdown has been truncated to the top {_ANALYTICS_MAX_BUCKETS} buckets; "
            f"{len(other_labels)} additional values ({other_count} employees) are grouped as 'Other'."
        )

    # ── Normalization notes (explicit, machine-checkable) ───────────────────
    normalization_notes: list[str] = []
    for canonical, raw_list in bucket_merged_from.items():
        if raw_list:
            merged_str = ", ".join(f"'{v}'" for v in sorted(set(raw_list)))
            normalization_notes.append(
                f"{merged_str} → '{canonical}' (likely data-entry variants; "
                f"recommend standardising the source data)"
            )

    return {
        "status_code": 200,
        "data": {
            "dimension": dimension,
            "total": total,
            "breakdown": breakdown,
            "caveats": caveats,
            "was_normalized": was_normalized,
            "normalization_notes": normalization_notes,
            "suggested_chart_type": _suggest_chart_type(breakdown),
            "label_resolved": label_resolved,
        },
    }


def _people_execute(user, resource, pk, action, method, params, body) -> dict:
    """Execute a single People & Payroll operation against the Django models.

    Mirrors ``people/views.py``: CBAC (already gated by ``_people_can``),
    RULE_12 org scoping, serializer output, and the Tier-1 DQ write gate for
    mutations. Returns the same ``{"status_code": ..., "data": ...}`` shape
    as the HTTP transport.
    """
    from people import serializers as S
    from people.sensitivity import mask_employee, mask_employee_list

    # ── Server-side analytics (aggregation + label resolution + DQ caveats) ────
    if resource == "analytics":
        if method == "GET":
            return _people_analytics(user, params)
        return {"status_code": 405, "data": {"detail": "Analytics endpoint is read-only"}}

    # ── Employees ───────────────────────────────────────────────────────
    if resource == "employees":
        from people.models import Employee

        if method == "GET":
            qs = _people_scope(user, Employee.objects.all(), "org_unit_id__in")
            if pk:
                # Accept employee_no as well as numeric PK (ECF-4 fix).
                # Try PK first, then fall back to employee_no so "1046" resolves
                # via employee_no when no record has PK=1046.
                employee = None
                try:
                    employee = qs.get(pk=pk)
                except (Employee.DoesNotExist, ValueError, TypeError):
                    pass
                if employee is None:
                    try:
                        employee = qs.get(employee_no=str(pk))
                    except Employee.DoesNotExist:
                        pass
                if employee is None:
                    return {"status_code": 404, "data": {"detail": "Employee not found"}}
                raw = S.EmployeeSerializer(employee).data
                masked = mask_employee(raw, user)
                payload: dict = {"status_code": 200, "data": masked}
                # B5: when compensation was stripped, say unauthorized — never
                # leave a silent hole the LLM paraphrases as "no salary data".
                stripped = [
                    f for f in ("basic_salary",)
                    if f in raw and f not in masked
                ]
                if stripped:
                    from people.sensitivity import can_view_compensation
                    if not can_view_compensation(user):
                        payload["unauthorized"] = True
                        payload["status_code"] = 403
                        payload["capability"] = "people:view_compensation"
                        payload["unauthorized_fields"] = stripped
                        payload["message"] = (
                            "Not authorized to view compensation "
                            "(people:view_compensation required)."
                        )
                return payload
            # Count the full population before slicing — partial pages must
            # carry total+truncated so the LLM never mistakes 100 for 535.
            total = qs.count()
            page = qs[:_PEOPLE_LIST_PAGE_CAP]
            results = mask_employee_list(S.EmployeeSerializer(page, many=True).data, user)
            truncated = total > _PEOPLE_LIST_PAGE_CAP
            data = {"total": total, "count": len(results), "results": results}
            if truncated:
                data["truncated"] = True
                data["caveat"] = (
                    f"Showing first {len(results)} of {total} employees. "
                    "Use analyze_employees with a dimension for aggregate statistics "
                    "over the full population."
                )
            return {"status_code": 200, "data": data}

        if method == "POST":
            # create_employee / onboarding submit — same contract as
            # EmployeeListCreateView.post (serializer + onboard hooks).
            from django.db import IntegrityError
            from django.utils import timezone as dj_tz

            from people.chronicle import record_event, snapshot_employee
            from people.employee_onboard_service import onboard_employee
            from people.validation import validate_write

            serializer = S.EmployeeSerializer(data=body or {})
            if not serializer.is_valid():
                return {
                    "status_code": 400,
                    "data": {
                        "detail": "Validation failed",
                        "errors": json.dumps(serializer.errors, default=str),
                    },
                }
            opening_basic = serializer.validated_data.pop("opening_basic", None)
            instance = Employee(**serializer.validated_data)
            gate = validate_write(instance)
            if gate.get("blocked"):
                return {
                    "status_code": 422,
                    "data": {
                        "detail": "DQ validation blocked this write",
                        "sample_failures": gate.get("sample_failures"),
                    },
                }
            try:
                serializer.save()
            except IntegrityError:
                return {
                    "status_code": 400,
                    "data": {"employee_no": "This employee number is already taken."},
                }
            record_event(
                entity_type="Employee",
                entity_id=serializer.instance.pk,
                event_kind="hired",
                effective_date=dj_tz.localdate(),
                user=user,
                before=None,
                after=snapshot_employee(serializer.instance),
            )
            try:
                onboard_employee(
                    serializer.instance,
                    opening_basic=opening_basic,
                    user=user,
                )
            except Exception:  # noqa: BLE001 — hire succeeded; hooks are best-effort
                logger.exception(
                    "Employee onboard hooks failed for employee_no=%s",
                    serializer.instance.employee_no,
                )
            return {
                "status_code": 201,
                "data": mask_employee(S.EmployeeSerializer(serializer.instance).data, user),
            }

        if method == "PATCH" and pk:
            # update_employee / onboarding activate — same contract as
            # EmployeeDetailView.patch (partial update + chronicle).
            from django.utils import timezone as dj_tz

            from people.chronicle import record_event, snapshot_employee
            from people.compensation_service import CompensationService
            from people.validation import validate_write

            qs = _people_scope(user, Employee.objects.all(), "org_unit_id__in")
            try:
                employee = qs.get(pk=pk)
            except (Employee.DoesNotExist, ValueError, TypeError):
                return {"status_code": 404, "data": {"detail": "Employee not found"}}
            before = snapshot_employee(employee)
            old_salary = employee.basic_salary
            data = body or {}
            if "basic_salary" in data:
                verified = CompensationService.verified_basic_amount(employee)
                if verified is not None:
                    return {
                        "status_code": 400,
                        "data": {
                            "detail": (
                                "basic_salary cannot be changed while a verified "
                                "compensation ledger basic line exists; append a "
                                "new ledger line instead."
                            ),
                        },
                    }
            serializer = S.EmployeeSerializer(employee, data=data, partial=True)
            if not serializer.is_valid():
                return {
                    "status_code": 400,
                    "data": {
                        "detail": "Validation failed",
                        "errors": json.dumps(serializer.errors, default=str),
                    },
                }
            for field, value in serializer.validated_data.items():
                setattr(employee, field, value)
            gate = validate_write(employee)
            if gate.get("blocked"):
                return {
                    "status_code": 422,
                    "data": {
                        "detail": "DQ validation blocked this write",
                        "sample_failures": gate.get("sample_failures"),
                    },
                }
            serializer.save()
            if old_salary != employee.basic_salary:
                event_kind = "salary_change"
            elif before.get("org_unit_id") != employee.org_unit_id:
                event_kind = "transferred"
            else:
                event_kind = "profile_updated"
            record_event(
                entity_type="Employee",
                entity_id=employee.pk,
                event_kind=event_kind,
                effective_date=dj_tz.localdate(),
                user=user,
                before=before,
                after=snapshot_employee(employee),
            )
            return {
                "status_code": 200,
                "data": mask_employee(S.EmployeeSerializer(employee).data, user),
            }

    # ── Positions ───────────────────────────────────────────────────────
    if resource == "positions":
        from people.models import Position

        if method == "GET":
            qs = _people_scope(user, Position.objects.all(), "org_unit_id__in")
            total = qs.count()
            page = qs[:_PEOPLE_LIST_PAGE_CAP]
            results = S.PositionSerializer(page, many=True).data
            data = {"total": total, "count": len(results), "results": results}
            if total > _PEOPLE_LIST_PAGE_CAP:
                data["truncated"] = True
                data["caveat"] = f"Showing first {len(results)} of {total} positions."
            return {"status_code": 200, "data": data}

    # ── Payroll runs (list/detail + compute/validate/commit) ─────────────
    if resource == "payroll-runs":
        from people.models import PayrollRun

        if method == "GET":
            qs = _people_scope(user, PayrollRun.objects.all(), "org_unit_id__in")
            if pk:
                try:
                    run = _resolve_payroll_run(qs, pk)
                except PayrollRun.DoesNotExist as exc:
                    return {"status_code": 404, "data": {"detail": str(exc)}}
                return {"status_code": 200, "data": S.PayrollRunSerializer(run).data}
            results = S.PayrollRunSerializer(qs, many=True).data
            return {"status_code": 200, "data": {"count": len(results), "results": results}}

        if method == "POST" and action in ("compute", "validate", "commit"):
            from people.payroll_service import PayrollRunService, PayrollServiceError
            from people.validation import persist_findings

            qs = _people_scope(user, PayrollRun.objects.all(), "org_unit_id__in")
            try:
                run = _resolve_payroll_run(qs, pk)
            except PayrollRun.DoesNotExist as exc:
                return {"status_code": 404, "data": {"detail": str(exc)}}
            service = PayrollRunService()
            try:
                result = getattr(service, action)(run)
            except PayrollServiceError as exc:
                return {"status_code": 409, "data": {"detail": str(exc)}}
            if action in ("validate", "commit"):
                persist_findings(run, result.get("findings", []))
            return {"status_code": 200, "data": result}

    # ── Payslip lines ───────────────────────────────────────────────────
    if resource == "payslip-lines":
        from people.models import PayslipLine

        if method == "GET":
            qs = PayslipLine.objects.all()
            run_id = params.get("payroll_run")
            if run_id:
                qs = qs.filter(payroll_run_id=run_id)
            total = qs.count()
            page = qs[:_PEOPLE_LIST_PAGE_CAP]
            results = S.PayslipLineSerializer(page, many=True).data
            data = {"total": total, "count": len(results), "results": results}
            if total > _PEOPLE_LIST_PAGE_CAP:
                data["truncated"] = True
                data["caveat"] = f"Showing first {len(results)} of {total} payslip lines."
            return {"status_code": 200, "data": data}

    # ── Leave entitlements ──────────────────────────────────────────────
    if resource == "leave-entitlements":
        from people.models import LeaveEntitlement

        if method == "GET":
            qs = _people_scope(user, LeaveEntitlement.objects.all(), "employee__org_unit_id__in")
            qs = _filter_qs_by_employee_param(qs, params)
            total = qs.count()
            page = qs[:_PEOPLE_LIST_PAGE_CAP]
            results = _annotate_employee_identity(
                S.LeaveEntitlementSerializer(page, many=True).data, page,
            )
            data = {"total": total, "count": len(results), "results": results}
            if _employee_param_from_query(params):
                data["filtered_by_employee"] = _employee_param_from_query(params)
            if total > _PEOPLE_LIST_PAGE_CAP:
                data["truncated"] = True
                data["caveat"] = f"Showing first {len(results)} of {total} leave entitlements."
            return {"status_code": 200, "data": data}

    # ── Leave records (list + create) ───────────────────────────────────
    if resource == "leave-records":
        from people.models import LeaveRecord

        if method == "GET":
            qs = _people_scope(user, LeaveRecord.objects.all(), "employee__org_unit_id__in")
            qs = _filter_qs_by_employee_param(qs, params)
            total = qs.count()
            page = qs[:_PEOPLE_LIST_PAGE_CAP]
            results = _annotate_employee_identity(
                S.LeaveRecordSerializer(page, many=True).data, page,
            )
            data = {"total": total, "count": len(results), "results": results}
            if _employee_param_from_query(params):
                data["filtered_by_employee"] = _employee_param_from_query(params)
            if total > _PEOPLE_LIST_PAGE_CAP:
                data["truncated"] = True
                data["caveat"] = f"Showing first {len(results)} of {total} leave records."
            return {"status_code": 200, "data": data}
        if method == "POST":
            serializer = S.LeaveRecordSerializer(data=body)
            if not serializer.is_valid():
                return {
                    "status_code": 400,
                    "data": {
                        "detail": "Validation failed",
                        "errors": json.dumps(serializer.errors, default=str),
                    },
                }
            from people.validation import validate_write

            gate = validate_write(LeaveRecord(**serializer.validated_data))
            if gate["blocked"]:
                return {
                    "status_code": 422,
                    "data": {
                        "detail": "DQ validation blocked this write",
                        "sample_failures": gate["sample_failures"],
                    },
                }
            serializer.save()
            return {"status_code": 201, "data": serializer.data}

    # ── Loans ───────────────────────────────────────────────────────────
    if resource == "loans":
        from people.models import Loan

        if method == "GET":
            qs = _people_scope(user, Loan.objects.all(), "employee__org_unit_id__in")
            qs = _filter_qs_by_employee_param(qs, params)
            total = qs.count()
            page = qs[:_PEOPLE_LIST_PAGE_CAP]
            results = _annotate_employee_identity(
                S.LoanSerializer(page, many=True).data, page,
            )
            data = {"total": total, "count": len(results), "results": results}
            if _employee_param_from_query(params):
                data["filtered_by_employee"] = _employee_param_from_query(params)
            if total > _PEOPLE_LIST_PAGE_CAP:
                data["truncated"] = True
                data["caveat"] = f"Showing first {len(results)} of {total} loans."
            return {"status_code": 200, "data": data}

    # ── Loan installments ───────────────────────────────────────────────
    if resource == "loan-installments":
        from people.models import LoanInstallment

        if method == "GET":
            qs = _people_scope(user, LoanInstallment.objects.all(), "loan__employee__org_unit_id__in")
            total = qs.count()
            page = qs[:_PEOPLE_LIST_PAGE_CAP]
            results = S.LoanInstallmentSerializer(page, many=True).data
            data = {"total": total, "count": len(results), "results": results}
            if total > _PEOPLE_LIST_PAGE_CAP:
                data["truncated"] = True
                data["caveat"] = f"Showing first {len(results)} of {total} loan installments."
            return {"status_code": 200, "data": data}

    # ── Attendance ──────────────────────────────────────────────────────
    if resource == "attendance":
        from people.models import AttendanceRecord

        if method == "GET":
            qs = _people_scope(user, AttendanceRecord.objects.all(), "employee__org_unit_id__in")
            total = qs.count()
            page = qs[:_PEOPLE_LIST_PAGE_CAP]
            results = S.AttendanceRecordSerializer(page, many=True).data
            data = {"total": total, "count": len(results), "results": results}
            if total > _PEOPLE_LIST_PAGE_CAP:
                data["truncated"] = True
                data["caveat"] = f"Showing first {len(results)} of {total} attendance records."
            return {"status_code": 200, "data": data}

    return {"status_code": 404, "data": {"detail": f"Unknown People endpoint: {resource}"}}


def _people_me(user, sub, method) -> dict:
    """Self-service People reads — strictly scoped to the CALLER's own record.

    Mirrors ``people/self_views.py`` (``IsActiveEmployee``): every query is
    filtered to ``user.employee_profile`` so the caller can only ever see their
    own leave, balance, loans, payslips, and profile. Authorization here IS the
    self-scoping — it deliberately does NOT require ``people:view`` (an ordinary
    employee holds only ``my:access``). Fail-closed when no active employee is
    linked, so "my leave" can never fall back to the org-wide population.
    """
    from people.models import Employee

    if method not in ("GET", "HEAD", "OPTIONS"):
        return {"status_code": 405, "data": {"detail": "Self-service endpoints are read-only"}}

    try:
        profile = user.employee_profile
    except (Employee.DoesNotExist, AttributeError):
        profile = None
    if profile is None or not getattr(profile, "is_active", False):
        return {
            "status_code": 403,
            "data": {"detail": (
                "No active employee profile is linked to your account, so your "
                "personal records cannot be resolved."
            )},
        }

    from people.self_serializers import EmployeeSummarySerializer

    if not sub:
        return {"status_code": 200, "data": EmployeeSummarySerializer(profile).data}

    if sub == "leave":
        from people.models import LeaveRecord
        from people.self_serializers import LeaveRecordSerializer

        qs = LeaveRecord.objects.filter(employee=profile)
        results = LeaveRecordSerializer(qs, many=True).data
        return {"status_code": 200, "data": {"count": len(results), "results": results}}

    if sub == "leave-balance":
        from django.utils import timezone
        from mdm.models import ReferenceValue
        from people.self_serializers import LeaveBalanceSerializer
        from people.self_views import _compute_balance

        year = timezone.now().year
        codes = list(
            ReferenceValue.objects.filter(reference_set__name="leave_type")
            .order_by("sort_order", "code").values_list("code", flat=True)
        )
        balances = []
        for code in codes:
            entitled, carried, used, pending, remaining = _compute_balance(profile, code, year)
            balances.append({
                "leave_type": code, "entitled": entitled, "carried_forward": carried,
                "opening_balance": entitled + carried, "used": used, "pending": pending,
                "remaining": remaining,
            })
        return {"status_code": 200, "data": LeaveBalanceSerializer(balances, many=True).data}

    if sub == "loan":
        from people.models import Loan
        from people.serializers import LoanSerializer

        qs = Loan.objects.filter(employee=profile)
        results = LoanSerializer(qs, many=True).data
        return {"status_code": 200, "data": {"count": len(results), "results": results}}

    if sub == "payslips":
        from people.models import PayslipLine
        from people.self_views import COMMITTED_RUN_STATUSES
        from people import serializers as S
        from people.sensitivity import can_view_compensation

        qs = PayslipLine.objects.filter(
            employee=profile, payroll_run__status__in=COMMITTED_RUN_STATUSES,
        )
        results = S.PayslipLineSerializer(qs, many=True).data
        payload: dict = {
            "status_code": 200,
            "data": {"count": len(results), "results": results},
        }
        # B5: empty payslips must not become soft "no salary data" when the
        # caller lacks compensation access — surface an explicit CBAC deny.
        if not results and not can_view_compensation(user):
            payload["unauthorized"] = True
            payload["status_code"] = 403
            payload["capability"] = "people:view_compensation"
            payload["message"] = (
                "Not authorized to view compensation "
                "(people:view_compensation required)."
            )
        return payload

    return {"status_code": 404, "data": {"detail": f"Unknown self-service resource: me/{sub}"}}


# ── P3-10 — governed skill invocation seam ──────────────────────────────

# Map the process-definition autonomy levels (6 levels, ``VALID_AUTONOMY``) to
# the PDP's per-activity dial (3 levels: human_only / act_confirm / auto). The
# mapping is deliberately conservative: anything that does not already assume
# silent execution is treated as human-gated.
_PROCESS_TO_PDP_AUTONOMY = {
    "human_only": "human_only",
    "observe": "human_only",
    "propose": "human_only",
    "act_confirm": "act_confirm",
    "act_notify": "auto",
    "act_silent": "auto",
}


def _map_autonomy(autonomy: str | None) -> str:
    """Map a process-step autonomy to the PDP dial level (fail-closed default)."""
    return _PROCESS_TO_PDP_AUTONOMY.get(
        (autonomy or "human_only").strip(), "human_only"
    )


def _capability_contract(capability_id: str) -> dict:
    """Return ``{requires_grant, version}`` for a capability.

    Empty when the capability id is blank or the row is unknown (fail-closed:
    ``requires_grant`` defaults False, so the grant stage is never assumed
    present).
    """
    if not capability_id:
        return {"requires_grant": False, "version": ""}
    try:
        from ai.models.capability import Capability

        cap = Capability.objects.filter(capability_id=capability_id).first()
        if cap is None:
            return {"requires_grant": False, "version": ""}
        return {
            "requires_grant": bool(
                (cap.approval_requirements or {}).get("requires_grant")
            ),
            "version": str(cap.version) if cap.version else "",
        }
    except Exception:  # noqa: BLE001 — fail-closed, never assume a grant
        return {"requires_grant": False, "version": ""}


class CarbonHostExecutor(HostAPIExecutor):
    """HostAPIExecutor whose transport is this Django process.

    ``user_token`` is a synthetic marker (``inproc:<app>:<user_id>``) — the
    plugin layer gates on truthiness, and no real JWT is ever needed because
    requests never leave the process.  ``host_user_id`` is the Django user PK
    the staged actions execute as.
    """

    def __init__(
        self,
        db,
        instance_config: dict | None = None,
        user_token: str | None = None,
        host_user_id: str | None = None,
    ):
        super().__init__(db, instance_config=instance_config, user_token=user_token)
        self.host_user_id = host_user_id

    # ── Command boundary (P2-06b) ───────────────────────────────────────

    async def execute_host_api_via_boundary(
        self,
        *,
        effect,
        api_name: str,
        method: str,
        path: str,
        query_params: dict | None = None,
        body: dict | None = None,
        explanation: str = "",
        conversation_id: str = "",
        needs_confirmation: bool = False,
        instance_id: str = "",
        host_user_id: str | None = None,
    ) -> dict:
        """Route a resolved ``call_host_api`` effect through the fail-closed
        command boundary.

        ``effect`` is the engine tool's host-effect closure (``call_api_direct``
        for reads / ``create_pending_execution`` for mutations); this method
        wraps it in a :class:`~ai.command_boundary.Command` with a real PDP and
        ledger so every host effect passes identity → scope → contract →
        validate → PDP → consent → budget → idempotency → execute → verify →
        outcome.  ``requires_confirmation=False`` because the pending-execution
        card *is* the consent mechanism for mutations (stage 7 must not
        pre-refuse it).
        """
        from ai.command_boundary import Command
        from ai.command_boundary_factory import get_command_boundary
        from ai.protocol import Scope

        uid = str(host_user_id) if host_user_id else (instance_id or "")
        command = Command(
            principal=uid or None,
            scope=Scope(user_identifier=uid),
            tool="call_host_api",
            action="call_host_api",
            params={
                "api_name": api_name,
                "method": method,
                "path": path,
                "query_params": query_params,
                "body": body,
                "explanation": explanation,
                "conversation_id": conversation_id,
            },
            objects=[api_name],
            requires_confirmation=False,
            autonomy="human_only" if needs_confirmation else "auto",
            instance_id=instance_id,
            host_user_id=host_user_id,
        )
        boundary = get_command_boundary(
            self.db,
            executor=effect,
            tool_catalog={"call_host_api": True},
        )
        outcome = await boundary.execute(command)
        if outcome.status in ("executed", "confirmed"):
            result = outcome.result
            return result if isinstance(result, dict) else {"result": result}
        return {"error": outcome.error or outcome.reason or "action refused"}

    async def inspect_case_via_boundary(
        self,
        *,
        run_id,
        instance_id="",
        conversation_id="",
        host_user_id=None,
    ) -> dict:
        """Read-only case inspection (P4-05) through the fail-closed boundary.

        Resolves the caller and gates on ``ai:inspect_case`` BEFORE any read,
        then runs a SELECT-only effect closure that assembles the run's current
        activity, blocker, SLA, applicable SOP clause, and journal event ids.
        The boundary persists only its own PDP/ledger audit rows — the case
        tables (run/step/journal) are never mutated.
        """
        from asgiref.sync import sync_to_async

        from ai.command_boundary import Command
        from ai.command_boundary_factory import get_command_boundary
        from ai.protocol import Scope

        effective_host_user_id = host_user_id or self.host_user_id
        uid = str(effective_host_user_id) if effective_host_user_id else (instance_id or "")

        # ── Capability gate (fail-closed) — resolve the user and check the
        # ``ai:inspect_case`` capability BEFORE touching any case table.
        def _check_capability() -> bool:
            from accounts.capabilities import get_user_capabilities

            if not uid:
                return False
            from accounts.models import User

            try:
                user = User.objects.get(pk=uid)
            except Exception:  # noqa: BLE001 — fail closed on any resolution error
                return False
            return "ai:inspect_case" in get_user_capabilities(user)

        authorized = await sync_to_async(_check_capability, thread_sensitive=True)()
        if not authorized:
            return {"error": "missing capability ai:inspect_case"}

        # ── Read-only effect closure (SELECTs only — no mutation) ──────────
        def _gather_case() -> dict:
            from ai.models.core import Run, RunStep
            from ai.models.human_task import HumanTask
            from ai.models.process import ProcessDefinition
            from ai.models.step_journal import StepJournalEntry

            iso = lambda dt: dt.isoformat() if dt else None

            run = Run.objects.filter(id=run_id).first()
            if run is None:
                return {"error": "run not found", "run_id": run_id}

            steps = list(RunStep.objects.filter(run_id=run_id).order_by("step_index"))

            # Current activity = latest non-planned step (highest step_index with
            # a non-empty step_state/status); otherwise the last step.
            current_step = None
            for step in reversed(steps):
                state = (step.step_state or "").strip()
                status = (step.status or "").strip()
                if state not in ("", "planned") or status not in ("", "planned"):
                    current_step = step
                    break
            if current_step is None and steps:
                current_step = steps[-1]

            def _step_dict(step) -> dict:
                return {
                    "id": step.id,
                    "step_id": step.step_id,
                    "step_index": step.step_index,
                    "step_state": step.step_state,
                    "status": step.status,
                    "tool_name": step.tool_name,
                    "operation_id": step.operation_id,
                    "outcome": step.outcome,
                    "last_error": step.last_error,
                }

            current_activity = _step_dict(current_step) if current_step else None

            journal = list(
                StepJournalEntry.objects.filter(run_id=run_id).order_by("sequence")
            )
            event_ids = [
                {
                    "id": entry.id,
                    "event_type": entry.event_type,
                    "sequence": entry.sequence,
                    "step_id": entry.step_id,
                }
                for entry in journal
            ]
            operation_ids = sorted(
                {s.operation_id for s in steps if (s.operation_id or "").strip()}
            )

            # ── Blocker resolution (pending approval → kill switch → failed step) ──
            blocker = None
            pending = None
            for task in HumanTask.objects.filter(
                run_id=run_id, status="pending",
            ).order_by("created_at"):
                if not task.is_expired():
                    pending = task
                    break
            if pending is not None:
                blocker = {
                    "kind": "awaiting_approval",
                    "required_authority": pending.required_authority,
                    "task_id": pending.id,
                }
            elif run.kill_switched_at is not None:
                blocker = {"kind": "kill_switch", "at": iso(run.kill_switched_at)}
            else:
                failed_step = None
                for step in steps:
                    if (step.last_error or "").strip() and step.status == "failed":
                        failed_step = step
                        break
                if failed_step is not None:
                    blocker = {
                        "kind": "failed_step",
                        "step_id": failed_step.step_id,
                        "last_error": failed_step.last_error,
                    }

            # ── SLA + applicable SOP clause from the pinned definition ────
            sla: dict = {"constraints": []}
            applicable_sop_clause: list = []

            definition_qs = ProcessDefinition.objects.filter(
                process_id=run.definition_id,
            )
            if run.definition_version:
                definition_qs = definition_qs.filter(version=run.definition_version)
            definition = definition_qs.order_by("-created_at").first()
            doc = (definition.definition if definition else None) or {}

            constraints = doc.get("constraints") or []
            if isinstance(constraints, list):
                sla["constraints"] = constraints
                for clause in constraints:
                    text = clause if isinstance(clause, str) else str(clause)
                    if any(
                        keyword in text.lower()
                        for keyword in ("sla", "within", "response", "deadline", "turnaround")
                    ):
                        sla.setdefault("clauses", []).append(clause)

            policies = doc.get("policies") or []
            exceptions = doc.get("exceptions") or []
            if isinstance(policies, (list, tuple)):
                applicable_sop_clause.extend(policies)
            if isinstance(exceptions, (list, tuple)):
                applicable_sop_clause.extend(exceptions)
            if isinstance(constraints, (list, tuple)):
                applicable_sop_clause.extend(constraints)

            return {
                "run_id": run.id,
                "process_id": run.definition_id,
                "process_version": run.definition_version,
                "run_state": run.run_state,
                "status": run.status,
                "created_at": iso(run.created_at),
                "updated_at": iso(run.updated_at),
                "kill_switched_at": iso(run.kill_switched_at) if run.kill_switched_at else None,
                "current_activity": current_activity,
                "blocker": blocker,
                "sla": sla,
                "applicable_sop_clause": applicable_sop_clause,
                "event_ids": event_ids,
                "operation_ids": operation_ids,
            }

        async def _read_effect(command=None) -> dict:
            return await sync_to_async(_gather_case, thread_sensitive=True)()

        command = Command(
            principal=uid or None,
            scope=Scope(user_identifier=uid),
            tool="inspect_case",
            action="inspect",
            params={"run_id": run_id},
            objects=[run_id],
            requires_confirmation=False,
            autonomy="auto",
            instance_id=instance_id,
            host_user_id=effective_host_user_id,
        )
        boundary = get_command_boundary(
            self.db,
            executor=_read_effect,
            tool_catalog={"inspect_case": True},
        )
        outcome = await boundary.execute(command)
        if outcome.status in ("executed", "confirmed"):
            result = outcome.result
            return result if isinstance(result, dict) else {"result": result}
        return {"error": outcome.error or outcome.reason or "action refused"}

    async def invoke_skill_via_boundary(
        self,
        *,
        skill_name: str = "",
        process_ref: str = "",
        args: dict | None = None,
        explanation: str = "",
        conversation_id: str = "",
        instance_id: str = "",
        host_user_id: str | None = None,
        author_user_id: str | None = None,
        allowed_tools: list[str] | None = None,
    ) -> dict:
        """Route an executable-skill invocation through the command boundary.

        The skill body's ``process_ref`` (``process_id`` or ``process_id@version``)
        is resolved to a governed process definition, its status is gated
        (active/review only), and a run is created (or resumed) as the boundary's
        executor closure — so the PDP, consent, and grant stages all run for the
        ``invoke_skill`` effect before the run is touched. Fail-closed at every
        step: unknown refs, non-invokable statuses, kill-switched processes, and
        a missing host user all refuse without executing any skill body.
        """
        from asgiref.sync import sync_to_async

        from ai.command_boundary import Command
        from ai.command_boundary_factory import get_command_boundary
        from ai.models.core import Run
        from ai.models.process import STATUS_ACTIVE, STATUS_REVIEW
        from ai.plans_service import PlansService, STATUS_APPROVED, STATUS_PAUSED
        from ai.protocol import Scope
        from ai.registry_service import (
            ProcessRegistry,
            RegistryError,
            RegistryNotFoundError,
        )

        uid = str(host_user_id) if host_user_id else (instance_id or "")
        principal = str(author_user_id) if author_user_id else uid
        registry = ProcessRegistry()

        def _refused(error: str) -> dict:
            return {
                "status": "refused",
                "run_id": None,
                "process_id": None,
                "process_version": None,
                "boundary_outcome": None,
                "pdp_decision": None,
                "error": error,
            }

        # ── Resolve the referenced process (fail-closed on unknown ref) ──
        try:
            definition = await sync_to_async(
                registry.resolve, thread_sensitive=True
            )(process_ref)
        except RegistryNotFoundError:
            return _refused(f"No process definition found for {process_ref!r}.")
        except RegistryError as exc:
            return _refused(str(exc))

        process_id = definition.process_id
        process_version = definition.version or ""

        # ── Status gate: only active/review may be invoked ───────────────
        if definition.status not in (STATUS_ACTIVE, STATUS_REVIEW):
            return _refused(
                f"Process {process_id!r} is {definition.status!r}; only active "
                "or review processes may be invoked."
            )
        if (definition.definition or {}).get("kill_switch"):
            return _refused(f"Process {process_id!r} is kill-switched.")

        steps = (definition.definition or {}).get("steps", []) or []
        first_step = steps[0] if steps and isinstance(steps[0], dict) else {}
        capability_id = str(first_step.get("capability", "") or "")
        step_id = first_step.get("id", "")

        # ── Effective autonomy (definition default + per-org overrides) ──
        autonomy = first_step.get("autonomy") or "human_only"
        try:
            effective = await sync_to_async(
                registry.get_autonomy, thread_sensitive=True
            )(process_id)
            entry = (effective.get("steps") or {}).get(step_id) or {}
            autonomy = entry.get("default") or autonomy
        except Exception:  # noqa: BLE001 — fall back to the definition default
            pass

        contract = await sync_to_async(
            _capability_contract, thread_sensitive=True
        )(capability_id)
        step_requires_grant = bool(
            (first_step.get("approval_requirements") or {}).get("requires_grant")
        ) or bool(first_step.get("requires_grant"))
        requires_grant = step_requires_grant or contract["requires_grant"]
        capability_version = contract["version"]

        # ── Effect closure: create (or resume) a governed run ────────────
        async def _run_effect(command: Command) -> dict:
            from accounts.models import User

            if not uid:
                return {"status": "refused", "error": "No host user for run creation."}
            try:
                user = await sync_to_async(
                    User.objects.get, thread_sensitive=True
                )(pk=uid)
            except Exception as exc:  # noqa: BLE001 — fail closed
                return {"status": "refused", "error": f"Host user {uid!r} not found."}

            service = PlansService()

            _existing = sync_to_async(
                lambda: list(
                    Run.objects.filter(
                        host_user_id=uid,
                        definition_id=process_id,
                        status__in=[STATUS_APPROVED, STATUS_PAUSED],
                    ).order_by("-created_at")[:1]
                ),
                thread_sensitive=True,
            )
            existing = await _existing()
            if existing:
                plan_id = existing[0].id
                _resume = sync_to_async(
                    service.resume_workflow, thread_sensitive=True
                )
                await _resume(user, plan_id)
                return {
                    "status": "resumed",
                    "run_id": plan_id,
                    "process_id": process_id,
                    "process_version": process_version,
                }

            brief = f"Invoke skill {skill_name!r} for governed process {process_id}."
            _create = sync_to_async(service.create_plan, thread_sensitive=True)
            plan = await _create(user, brief, conversation_id or "")
            plan_id = plan.get("id") if isinstance(plan, dict) else None
            if not plan_id:
                return {"status": "refused", "error": "Plan creation returned no plan id."}

            def _pin() -> None:
                run = Run.objects.get(id=plan_id)
                run.pin_definition(process_id, process_version)
                run.save(update_fields=["definition_id", "definition_version"])

            await sync_to_async(_pin, thread_sensitive=True)()
            return {
                "status": "created",
                "run_id": plan_id,
                "process_id": process_id,
                "process_version": process_version,
            }

        # ── Authorized tools (P4-04) ──────────────────────────────────────
        # Resolve the invoking principal's capabilities and derive the subset
        # of TOOL_CAPABILITY_MAP tools they are authorized to use.  Fail-closed:
        # any failure to resolve the user yields an empty authorized set (never
        # "all tools").  This feeds the PDP's ``deny-unauthorized-skill-tool``
        # mandatory policy at stage 6.
        from accounts.capabilities import get_user_capabilities
        from ai.pdp import authorized_tool_names

        def _resolve_authorized_tools() -> frozenset[str]:
            if not uid:
                return frozenset()
            try:
                from accounts.models import User

                user = User.objects.get(pk=uid)
            except Exception:  # noqa: BLE001 — fail-closed on any resolution error
                return frozenset()
            return authorized_tool_names(get_user_capabilities(user))

        authorized = await sync_to_async(
            _resolve_authorized_tools, thread_sensitive=True
        )()
        process_state = {
            "skill_allowed_tools": sorted(set(allowed_tools or [])),
            "authorized_tools": sorted(authorized),
        }

        command = Command(
            principal=principal or None,
            scope=Scope(user_identifier=uid),
            tool="invoke_skill",
            action="invoke_skill",
            params={
                "skill_name": skill_name,
                "process_ref": process_ref,
                "args": args,
                "author_user_id": author_user_id,
                "explanation": explanation,
                "conversation_id": conversation_id,
            },
            objects=[process_id],
            requires_confirmation=False,
            requires_grant=bool(requires_grant),
            capability=capability_id,
            process_version=process_version,
            capability_version=capability_version,
            autonomy=_map_autonomy(autonomy),
            process_state=process_state,
            instance_id=instance_id,
            host_user_id=host_user_id,
            idempotency_key=f"invoke_skill:{process_ref}:{principal}",
        )

        boundary = get_command_boundary(
            self.db,
            executor=_run_effect,
            tool_catalog={"invoke_skill": True},
        )
        outcome = await boundary.execute(command)

        pdp_decision = outcome.decision.value if outcome.decision else None
        if outcome.status in ("executed", "confirmed"):
            result = outcome.result if isinstance(outcome.result, dict) else {}
            return {
                "status": outcome.status,
                "run_id": result.get("run_id"),
                "process_id": process_id,
                "process_version": process_version,
                "boundary_outcome": outcome.status,
                "pdp_decision": pdp_decision,
                "error": None,
            }
        return {
            "status": outcome.status,
            "run_id": None,
            "process_id": process_id,
            "process_version": process_version,
            "boundary_outcome": outcome.status,
            "pdp_decision": pdp_decision,
            "error": outcome.error or outcome.reason or "action refused",
        }

    async def execute_worker_tools_via_boundary(
        self,
        *,
        tool_calls: list[dict],
        instance_id: str = "",
        conversation_id: str = "",
        run_id: str | None = None,
        host_user_id: str | None = None,
        knowledge_store=None,
    ) -> list[dict]:
        """Route a worker's fan-out tool calls through the command boundary.

        Each worker tool call becomes one fail-closed ``Command``: read-only
        tools are declared ``action="read"`` (PDP → ALLOW) so stage-7 consent
        is skipped and the boundary executor closure runs the tool; mutations
        are declared ``action="execute"`` with ``autonomy="human_only"``
        (PDP → ASK) so stage-7 consent refuses them without ever running the
        closure. Workers are read-only (ADR-001).
        """
        from ai.command_boundary import Command
        from ai.command_boundary_factory import get_command_boundary, _STATIC_TOOL_NAMES
        from ai.protocol import Scope
        from ai.engine.cognition.turn.execute import _execute_single_tool

        uid = str(host_user_id) if host_user_id else (instance_id or "")

        results: list[dict] = []
        for tc in tool_calls:
            name = tc.get("function", {}).get("name", "unknown")
            raw_args = tc.get("function", {}).get("arguments", "{}")
            if isinstance(raw_args, str):
                try:
                    args = json.loads(raw_args)
                except (json.JSONDecodeError, TypeError):
                    args = {}
            elif isinstance(raw_args, dict):
                args = raw_args
            else:
                args = {}

            action = "execute" if _worker_is_mutation(name, args) else "read"

            command = Command(
                principal=uid or None,
                scope=Scope(user_identifier=uid),
                tool=name,
                action=action,
                params=args,
                objects=[name],
                requires_confirmation=False,
                autonomy="human_only",
                instance_id=instance_id,
                run_id=run_id,
                host_user_id=host_user_id,
            )

            async def effect(command: Command) -> dict:
                return await _execute_single_tool(
                    tc,
                    self,
                    hook_pipeline=None,
                    hook_ctx_defaults={
                        "instance_id": instance_id,
                        "conversation_id": conversation_id,
                        "run_id": run_id,
                        "host_user_id": host_user_id,
                    },
                    knowledge_store=knowledge_store,
                )

            boundary = get_command_boundary(
                self.db,
                executor=effect,
                tool_catalog={n: True for n in _STATIC_TOOL_NAMES},
            )
            outcome = await boundary.execute(command)

            if outcome.status in ("executed", "confirmed"):
                result = outcome.result
                if isinstance(result, dict) and "tool_name" in result:
                    results.append(result)
                else:
                    results.append({
                        "tool_name": name,
                        "tool_call_id": tc.get("id", ""),
                        "result": result,
                        "error": None,
                        "guardrail_flags": [],
                    })
            else:
                results.append({
                    "tool_name": name,
                    "tool_call_id": tc.get("id", ""),
                    "result": None,
                    "error": (
                        "Worker tool call refused by boundary: "
                        f"{outcome.error or outcome.reason or 'refused'}"
                    ),
                    "guardrail_flags": ["worker_tool_blocked", f"blocked:{name}"],
                })

        return results

    async def execute_delivery_via_boundary(
        self,
        *,
        effect,
        instance_id: str = "",
        host_user_id: str | None = None,
        delivery_type: str = "proactive_delivery",
    ) -> dict:
        """Route a proactive-delivery host effect through the fail-closed
        command boundary (P2-06e).

        ``effect`` is the engine's host-effect closure that performs the actual
        delivery (WebSocket/event-bus push + notification persistence); this
        method wraps it in a :class:`~ai.command_boundary.Command` so every
        delivery passes the 14-stage boundary and the PDP persists a
        :class:`~ai.models.pdp.PolicyDecisionRow` per delivery.
        """
        from ai.command_boundary import Command
        from ai.command_boundary_factory import get_command_boundary
        from ai.protocol import Scope

        uid = str(host_user_id) if host_user_id else (instance_id or "")
        command = Command(
            principal=uid or None,
            scope=Scope(user_identifier=uid),
            tool="proactive_delivery",
            action="deliver",
            params={"delivery_type": delivery_type},
            objects=[instance_id or "", delivery_type],
            requires_confirmation=False,
            autonomy="auto",
            instance_id=instance_id,
            host_user_id=host_user_id,
        )
        boundary = get_command_boundary(
            self.db,
            executor=effect,
            tool_catalog={"proactive_delivery": True},
        )
        outcome = await boundary.execute(command)
        return {
            "status": outcome.status,
            "result": outcome.result,
            "error": outcome.error,
            "reason": outcome.reason,
        }

    async def execute_step_via_boundary(
        self,
        *,
        effect,
        tool_name: str,
        is_mutation: bool,
        confirmation_token: str | None = None,
        instance_id: str = "",
        host_user_id: str | None = None,
        conversation_id: str = "",
    ) -> dict:
        """Route a ReAct plan step through the fail-closed command boundary.

        ``effect`` is the step's actual tool-effect closure (or ``None`` when
        the caller only wants the boundary's consent verdict for a no-token
        mutation — in that case a no-op closure is supplied so stage 11 has
        something to run if consent ever passes).  The method builds a
        :class:`~ai.command_boundary.Command` and maps the
        :class:`~ai.command_boundary.Outcome` to a plain dict the engine can
        read without importing boundary types.

        Mutations are declared with a mutating action and
        ``autonomy="human_only"`` so the PDP returns ``ASK`` at stage 6 and
        stage 7 (consent) refuses a no-token mutation before the effect
        closure ever runs; a supplied ``confirmation_token`` satisfies stage 7
        and the effect executes.
        """
        from ai.command_boundary import Command
        from ai.command_boundary_factory import get_command_boundary
        from ai.protocol import Scope

        uid = str(host_user_id) if host_user_id else (instance_id or "")
        action = "execute" if is_mutation else "read"

        command = Command(
            principal=uid or None,
            scope=Scope(user_identifier=uid),
            tool=tool_name or "plan_step",
            action=action,
            params={"conversation_id": conversation_id},
            objects=[tool_name or "plan_step"],
            requires_confirmation=bool(is_mutation),
            confirmation_token=confirmation_token,
            autonomy="human_only" if is_mutation else "auto",
            instance_id=instance_id,
            host_user_id=host_user_id,
        )

        async def _noop(command=None) -> dict:
            return {}

        boundary = get_command_boundary(
            self.db,
            executor=effect if effect is not None else _noop,
            tool_catalog={tool_name or "plan_step": True},
        )
        outcome = await boundary.execute(command)

        if outcome.status in ("executed", "confirmed"):
            return {
                "status": outcome.status,
                "result": outcome.result,
                "requires_confirmation": False,
            }
        if (
            outcome.status == "refused"
            and outcome.error
            and "confirmation" in outcome.error.lower()
        ):
            return {
                "status": "refused",
                "error": outcome.error,
                "requires_confirmation": True,
            }
        return {
            "status": outcome.status,
            "error": outcome.error or outcome.reason,
            "requires_confirmation": False,
        }

    # ── In-process transport ────────────────────────────────────────────

    async def _call_api(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        body: dict | None = None,
    ) -> dict:
        """Execute a host API call in-process (no HTTP, no JWT).

        Both GET (read-only, no confirmation) and POST (mutation, staged via
        ``create_pending_execution``) dispatch through this method so the LLM's
        ``call_host_api`` tool sees a uniform transport.
        """
        # Memory writes (learn_fact / forget_fact) are not host HTTP endpoints
        # — the engine stages them with method="MEMORY" / endpoint="long_term/*"
        # and the confirmed proposal is written straight to LongTermMemory.
        if (method or "").upper() == "MEMORY":
            return await self._memory_in_process(
                method=method.upper(), params=params, body=body or {}
            )

        key = _canonical_endpoint(endpoint)

        # People & Payroll namespace — routed by resource/pk/action so the
        # path-parameter detail/action endpoints (e.g. employees/5, payroll-runs/5/compute)
        # resolve without a static per-route key.
        if key == "carbon-api/people" or key.startswith("carbon-api/people/"):
            merged = dict(params or {})
            if "?" in (endpoint or ""):
                from urllib.parse import parse_qs, urlsplit

                for qk, qv in parse_qs(urlsplit(endpoint).query).items():
                    merged.setdefault(qk, qv[0] if len(qv) == 1 else qv)
            return await self._people_in_process(
                method=method.upper(), params=merged, body=body or {}, endpoint=key
            )

        handler_name = _IN_PROCESS_ENDPOINTS.get(key)
        if handler_name:
            handler = getattr(self, f"_{handler_name}_in_process", None)
            if handler is not None:
                # Merge query-string params (e.g. the `?module_id={id}` baked
                # into a catalog path) into the explicit params dict so
                # in-process handlers see a uniform view.
                merged = dict(params or {})
                if "?" in (endpoint or ""):
                    from urllib.parse import parse_qs, urlsplit

                    for qk, qv in parse_qs(urlsplit(endpoint).query).items():
                        merged.setdefault(qk, qv[0] if len(qv) == 1 else qv)
                return await handler(
                    method=method.upper(), params=merged, body=body or {}
                )
        raise ToolExecutionError(
            f"Host API endpoint {method} {endpoint} is not available for "
            "in-process execution from the AI workspace."
        )

    async def _memory_in_process(
        self, method: str = "MEMORY", params: dict | None = None, body: dict | None = None
    ) -> dict:
        """MEMORY ``long_term/*`` executed directly in-process (learn / forget).

        Backs the ``learn_fact`` / ``forget_fact`` tools: a *confirmed* proposal
        writes (or archives) a durable ``MemoryLongTerm`` fact via the engine's
        ``LongTermMemory`` — no HTTP, no separate memory service.  The tool layer
        already staged this as a confirmation card; this handler is the confirmed
        write.  Ownership is inherited from ``self.host_user_id`` so private
        facts are scoped to the confirming user (RULE_21 / P0-2).
        """
        from ai.engine.memory.long_term import LongTermMemory

        body = body or {}
        operation = body.get("operation", "learn")
        # Scope memory facts to the active instance partition. The engine stamps
        # the instance_id on the body, but fall back to the executor's resolved
        # instance config so a Nibras fact can never land in the Carbon memory
        # partition (and vice-versa).
        instance_id = (
            body.get("instance_id")
            or (self.instance_config or {}).get("instance_id")
            or "carbon"
        )
        ltm = LongTermMemory(self.db)

        if operation == "forget":
            memory_id = (body.get("memory_id") or "").strip()
            archived = bool(memory_id) and await ltm.archive_fact(memory_id)
            return {
                "status_code": 200 if archived else 404,
                "data": {
                    "id": memory_id,
                    "name": "forgotten fact",
                    "archived": archived,
                },
                "kind": "memory",
                "operation": "forget",
            }

        fact = (body.get("fact") or "").strip()
        if not fact:
            raise ToolExecutionError("Cannot remember an empty fact.")

        fact_id = await ltm.store_fact(
            instance_id=instance_id,
            category=body.get("category", "observation"),
            content=fact,
            source=body.get("source") or "learn_fact",
            confidence=float(body.get("confidence", 1.0)),
            host_user_id=self.host_user_id,
            visibility="private",
        )
        return {
            "status_code": 201,
            "data": {
                "id": fact_id,
                "name": "remembered fact",
                "fact": fact,
                "category": body.get("category", "observation"),
            },
            "kind": "memory",
            "operation": "learn",
        }

    async def _dq_rules_in_process(
        self, method: str = "POST", params: dict | None = None, body: dict | None = None
    ) -> dict:
        """GET/POST /carbon-api/dq/rules/ executed directly in-process.

        - ``POST`` creates a rule via ``DQRuleSerializer`` and returns the same
          ``{"status_code": 201, "data": {...}}`` shape the HTTP transport would.
        - ``GET`` lists rules (used by ``list_dq_rules`` so the LLM can reuse an
          existing rule instead of duplicating it).
        """
        from asgiref.sync import sync_to_async
        from django.contrib.auth import get_user_model

        if method == "GET":
            return await self._list_dq_rules_in_process(params or {})

        user = await self._resolve_user()
        if user is None:
            raise ToolExecutionError(
                "No authenticated user for rule creation — please refresh the page."
            )

        def _create() -> dict:
            from dq.serializers import DQRuleSerializer

            serializer = DQRuleSerializer(data=body)
            if not serializer.is_valid():
                raise ToolExecutionError(
                    "Rule validation failed: "
                    + json.dumps(serializer.errors, default=str)[:1200]
                )
            rule = serializer.save(created_by=user)
            return {
                "id": rule.pk,
                "name": rule.name,
                "rule_type": rule.rule_type,
                "rule_level": rule.rule_level,
                "severity": rule.severity,
                "dimension": rule.dimension,
                "is_active": rule.is_active,
            }

        try:
            data = await sync_to_async(_create, thread_sensitive=True)()
        except ToolExecutionError:
            raise
        except Exception as exc:  # noqa: BLE001 - fail-visible
            logger.exception("In-process DQ rule creation failed")
            raise ToolExecutionError(f"Rule creation failed: {exc}") from exc
        return {"status_code": 201, "data": data}

    async def _list_dq_rules_in_process(self, params: dict) -> dict:
        """GET /carbon-api/dq/rules/ — list non-archived rules visible to the user."""
        from asgiref.sync import sync_to_async

        user = await self._resolve_user()
        if user is None:
            raise ToolExecutionError(
                "No authenticated user for rule listing — please refresh the page."
            )

        def _list() -> list[dict]:
            from dq.models import DQRule
            from dq.views import _get_user_org_units

            qs = DQRule.objects.filter(archived=False)
            if not (user.is_superuser or user.is_staff):
                org_units = list(_get_user_org_units(user))
                if not org_units:
                    return []
                qs = qs.filter(
                    field_assignments__data_table__module__org_unit_id__in=org_units
                ).distinct()
            search = params.get("search")
            if search:
                qs = qs.filter(name__icontains=search)
            return [
                {
                    "id": r.pk,
                    "name": r.name,
                    "rule_type": r.rule_type,
                    "rule_level": r.rule_level,
                    "severity": r.severity,
                    "dimension": r.dimension,
                    "is_active": r.is_active,
                }
                for r in qs[:200]
            ]

        try:
            data = await sync_to_async(_list, thread_sensitive=True)()
        except ToolExecutionError:
            raise
        except Exception as exc:  # noqa: BLE001 - fail-visible
            logger.exception("In-process DQ rule listing failed")
            raise ToolExecutionError(f"Rule listing failed: {exc}") from exc
        return {"status_code": 200, "data": {"results": data}}

    async def _tables_in_process(
        self, method: str = "GET", params: dict | None = None, body: dict | None = None
    ) -> dict:
        """GET/POST /carbon-api/dataschema/tables/ executed directly in-process.

        - ``GET`` lists tables (optionally filtered by ``module_id``) — backs
          ``get_data_product_details`` / ``list_data_tables``.
        - ``POST`` creates a table with optional nested ``fields`` (schema
          change) and mirrors ``DataTableViewSet.perform_create`` logging.
        """
        if method == "GET":
            return await self._list_tables_in_process(params or {})
        return await self._create_table_in_process(body or {})

    async def _list_tables_in_process(self, params: dict) -> dict:
        """GET /carbon-api/dataschema/tables/ — tables visible to the user."""
        from asgiref.sync import sync_to_async

        user = await self._resolve_user()
        if user is None:
            raise ToolExecutionError(
                "No authenticated user for table listing — please refresh the page."
            )

        def _list() -> list[dict]:
            from dataschema.models import DataTable
            from accounts.rbac_utils import get_visible_module_ids

            qs = DataTable.objects.select_related("module").filter(is_archived=False)
            visible = get_visible_module_ids(user)
            if visible is not None:
                qs = qs.filter(module_id__in=visible)
            module_id = params.get("module_id")
            if module_id:
                qs = qs.filter(module_id=module_id)
            return [
                {
                    "id": t.pk,
                    "title": t.title,
                    "name": t.name,
                    "module": t.module_id,
                    "module_name": getattr(t.module, "name", None),
                    "description": t.description,
                    "is_locked": t.is_locked,
                }
                for t in qs[:200]
            ]

        try:
            data = await sync_to_async(_list, thread_sensitive=True)()
        except ToolExecutionError:
            raise
        except Exception as exc:  # noqa: BLE001 - fail-visible
            logger.exception("In-process data table listing failed")
            raise ToolExecutionError(f"Table listing failed: {exc}") from exc
        return {"status_code": 200, "data": {"results": data}}

    async def _table_detail_in_process(
        self, method: str = "GET", params: dict | None = None, body: dict | None = None
    ) -> dict:
        """GET /carbon-api/dataschema/tables/detail/?id=N — read-only detail.

        Returns one table with its active fields (id/name/label). Added for
        the Flight Director acceptance re-query (Phase 25-C, spec §3.5: the
        ``table_fields`` criterion asserts the EXACT field set vs the brief).
        Read-only — never stages or mutates; visibility-scoped exactly like
        ``_list_tables_in_process`` (CBAC via ``get_visible_module_ids``).
        """
        from asgiref.sync import sync_to_async

        user = await self._resolve_user()
        if user is None:
            raise ToolExecutionError(
                "No authenticated user for table detail — please refresh the page."
            )

        table_id = (params or {}).get("id") or (params or {}).get("table_id")
        if not table_id:
            return {
                "status_code": 400,
                "data": {"detail": "table id is required"},
            }

        def _detail() -> dict | None:
            from dataschema.models import DataTable
            from accounts.rbac_utils import get_visible_module_ids

            try:
                table = DataTable.objects.select_related("module").get(
                    pk=table_id, is_archived=False
                )
            except (DataTable.DoesNotExist, ValueError, TypeError):
                return None
            visible = get_visible_module_ids(user)
            if visible is not None and table.module_id not in visible:
                return None
            fields = [
                {"id": f.pk, "name": f.name, "label": f.label}
                for f in table.fields.filter(is_active=True, is_archived=False)
            ]
            return {
                "id": table.pk,
                "title": table.title,
                "name": table.name,
                "module": table.module_id,
                "module_name": getattr(table.module, "name", None),
                "description": table.description,
                "is_locked": table.is_locked,
                "fields": fields,
            }

        try:
            data = await sync_to_async(_detail, thread_sensitive=True)()
        except Exception as exc:  # noqa: BLE001 - fail-visible
            logger.exception("In-process table detail lookup failed")
            raise ToolExecutionError(f"Table detail lookup failed: {exc}") from exc
        if data is None:
            return {"status_code": 404, "data": {"detail": "Table not found"}}
        return {"status_code": 200, "data": data}

    async def _create_table_in_process(self, body: dict) -> dict:
        """POST /carbon-api/dataschema/tables/ — create table + optional fields."""
        from asgiref.sync import sync_to_async

        user = await self._resolve_user()
        if user is None:
            raise ToolExecutionError(
                "No authenticated user for table creation — please refresh the page."
            )

        def _create() -> dict:
            from dataschema.models import DataTable
            from dataschema.serializers import DataFieldSerializer, DataTableSerializer
            from dataschema.views import _log_schema_change

            serializer = DataTableSerializer(data=body)
            if not serializer.is_valid():
                raise ToolExecutionError(
                    "Table validation failed: "
                    + json.dumps(serializer.errors, default=str)[:1200]
                )
            table = serializer.save(created_by=user)
            fields = []
            for i, raw in enumerate(body.get("fields") or []):
                field_body = dict(raw)
                field_body.setdefault("data_table", table.pk)
                field_body.setdefault("order", i)
                fser = DataFieldSerializer(data=field_body)
                if not fser.is_valid():
                    raise ToolExecutionError(
                        "Field validation failed: "
                        + json.dumps(fser.errors, default=str)[:1200]
                    )
                field = fser.save(created_by=user)
                fields.append({"id": field.pk, "name": field.name, "label": field.label})
            _log_schema_change(
                user, "add", data_table=table, after=DataTableSerializer(table).data
            )
            return {
                "id": table.pk,
                "title": table.title,
                "name": table.name,
                "module": table.module_id,
                "module_name": getattr(table.module, "name", None),
                "description": table.description,
                "is_locked": table.is_locked,
                "fields": fields,
            }

        try:
            data = await sync_to_async(_create, thread_sensitive=True)()
        except ToolExecutionError:
            raise
        except Exception as exc:  # noqa: BLE001 - fail-visible
            logger.exception("In-process data table creation failed")
            raise ToolExecutionError(f"Table creation failed: {exc}") from exc
        return {"status_code": 201, "data": data}

    async def _rule_assignments_in_process(
        self, method: str = "POST", params: dict | None = None, body: dict | None = None
    ) -> dict:
        """POST /carbon-api/dq/rule-assignments/ — bind rule(s) to a table.

        Accepts either ``{"rule": <id>, "data_table": <id>, "data_field": <id|null>}``
        or ``{"table_id": <id>, "dq_rule_ids": [<ids>]}``.
        """
        from asgiref.sync import sync_to_async

        if method != "POST":
            raise ToolExecutionError(
                "Rule assignments only support POST via call_host_api."
            )
        user = await self._resolve_user()
        if user is None:
            raise ToolExecutionError(
                "No authenticated user for rule binding — please refresh the page."
            )

        def _bind() -> dict:
            from dq.models import RuleFieldAssignment

            table_id = body.get("data_table") or body.get("table_id")
            rule_ids = body.get("dq_rule_ids")
            if not rule_ids and body.get("rule"):
                rule_ids = [body.get("rule")]
            if not table_id or not rule_ids:
                raise ToolExecutionError(
                    "Rule binding requires 'data_table'/'table_id' and "
                    "'rule'/'dq_rule_ids'."
                )
            data_field = body.get("data_field")
            created = []
            for rid in rule_ids:
                # Guard against the unique_rule_table constraint when the LLM
                # retries or reuses an existing binding.
                if RuleFieldAssignment.objects.filter(
                    rule_id=rid, data_table_id=table_id, data_field_id=data_field
                ).exists():
                    continue
                assn = RuleFieldAssignment.objects.create(
                    rule_id=rid, data_table_id=table_id, data_field_id=data_field
                )
                created.append({"id": assn.pk, "rule": assn.rule_id, "data_table": assn.data_table_id})
            return {"bindings": created, "count": len(created)}

        try:
            data = await sync_to_async(_bind, thread_sensitive=True)()
        except ToolExecutionError:
            raise
        except Exception as exc:  # noqa: BLE001 - fail-visible
            logger.exception("In-process rule binding failed")
            raise ToolExecutionError(f"Rule binding failed: {exc}") from exc
        return {"status_code": 201, "data": data}

    # ── Carbon emissions read-only grounding (Tier 1, RULE_21) ──────────

    async def _emission_factors_in_process(
        self, method: str = "GET", params: dict | None = None, body: dict | None = None
    ) -> dict:
        """GET /carbon-api/carbon/factors/ — GLOBAL active emission factors (RULE_12)."""
        if method != "GET":
            return {"status_code": 405, "data": {"detail": "Method not allowed"}}
        from asgiref.sync import sync_to_async

        user = await self._resolve_user()
        if user is None:
            return {"status_code": 401, "data": {"detail": "Authentication required"}}

        def _list() -> list[dict]:
            from emissions.models import EmissionFactor

            return [
                {
                    "id": f.pk,
                    "name": f.name,
                    "code": f.code,
                    "category": f.category,
                    "subcategory": f.subcategory,
                    "scope": f.scope,
                    "factor_value": float(f.factor_value),
                    "factor_unit": f.factor_unit,
                    "activity_unit": f.activity_unit,
                    "country": f.country,
                    "source": f.source,
                    "tags": f.tags,
                }
                for f in EmissionFactor.objects.filter(is_active=True)[:200]
            ]

        try:
            data = await sync_to_async(_list, thread_sensitive=True)()
        except Exception as exc:  # noqa: BLE001 - fail-visible
            logger.exception("In-process emission factor listing failed")
            raise ToolExecutionError(f"Emission factor listing failed: {exc}") from exc
        return {"status_code": 200, "data": {"results": data}}

    async def _gwp_gases_in_process(
        self, method: str = "GET", params: dict | None = None, body: dict | None = None
    ) -> dict:
        """GET /carbon-api/carbon/gwp/ — GLOBAL global warming potentials (RULE_12)."""
        if method != "GET":
            return {"status_code": 405, "data": {"detail": "Method not allowed"}}
        from asgiref.sync import sync_to_async

        user = await self._resolve_user()
        if user is None:
            return {"status_code": 401, "data": {"detail": "Authentication required"}}

        def _list() -> list[dict]:
            from emissions.models import GWP

            return [
                {
                    "id": g.pk,
                    "gas_name": g.gas_name,
                    "gas_formula": g.gas_formula,
                    "gwp_ar5_100yr": float(g.gwp_ar5_100yr) if g.gwp_ar5_100yr is not None else None,
                    "gwp_ar6_100yr": float(g.gwp_ar6_100yr) if g.gwp_ar6_100yr is not None else None,
                    "gwp_ar5_20yr": float(g.gwp_ar5_20yr) if g.gwp_ar5_20yr is not None else None,
                    "gwp_ar6_20yr": float(g.gwp_ar6_20yr) if g.gwp_ar6_20yr is not None else None,
                }
                for g in GWP.objects.all()[:200]
            ]

        try:
            data = await sync_to_async(_list, thread_sensitive=True)()
        except Exception as exc:  # noqa: BLE001 - fail-visible
            logger.exception("In-process GWP listing failed")
            raise ToolExecutionError(f"GWP listing failed: {exc}") from exc
        return {"status_code": 200, "data": {"results": data}}

    async def _reporting_periods_in_process(
        self, method: str = "GET", params: dict | None = None, body: dict | None = None
    ) -> dict:
        """GET /carbon-api/carbon/periods/ — GLOBAL reporting periods (RULE_12)."""
        if method != "GET":
            return {"status_code": 405, "data": {"detail": "Method not allowed"}}
        from asgiref.sync import sync_to_async

        user = await self._resolve_user()
        if user is None:
            return {"status_code": 401, "data": {"detail": "Authentication required"}}

        def _list() -> list[dict]:
            from emissions.models import ReportingPeriod

            return [
                {
                    "id": p.pk,
                    "name": p.name,
                    "start_date": p.start_date.isoformat(),
                    "end_date": p.end_date.isoformat(),
                    "status": p.status,
                    "is_baseline": p.is_baseline,
                }
                for p in ReportingPeriod.objects.order_by('-start_date')[:50]
            ]

        try:
            data = await sync_to_async(_list, thread_sensitive=True)()
        except Exception as exc:  # noqa: BLE001 - fail-visible
            logger.exception("In-process reporting period listing failed")
            raise ToolExecutionError(f"Reporting period listing failed: {exc}") from exc
        return {"status_code": 200, "data": {"results": data}}

    async def _calculation_summary_in_process(
        self, method: str = "GET", params: dict | None = None, body: dict | None = None
    ) -> dict:
        """GET /carbon-api/carbon/calculations/summary/ — ORG-SCOPED summary."""
        if method != "GET":
            return {"status_code": 405, "data": {"detail": "Method not allowed"}}
        from asgiref.sync import sync_to_async

        user = await self._resolve_user()
        if user is None:
            return {"status_code": 401, "data": {"detail": "Authentication required"}}

        period_id = (params or {}).get('reporting_period_id')

        def _summary() -> dict:
            from emissions.services import CalculationSummaryService

            return CalculationSummaryService.get_summary(user, period_id)

        try:
            summary = await sync_to_async(_summary, thread_sensitive=True)()
        except Exception as exc:  # noqa: BLE001 - fail-visible
            logger.exception("In-process calculation summary failed")
            raise ToolExecutionError(f"Calculation summary failed: {exc}") from exc
        # Coerce Decimal/date types so the payload is always JSON-safe.
        coerced = json.loads(json.dumps(summary, default=_json_coerce))
        # Steer the envelope synthesis to bar charts: scope/module are magnitude
        # comparisons per category, not balanced proportions — bars read better.
        coerced["suggested_chart_type"] = "bar"
        return {"status_code": 200, "data": coerced}

    async def _chairman_overview_in_process(
        self, method: str = "GET", params: dict | None = None, body: dict | None = None
    ) -> dict:
        """GET /carbon-api/carbon/chairman/ — ORG-SCOPED chairman overview."""
        if method != "GET":
            return {"status_code": 405, "data": {"detail": "Method not allowed"}}
        from asgiref.sync import sync_to_async

        user = await self._resolve_user()
        if user is None:
            return {"status_code": 401, "data": {"detail": "Authentication required"}}

        period_id = (params or {}).get('reporting_period_id')

        def _overview() -> dict:
            from emissions.services import ChairmanService

            return ChairmanService.get_chairman_data(user, period_id)

        try:
            payload = await sync_to_async(_overview, thread_sensitive=True)()
        except Exception as exc:  # noqa: BLE001 - fail-visible
            logger.exception("In-process chairman overview failed")
            raise ToolExecutionError(f"Chairman overview failed: {exc}") from exc
        # Coerce Decimal/date types so the payload is always JSON-safe.
        return {"status_code": 200, "data": json.loads(json.dumps(payload, default=_json_coerce))}

    async def _people_analytics_in_process(
        self,
        method: str = "GET",
        params: dict | None = None,
        body: dict | None = None,
    ) -> dict:
        """GET /carbon-api/people/analytics/ — server-side aggregation.

        Dispatches to :func:`_people_analytics` so the LLM never has to count
        rows itself.  Requires ``people:view`` capability (same gate as list).
        """
        from asgiref.sync import sync_to_async

        if (method or "GET").upper() != "GET":
            return {"status_code": 405, "data": {"detail": "Method not allowed"}}

        user = await self._resolve_user()
        if user is None:
            return {"status_code": 401, "data": {"detail": "Authentication required"}}

        # Run capability check + aggregation together inside sync_to_async so
        # Django DB access never happens from an async frame.
        def _run() -> dict:
            if not _people_can(user, "people:view"):
                return {"status_code": 403, "data": {"detail": "people:view capability required"}}
            return _people_analytics(user, params or {})

        try:
            return await sync_to_async(_run, thread_sensitive=True)()
        except Exception as exc:  # noqa: BLE001
            logger.exception("In-process people analytics failed")
            raise ToolExecutionError(f"People analytics failed: {exc}") from exc

    async def _people_in_process(
        self,
        method: str = "GET",
        params: dict | None = None,
        body: dict | None = None,
        endpoint: str = "",
    ) -> dict:
        """Execute a People & Payroll endpoint in-process (Nibras grounded reads
        and confirmed writes).

        Read endpoints (GET) run without confirmation; mutations
        (compute/validate/commit/leave create) arrive here only after the user
        confirms the staged ``ToolExecution``. All access is CBAC-gated
        (``people:view`` / ``people:manage``) and org-scoped, mirroring the
        DRF view layer.
        """
        from asgiref.sync import sync_to_async

        user = await self._resolve_user()
        if user is None:
            return {"status_code": 401, "data": {"detail": "Authentication required"}}

        method = (method or "GET").upper()
        resource, pk, action = _people_route(endpoint)

        def _dispatch() -> dict:
            if resource == "me":
                # Self-service: the self-scoping IS the authorization (mirrors
                # IsActiveEmployee). Must NOT require people:view — an ordinary
                # employee holds only my:access, yet may read their own records.
                return _people_me(user, pk, method)
            cap = "people:view" if method in ("GET", "HEAD", "OPTIONS") else "people:manage"
            if not _people_can(user, cap):
                return {
                    "status_code": 403,
                    "unauthorized": True,
                    "data": {
                        "detail": f"{cap} capability required",
                        "message": (
                            "Not authorized to view this HR data for other employees. "
                            f"Required capability: {cap}."
                        ),
                    },
                }
            return _people_execute(user, resource, pk, action, method, params or {}, body or {})

        try:
            return await sync_to_async(_dispatch, thread_sensitive=True)()
        except ToolExecutionError:
            raise
        except Exception as exc:  # noqa: BLE001 - fail-visible
            logger.exception("In-process People API call failed")
            raise ToolExecutionError(f"People API call failed: {exc}") from exc

    async def _resolve_user(self):
        """Resolve the Django user for ``host_user_id`` (or ``None``)."""
        from asgiref.sync import sync_to_async
        from django.contrib.auth import get_user_model

        if not self.host_user_id:
            return None
        User = get_user_model()
        try:
            return await sync_to_async(User.objects.get)(pk=self.host_user_id)
        except User.DoesNotExist:
            return None

    # ── ECF entity fetch seam (ADR-0032) ────────────────────────────────
    # The host provides the ORM fetch so the engine resolver stays domain-free
    # (RULE_20). Sync by design — the engine wraps it in sync_to_async.

    def entity_fetch(self, model_path: str, filters: dict, fields: list, limit: int) -> list[dict]:
        """Complete-scan ORM fetch for the ECF resolver, org-scoped (RULE_12).

        LeaveRecord (and other employee-linked models) use
        ``employee__org_unit_id__in`` — not bare ``org_unit_id__in``.
        """
        import importlib

        mod_name, cls_name = model_path.rsplit(".", 1)
        model_cls = getattr(importlib.import_module(mod_name), cls_name)
        qs = model_cls.objects.all()

        # Apply People org-unit scoping for the acting user (RULE_12).
        org_lookup = _people_entity_scope_lookup(model_path, getattr(self, "instance_config", None))
        if self.host_user_id and org_lookup:
            from django.contrib.auth import get_user_model
            try:
                user = get_user_model().objects.get(pk=self.host_user_id)
                qs = _people_scope(user, qs, org_lookup)
            except Exception:  # noqa: BLE001 — scoping best-effort; never crash a lookup
                pass

        if filters:
            qs = qs.filter(**_normalize_people_entity_filters(filters))
        if limit and limit > 0:
            qs = qs[:limit]

        # Prefer requested fields (search/identifiers/label_map); empty → all.
        # Use model field names so FKs land as ``employee`` not only ``employee_id``.
        select: list[str] = []
        if fields:
            concrete = {f.name for f in model_cls._meta.concrete_fields}
            for name in fields:
                if name in concrete and name not in select:
                    select.append(name)
        if select:
            rows = list(qs.values(*select))
        else:
            rows = list(qs.values())
        return [_normalize_entity_row(r, model_cls) for r in rows]

    def entity_count(self, model_path: str, filters: dict) -> int:
        """Scoped ORM count for ECF canonical metrics (ADR-0032 / ECF-6).

        Same org-scoping as :meth:`entity_fetch` (incl. LeaveRecord
        ``employee__org_unit_id__in``). Filters come from the descriptor
        ``metrics{}`` block — never invented by the LLM.
        """
        import importlib

        mod_name, cls_name = model_path.rsplit(".", 1)
        model_cls = getattr(importlib.import_module(mod_name), cls_name)
        qs = model_cls.objects.all()

        org_lookup = _people_entity_scope_lookup(model_path, getattr(self, "instance_config", None))
        if self.host_user_id and org_lookup:
            from django.contrib.auth import get_user_model
            try:
                user = get_user_model().objects.get(pk=self.host_user_id)
                qs = _people_scope(user, qs, org_lookup)
            except Exception:  # noqa: BLE001 — scoping best-effort
                pass

        if filters:
            qs = qs.filter(**_normalize_people_entity_filters(filters))
        return qs.count()

    def people_metric_access(self) -> dict:
        """Whether the caller may run People org-scoped aggregates (A10 honesty).

        ESS with ``my:access`` only has empty visible orgs → ``entity_count``
        returns 0, which Chat then charts as "no employees". That is a soft lie.
        Require ``people:view`` (or global admin); never unscoped brand totals.
        """
        from people.permissions import is_global_admin

        if not self.host_user_id:
            return {
                "allowed": False,
                "reason": "authentication_required",
                "message": "Not authorized to view organization workforce metrics.",
            }
        from django.contrib.auth import get_user_model

        try:
            user = get_user_model().objects.get(pk=self.host_user_id)
        except Exception:  # noqa: BLE001
            return {
                "allowed": False,
                "reason": "authentication_required",
                "message": "Not authorized to view organization workforce metrics.",
            }
        if is_global_admin(user):
            return {"allowed": True, "reason": "global_admin"}
        if _people_can(user, "people:view"):
            return {"allowed": True, "reason": "people:view"}
        return {
            "allowed": False,
            "reason": "people:view_required",
            "message": (
                "Not authorized to view organization workforce metrics "
                "(people:view required)."
            ),
        }

    def entity_exists_unscoped(self, model_path: str, filters: dict) -> bool:
        """True if any row matches filters with **no** org CBAC scope applied.

        Used only to distinguish ``not found`` from ``unauthorized`` for ESS
        callers who lack ``people:view`` (Wave B4 soft-deny honesty). Never
        returns row payloads.
        """
        import importlib

        if not filters:
            return False
        mod_name, cls_name = model_path.rsplit(".", 1)
        model_cls = getattr(importlib.import_module(mod_name), cls_name)
        try:
            return model_cls.objects.filter(
                **_normalize_people_entity_filters(filters)
            ).exists()
        except Exception:  # noqa: BLE001 — bad filter → treat as absent
            return False

    def user_capabilities(self) -> frozenset:
        """Return the acting user's CBAC capability keys (for honest masking)."""
        if not self.host_user_id:
            return frozenset()
        try:
            from accounts.capabilities import get_user_capabilities
            from django.contrib.auth import get_user_model
            user = get_user_model().objects.get(pk=self.host_user_id)
            return frozenset(get_user_capabilities(user))
        except Exception:  # noqa: BLE001
            return frozenset()

    # ── Confirmation lifecycle (Django Store-session compatible) ────────

    async def create_pending_execution(
        self,
        conversation_id: str,
        tool_name: str,
        method: str,
        endpoint: str,
        params: dict | None = None,
        body: dict | None = None,
        confirmation_message: str | None = None,
    ) -> "ToolExecution":
        """Stage a pending confirmation, stamped with the acting user.

        Same contract as :meth:`HostAPIExecutor.create_pending_execution`,
        plus ``host_user_id`` so ownership checks (P0-2) and tenant filtering
        hold in the in-process transport.
        """
        from ai.engine.core.models import ToolExecution, generate_uuid

        execution = ToolExecution(
            id=generate_uuid(),
            conversation_id=conversation_id,
            tool_name=tool_name,
            input_params=json.dumps({
                "method": method,
                "endpoint": endpoint,
                "params": params,
                "body": body,
                "confirmation_message": confirmation_message,
            }),
            status="pending_confirmation",
            confirmed_by_user=False,
            host_user_id=self.host_user_id,
        )
        self.db.add(execution)
        await self.db.commit()
        await self.db.refresh(execution)
        logger.info("Created pending execution: %s for %s %s", execution.id, method, endpoint)
        return execution

    async def confirm_execution(
        self,
        execution_id: str,
        expected_host_user_id: str | None = None,
    ) -> dict:
        """Confirm a staged execution and run it in-process.

        Re-implements :meth:`HostAPIExecutor.confirm_execution` using the
        Django Store session surface (``select``/``commit`` — the base class
        uses SQLAlchemy ``execute()`` which the Store session does not expose).
        """
        from ai.engine.core.models import ToolExecution

        rows = await self.db.select(ToolExecution, {"id": execution_id})
        execution = rows[0] if rows else None

        if execution is None:
            raise ToolExecutionError(f"Execution '{execution_id}' not found")
        if execution.status != "pending_confirmation":
            raise ToolExecutionError(
                f"Execution '{execution_id}' is not pending confirmation "
                f"(status: {execution.status})"
            )

        # Defense-in-depth ownership check (P0-2)
        if (
            expected_host_user_id is not None
            and execution.host_user_id is not None
            and execution.host_user_id != expected_host_user_id
        ):
            raise ToolExecutionError(
                f"Execution '{execution_id}' belongs to {execution.host_user_id}, "
                f"not {expected_host_user_id}"
            )

        params = json.loads(execution.input_params) if execution.input_params else {}
        method = params.get("method", "GET")
        endpoint = params.get("endpoint", "")
        query_params = params.get("params")
        body = params.get("body")

        try:
            api_result = await self._call_api(method, endpoint, query_params, body)
        except Exception as exc:  # noqa: BLE001 - fail-visible
            execution.status = "failed"
            execution.output = json.dumps({"error": str(exc)})
            execution.executed_at = _utcnow()
            await self.db.commit()
            raise

        # Honest confirm: non-2xx must not mark the staged write "confirmed"
        # (N-AG-LV-01: leave POST 4xx still showed Run completed with no row).
        status_code = None
        if isinstance(api_result, dict):
            status_code = api_result.get("status_code")
        try:
            code_int = int(status_code) if status_code is not None else None
        except (TypeError, ValueError):
            code_int = None
        if code_int is not None and not (200 <= code_int < 300):
            execution.status = "failed"
            execution.output = json.dumps(api_result, default=str)
            execution.executed_at = _utcnow()
            await self.db.commit()
            raise ToolExecutionError(
                f"Confirmed API call failed with HTTP {code_int} "
                f"({method} {endpoint})"
            )

        execution.status = "confirmed"
        execution.confirmed_by_user = True
        execution.output = json.dumps(api_result, default=str)
        execution.executed_at = _utcnow()
        await self.db.commit()

        logger.info("Executed confirmed action: %s → %s %s", execution_id, method, endpoint)
        return api_result

    async def decline_execution(
        self,
        execution_id: str,
        expected_host_user_id: str | None = None,
    ) -> None:
        """Decline a staged execution (Django Store-session compatible)."""
        from ai.engine.core.models import ToolExecution

        rows = await self.db.select(ToolExecution, {"id": execution_id})
        execution = rows[0] if rows else None

        if expected_host_user_id is not None and execution is not None:
            if (
                execution.host_user_id is not None
                and execution.host_user_id != expected_host_user_id
            ):
                raise ToolExecutionError(
                    f"Execution '{execution_id}' belongs to {execution.host_user_id}, "
                    f"not {expected_host_user_id}"
                )

        if execution is not None and execution.status == "pending_confirmation":
            execution.status = "declined"
            execution.executed_at = _utcnow()
            await self.db.commit()


def _utcnow():
    """Timezone-aware now for ``executed_at`` (matches engine clock)."""
    from django.utils.timezone import now

    return now()
