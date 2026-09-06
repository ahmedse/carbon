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

from ai.engine.agent.executor import HostAPIExecutor
from ai.engine.core.exceptions import ToolExecutionError

logger = logging.getLogger("carbon.ai.host_executor")


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
        "gender", "is_active", "nationality", "nationality_code",
        "employment_type_code", "contract_type_code",
        "position", "org_unit", "kuwaitization", "rotation",
    }
    FK_LABEL_MAP = {
        "position": ("people.models.Position", "title"),
        "org_unit": ("mdm.models.OrgUnit",     "name"),
    }
    BLANK_CAVEAT_PCT = 50.0

    dimension = (params.get("dimension") or "").strip().lower()
    if dimension not in ALLOWED_DIMENSIONS:
        return {
            "status_code": 400,
            "data": {
                "detail": (
                    f"Unknown dimension '{dimension}'. "
                    f"Allowed: {', '.join(sorted(ALLOWED_DIMENSIONS))}"
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

    # ── Synonym normalisation (text fields only; FK fields skip this) ──────
    # Merge raw DB values into canonical buckets so "M" and "male" become one row.
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
            canonical = pk_to_label.get(raw_val, "(blank)") if raw_val is not None else "(blank)"
            bucket_counts[canonical] += row["count"]
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
                try:
                    employee = qs.get(pk=pk)
                except Employee.DoesNotExist:
                    return {"status_code": 404, "data": {"detail": "Employee not found"}}
                return {"status_code": 200, "data": mask_employee(S.EmployeeSerializer(employee).data, user)}
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
                    run = qs.get(pk=pk)
                except PayrollRun.DoesNotExist:
                    return {"status_code": 404, "data": {"detail": "Payroll run not found"}}
                return {"status_code": 200, "data": S.PayrollRunSerializer(run).data}
            results = S.PayrollRunSerializer(qs, many=True).data
            return {"status_code": 200, "data": {"count": len(results), "results": results}}

        if method == "POST" and action in ("compute", "validate", "commit"):
            from people.payroll_service import PayrollRunService, PayrollServiceError
            from people.validation import persist_findings

            qs = _people_scope(user, PayrollRun.objects.all(), "org_unit_id__in")
            try:
                run = qs.get(pk=pk)
            except PayrollRun.DoesNotExist:
                return {"status_code": 404, "data": {"detail": "Payroll run not found"}}
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
            total = qs.count()
            page = qs[:_PEOPLE_LIST_PAGE_CAP]
            results = S.LeaveEntitlementSerializer(page, many=True).data
            data = {"total": total, "count": len(results), "results": results}
            if total > _PEOPLE_LIST_PAGE_CAP:
                data["truncated"] = True
                data["caveat"] = f"Showing first {len(results)} of {total} leave entitlements."
            return {"status_code": 200, "data": data}

    # ── Leave records (list + create) ───────────────────────────────────
    if resource == "leave-records":
        from people.models import LeaveRecord

        if method == "GET":
            qs = _people_scope(user, LeaveRecord.objects.all(), "employee__org_unit_id__in")
            total = qs.count()
            page = qs[:_PEOPLE_LIST_PAGE_CAP]
            results = S.LeaveRecordSerializer(page, many=True).data
            data = {"total": total, "count": len(results), "results": results}
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
            total = qs.count()
            page = qs[:_PEOPLE_LIST_PAGE_CAP]
            results = S.LoanSerializer(page, many=True).data
            data = {"total": total, "count": len(results), "results": results}
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
        return {"status_code": 200, "data": summary}

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
        return {"status_code": 200, "data": payload}

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
            cap = "people:view" if method in ("GET", "HEAD", "OPTIONS") else "people:manage"
            if not _people_can(user, cap):
                return {"status_code": 403, "data": {"detail": f"{cap} capability required"}}
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
