"""
AI Pulse Ops API — read-only in-process engine observability surface.

GET  /carbon-api/ai/pulse/health/
GET  /carbon-api/ai/pulse/modules/
GET  /carbon-api/ai/pulse/tasks/{task_id}/

Read-only by structure: every view is a GET-only ``APIView`` (no models
back these endpoints, so no viewset). The engine runs in-process — there
is no HTTP transport to Pulse — and these endpoints advertise its
capabilities and expose task status for the AI admin console.
"""

import logging
from dataclasses import asdict

from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import AdminOrSuperuserOnly
from ai.engine_runtime import get_task, list_modules
from ai.intelligence import CarbonIntelligence

logger = logging.getLogger("carbon.ai.ops_api")


class PulseHealthView(APIView):
    """GET /health/ — engine health plus advertised modules."""

    permission_classes = [AdminOrSuperuserOnly]
    required_capability = "ai:view_console"

    def get(self, request):
        try:
            status = CarbonIntelligence().health_check()
            return Response(asdict(status))
        except Exception as exc:  # noqa: BLE001 — never 500 the console
            logger.exception("pulse health check failed")
            return Response(
                {
                    "name": "pulse",
                    "version": "unknown",
                    "healthy": False,
                    "modules_available": [],
                    "error": str(exc),
                }
            )


class PulseModulesView(APIView):
    """GET /modules/ — the task types the in-process engine advertises."""

    permission_classes = [AdminOrSuperuserOnly]
    required_capability = "ai:view_console"

    def get(self, request):
        data = list_modules()
        modules = data.get("modules", [])
        return Response({"modules": modules, "count": len(modules)})


class PulseTaskStatusView(APIView):
    """GET /tasks/{task_id}/ — in-process task status (fail-visible).

    ``engine_runtime.get_task`` never raises: unknown ids return a
    fail-visible ``{status: pulse_unavailable, error: {code: not_found}}``
    envelope, which we pass through unchanged.
    """

    permission_classes = [AdminOrSuperuserOnly]
    required_capability = "ai:view_console"

    def get(self, request, task_id):
        return Response(get_task(task_id))


# ── Domain App Manifest API ───────────────────────────────────────────────
# GET /carbon-api/ai/apps/            → all registered domain manifests
# GET /carbon-api/ai/apps/{app_id}/  → single domain manifest
#
# Used by the frontend to discover:
#   - Which task types each domain app supports
#   - Which entry-point buttons to render on domain pages
#   - Which starter chips to show in the AI workspace empty state
#
# Authentication: IsAuthenticated (non-admin users need to see their app's
# capabilities). No capability guard required — manifests contain no secrets.


class DomainAppManifestListView(APIView):
    """GET /apps/ — list manifests for all registered domain apps."""

    def get(self, request):
        from ai.domain_protocol import all_manifests
        return Response({"apps": all_manifests(), "count": len(all_manifests())})


class DomainAppManifestDetailView(APIView):
    """GET /apps/{app_identifier}/ — manifest for a single domain app."""

    def get(self, request, app_identifier):
        from ai.domain_protocol import get_manifest, has_domain
        if not has_domain(app_identifier):
            return Response(
                {"detail": f"Domain '{app_identifier}' is not registered."},
                status=404,
            )
        return Response(get_manifest(app_identifier))


# ── Access & CBAC assistance (Phase 24-H) ─────────────────────────────────
# Read-only/proposal-only. Every view is capability-gated and filters its
# answers by the caller's org subtree when requested. Proposals never write.


def _parse_org_ids(request) -> list[int] | None:
    """``?org_unit_ids=1,2,3`` → [1,2,3]; absent → None (global scope)."""
    raw = request.query_params.get("org_unit_ids")
    if not raw:
        return None
    try:
        return [int(part) for part in raw.split(",") if part.strip()]
    except ValueError:
        return []


class AccessAssistCapabilitiesView(APIView):
    """GET /access-assist/users/{user_id}/capabilities/?org_unit_ids=… — effective capability set."""

    permission_classes = [AdminOrSuperuserOnly]
    required_capability = "platform:view_audit"

    def get(self, request, user_id):
        from ai.knowledge.access_assist import effective_capabilities
        return Response(effective_capabilities(user_id, org_unit_ids=_parse_org_ids(request)))


class AccessAssistUsersWithCapabilityView(APIView):
    """GET /access-assist/capability/{capability_key}/users/?org_unit_ids=… — who can reach X?"""

    permission_classes = [AdminOrSuperuserOnly]
    required_capability = "platform:view_audit"

    def get(self, request, capability_key):
        from ai.knowledge.access_assist import users_with_capability
        return Response(users_with_capability(capability_key, org_unit_ids=_parse_org_ids(request)))


class AccessAssistProposeGrantView(APIView):
    """POST /access-assist/propose-grant/ — least-privilege grant proposal.

    Read-only: returns a ``requires_confirmation`` payload; never mutates.
    """

    permission_classes = [AdminOrSuperuserOnly]
    required_capability = "platform:manage_access"

    def post(self, request):
        from ai.knowledge.access_assist import propose_grant

        user_id = request.data.get("user_id")
        capability_key = request.data.get("capability_key")
        org_unit_ids = request.data.get("org_unit_ids")
        if not user_id or not capability_key:
            return Response(
                {"detail": "user_id and capability_key are required."}, status=400
            )
        result = propose_grant(
            user_id=int(user_id),
            capability_key=str(capability_key),
            org_unit_ids=org_unit_ids,
        )
        if "error" in result:
            return Response(result, status=404 if result["error"]["code"] == "not_found" else 400)
        return Response(result)


class AccessAssistAnomaliesView(APIView):
    """GET /access-assist/anomalies/?org_unit_ids=… — over-granted users + dormant grants."""

    permission_classes = [AdminOrSuperuserOnly]
    required_capability = "platform:view_audit"

    def get(self, request):
        from ai.knowledge.access_assist import flag_access_anomalies
        return Response(flag_access_anomalies(org_unit_ids=_parse_org_ids(request)))


# ── Lineage & impact (Phase 24-I) ─────────────────────────────────────────
# Read-only knowledge-graph projections over dataschema lineage + DQ rules
# (extends Phase B dq_graph). The coworker engine calls the modules directly;
# these HTTP views gate the admin console surface on platform:view_audit.


class LineageTableView(APIView):
    """GET /lineage/table/{table_id}/ — transitive upstream/downstream lineage."""

    permission_classes = [AdminOrSuperuserOnly]
    required_capability = "platform:view_audit"

    def get(self, request, table_id):
        from ai.knowledge.lineage import table_lineage
        result = table_lineage(table_id)
        if "error" in result:
            return Response(result, status=404)
        return Response(result)


class LineageFieldView(APIView):
    """GET /lineage/field/{field_id}/ — field-level flow (feeds / fed-by / references)."""

    permission_classes = [AdminOrSuperuserOnly]
    required_capability = "platform:view_audit"

    def get(self, request, field_id):
        from ai.knowledge.lineage import field_lineage
        result = field_lineage(field_id)
        if "error" in result:
            return Response(result, status=404)
        return Response(result)


class ImpactTableView(APIView):
    """GET /impact/table/{table_id}/ — what breaks if this table changes."""

    permission_classes = [AdminOrSuperuserOnly]
    required_capability = "platform:view_audit"

    def get(self, request, table_id):
        from ai.knowledge.lineage import impact_analysis_table
        result = impact_analysis_table(table_id)
        if "error" in result:
            return Response(result, status=404)
        return Response(result)


class ImpactFieldView(APIView):
    """GET /impact/field/{field_id}/ — what breaks if this field changes."""

    permission_classes = [AdminOrSuperuserOnly]
    required_capability = "platform:view_audit"

    def get(self, request, field_id):
        from ai.knowledge.lineage import impact_analysis_field
        result = impact_analysis_field(field_id)
        if "error" in result:
            return Response(result, status=404)
        return Response(result)


# ── Governance & policy (Phase 24-J) ──────────────────────────────────────
# Explain / map / drift are read-only (platform:view_audit). Drafting a
# policy change is DRAFT-ONLY — the reply carries requires_confirmation and
# never writes (RULE_21); gated on catalog:manage_policies (the capability
# whose holder may eventually apply it).


def _parse_bool_param(request, name: str) -> bool | None:
    raw = request.query_params.get(name)
    if raw is None:
        return None
    return raw.lower() in ("1", "true", "yes", "on")


class PolicyListView(APIView):
    """GET /policies/?enabled=1&scope_type=global — policy inventory."""

    permission_classes = [AdminOrSuperuserOnly]
    required_capability = "platform:view_audit"

    def get(self, request):
        from ai.knowledge.policy_advisor import list_policies
        return Response(list_policies(
            enabled=_parse_bool_param(request, "enabled"),
            scope_type=request.query_params.get("scope_type"),
        ))


class PolicyExplainView(APIView):
    """GET /policies/{policy_id}/ — policy explanation grounded in the rule catalog."""

    permission_classes = [AdminOrSuperuserOnly]
    required_capability = "platform:view_audit"

    def get(self, request, policy_id):
        from ai.knowledge.policy_advisor import explain_policy
        result = explain_policy(policy_id)
        if "error" in result:
            return Response(result, status=404)
        return Response(result)


class PolicyDraftView(APIView):
    """POST /policies/{policy_id}/draft/ — DRAFT a policy change (never executes)."""

    permission_classes = [AdminOrSuperuserOnly]
    required_capability = "catalog:manage_policies"

    def post(self, request, policy_id):
        from ai.knowledge.policy_advisor import draft_policy_change
        result = draft_policy_change(policy_id, request.data.get("proposed", {}))
        if "error" in result:
            status = 404 if result["error"]["code"] == "not_found" else 400
            return Response(result, status=status)
        return Response(result)


class PolicyMapView(APIView):
    """GET /policies/map/ — rules → policies → dimensions projection."""

    permission_classes = [AdminOrSuperuserOnly]
    required_capability = "platform:view_audit"

    def get(self, request):
        from ai.knowledge.policy_advisor import map_rules_to_policies
        return Response(map_rules_to_policies())


class PolicyDriftView(APIView):
    """GET /policies/drift/ — unbound rules, stale policies, dimension gaps."""

    permission_classes = [AdminOrSuperuserOnly]
    required_capability = "platform:view_audit"

    def get(self, request):
        from ai.knowledge.policy_advisor import flag_policy_drift
        return Response(flag_policy_drift())


# ── MDM & data product (Phase 24-K) ────────────────────────────────────────
# Entity explain + dedup suggestions are read-only (platform:view_audit).
# Proposing a merge is DRAFT-ONLY — requires_confirmation payload, never
# writes (RULE_21); gated on mdm:manage (the capability whose holder may
# eventually apply the merge).


def _parse_threshold(request, default: float = 0.85) -> float:
    try:
        value = float(request.query_params.get("threshold", default))
    except (TypeError, ValueError):
        return default
    return min(max(value, 0.0), 1.0)


class MdmExplainView(APIView):
    """GET /mdm/entity/{value_id}/ — explain an entity's master record."""

    permission_classes = [AdminOrSuperuserOnly]
    required_capability = "platform:view_audit"

    def get(self, request, value_id):
        from ai.knowledge.mdm_advisor import explain_entity
        result = explain_entity(value_id)
        if "error" in result:
            return Response(result, status=404)
        return Response(result)


class MdmDedupView(APIView):
    """GET /mdm/dedup/?set_id=1&threshold=0.85 — dedup suggestions (never merges)."""

    permission_classes = [AdminOrSuperuserOnly]
    required_capability = "platform:view_audit"

    def get(self, request):
        from ai.knowledge.mdm_advisor import dedup_suggestions
        set_id = request.query_params.get("set_id")
        result = dedup_suggestions(
            set_id=int(set_id) if set_id and set_id.isdigit() else None,
            threshold=_parse_threshold(request),
        )
        if "error" in result:
            return Response(result, status=404)
        return Response(result)


class MdmProposeMergeView(APIView):
    """POST /mdm/dedup/propose-merge/ — DRAFT a merge (never executes)."""

    permission_classes = [AdminOrSuperuserOnly]
    required_capability = "mdm:manage"

    def post(self, request):
        from ai.knowledge.mdm_advisor import propose_merge
        data = request.data or {}
        result = propose_merge(
            set_id=data.get("set_id"),
            duplicate_value_id=data.get("duplicate_value_id"),
            gold_value_id=data.get("gold_value_id"),
        )
        if "error" in result:
            return Response(result, status=404)
        return Response(result)
