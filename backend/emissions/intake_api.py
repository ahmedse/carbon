"""HTTP surface for CR-INT-01. The catalogue quotes files. Uploads do not invent kilograms."""
from __future__ import annotations

from django.http import HttpResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from emissions.campus_intake import (
    apply_template,
    coverage_board,
    coverage_row_state,
    enter_activity,
    enter_for_source,
    intake_catalogue,
    reconciliation_summary,
    record_assurance,
    record_contractual_factor,
    set_exclusion,
    store_discovered_activity,
    template_csv,
)
from emissions.views import CarbonBrandPermission


class CampusIntakeAPIView(APIView):
    permission_classes = [IsAuthenticated, CarbonBrandPermission]

    def get(self, request):
        payload = intake_catalogue()
        board = coverage_board(request.user)
        payload["streams"] = board["streams"]
        payload["periods"] = board["periods"]
        payload["coverage_complete"] = False
        payload["entry_period"] = board["open_period"]
        return Response(payload)


class CampusIntakeDiscoveredAPIView(APIView):
    """Record named-file quantities on the period they belong to. Writes no kilogram."""

    permission_classes = [IsAuthenticated, CarbonBrandPermission]

    def post(self, request):
        result = store_discovered_activity(user=request.user)
        status = 201 if result["written"] else 200
        return Response(result, status=status)


class CampusIntakeEntryAPIView(APIView):
    permission_classes = [IsAuthenticated, CarbonBrandPermission]

    def post(self, request):
        from emissions.models import EmissionFactor

        body = request.data if isinstance(request.data, dict) else {}
        factor = None
        factor_code = str(body.get("factor_code") or "").strip()
        if factor_code:
            factor = EmissionFactor.objects.filter(code=factor_code, is_active=True).first()
            if factor is None:
                return Response({"written": False, "kilograms": None, "errors": ["factor"]}, status=400)
        result = enter_activity(user=request.user, fields=body, factor=factor)
        status = 201 if result["written"] else 200
        if result["errors"] and not result["exclusions"]:
            status = 400
        return Response(result, status=status)


class CoverageRowSubmissionAPIView(APIView):
    """Submit activity against ONE coverage row (InventorySource).

    GET  returns the row's Missing / Entered / Excluded state on the open period.
    POST prefills campus, scope, unit and period from the row and stores one
    value. The client never picks a leaf, campus, scope or unit by hand.
    """

    permission_classes = [IsAuthenticated, CarbonBrandPermission]

    def _source(self, source_id):
        from emissions.models import InventorySource

        return (
            InventorySource.objects.filter(pk=source_id, is_active=True)
            .select_related("org_unit")
            .first()
        )

    def get(self, request, source_id):
        source = self._source(source_id)
        if source is None:
            return Response({"detail": "Coverage row not found."}, status=404)
        return Response(coverage_row_state(source, request.user))

    def post(self, request, source_id):
        from emissions.models import EmissionFactor

        source = self._source(source_id)
        if source is None:
            return Response({"detail": "Coverage row not found."}, status=404)
        body = request.data if isinstance(request.data, dict) else {}
        factor = None
        factor_code = str(body.get("factor_code") or "").strip()
        if factor_code:
            factor = EmissionFactor.objects.filter(code=factor_code, is_active=True).first()
            if factor is None:
                return Response({"written": False, "kilograms": None, "errors": ["factor"]}, status=400)
        result = enter_for_source(source=source, user=request.user, fields=body, factor=factor)
        status = 201 if result["written"] else 200
        if result["errors"] and not result["exclusions"]:
            status = 400
        payload = dict(result)
        payload["coverage_row"] = coverage_row_state(source, request.user)
        return Response(payload, status=status)


class CoverageRowExclusionAPIView(APIView):
    """Declare or clear an exclusion for ONE coverage row.

    POST prefills the row and the single open period. It writes only the
    open period's InventorySourceStatus; a locked or closed period is not a
    write target. No kilogram and no Calculation is produced. ``reason`` is
    required when excluding and must be one of the four vocabulary codes;
    ``other`` also requires notes.
    """

    permission_classes = [IsAuthenticated, CarbonBrandPermission]

    def post(self, request, source_id):
        from emissions.models import InventorySource

        source = (
            InventorySource.objects.filter(pk=source_id, is_active=True)
            .select_related("org_unit")
            .first()
        )
        if source is None:
            return Response({"detail": "Coverage row not found."}, status=404)
        body = request.data if isinstance(request.data, dict) else {}
        excluded = body.get("excluded", True)
        if isinstance(excluded, str):
            excluded = excluded.strip().lower() not in {"false", "0", "no", ""}
        result = set_exclusion(
            source=source,
            user=request.user,
            excluded=bool(excluded),
            reason=body.get("reason") or "",
            notes=body.get("notes") or "",
        )
        if result["written"]:
            status = 201
        elif result["errors"] and not result["exclusions"]:
            status = 400
        else:
            status = 200
        return Response(result, status=status)


class CoverageReconciliationAPIView(APIView):
    """Required vs received counts. Coverage is the only surface that says these.

    GET returns counts (required, entered, excluded, missing, awaiting_factor)
    for the open period and per active CoverageGoal. It returns no kilogram and
    no "coverage complete" percent.
    """

    permission_classes = [IsAuthenticated, CarbonBrandPermission]

    def get(self, request):
        return Response(reconciliation_summary(request.user))


class CampusIntakeTemplateAPIView(APIView):
    permission_classes = [IsAuthenticated, CarbonBrandPermission]

    def get(self, request, leaf_id):
        body = template_csv(leaf_id)
        if not body:
            return Response({"detail": "This leaf has no activity template."}, status=404)
        response = HttpResponse(body, content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{leaf_id}-template.csv"'
        return response


class CampusIntakeUploadAPIView(APIView):
    permission_classes = [IsAuthenticated, CarbonBrandPermission]

    def post(self, request, leaf_id):
        from emissions.models import EmissionFactor

        rows = request.data.get("rows") if isinstance(request.data, dict) else None
        if not isinstance(rows, list):
            return Response({"written": False, "kilograms": None, "errors": ["rows"]}, status=400)
        factor = None
        factor_code = str(request.data.get("factor_code") or "").strip()
        if factor_code:
            factor = EmissionFactor.objects.filter(code=factor_code, is_active=True).first()
            if factor is None:
                return Response({"written": False, "kilograms": None, "errors": ["factor"]}, status=400)
        result = apply_template(leaf_id=leaf_id, rows=rows, user=request.user, factor=factor)
        status = 201 if result["written"] else 200
        if result["errors"] and not result["exclusions"]:
            status = 400
        return Response(result, status=status)


class ContractualFactorAPIView(APIView):
    permission_classes = [IsAuthenticated, CarbonBrandPermission]

    def get(self, request):
        from emissions.models import ContractualScope2Factor

        row = (
            ContractualScope2Factor.objects.filter(is_active=True)
            .select_related("emission_factor", "grid_factor")
            .order_by("-recorded_at")
            .first()
        )
        if row is None:
            return Response({
                "present": False,
                "reason": "no_distinct_contractual_factor",
                "total_co2e_kg": None,
            })
        return Response({
            "present": True,
            "factor_id": row.emission_factor_id,
            "factor_code": row.emission_factor.code,
            "source": row.emission_factor.source,
            "total_co2e_kg": None,
        })

    def post(self, request):
        from django.core.exceptions import ValidationError

        from emissions.models import EmissionFactor

        code = str(request.data.get("factor_code") or "").strip()
        grid_code = str(request.data.get("grid_factor_code") or "").strip()
        contractual = EmissionFactor.objects.filter(code=code).first()
        grid = EmissionFactor.objects.filter(code=grid_code).first()
        if contractual is None or grid is None:
            return Response({"present": False, "total_co2e_kg": None, "errors": ["factor"]}, status=400)
        try:
            record_contractual_factor(contractual=contractual, grid=grid)
        except ValidationError as exc:
            return Response({"present": False, "total_co2e_kg": None, "errors": exc.messages}, status=400)
        return Response({"present": True, "factor_code": code, "total_co2e_kg": None}, status=201)


class AssuranceEngagementAPIView(APIView):
    permission_classes = [IsAuthenticated, CarbonBrandPermission]

    def get(self, request):
        from emissions.campus_intake import assurance_status
        from emissions.models import AssuranceEngagement, ReportingPeriod

        period = ReportingPeriod.objects.filter(status="open").order_by("id").first()
        latest = None
        if period is not None:
            latest = AssuranceEngagement.objects.filter(reporting_period=period).order_by("-recorded_at").first()
        fields = None
        if latest is not None:
            fields = {
                "assurer_name": latest.assurer_name,
                "engagement_type": latest.engagement_type,
                "standard": latest.standard,
                "opinion_date": latest.opinion_date,
                "statement_id": latest.statement_id,
            }
        status = assurance_status(fields, period.end_date if period else None)
        status["recorded"] = latest is not None
        return Response(status)

    def post(self, request):
        from emissions.models import ReportingPeriod

        periods = list(ReportingPeriod.objects.filter(status="open").order_by("id"))
        if len(periods) != 1:
            return Response({"not_assured_met": False, "errors": ["open period count"]}, status=400)
        status = record_assurance(reporting_period=periods[0], fields=request.data)
        return Response(status, status=201)
