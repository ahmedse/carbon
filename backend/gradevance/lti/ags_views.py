"""AGS passback API — preview + optional HTTP POST to LMS lineitem."""
from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from gradevance.lti.ags import AgsPassbackError, build_ags_score_for_run
from gradevance.lti.ags_passback import (
    attempt_ags_passback,
    lineitem_from_assignment,
    lti_user_from_submission,
    record_ags_on_run,
)
from gradevance.models import AnalysisRun
from gradevance.permissions import GradevanceMarkAccess


def _mean_score(run: AnalysisRun) -> float | None:
    scores = [
        s.score_0_100
        for s in run.rubric_scores.all()
        if s.score_0_100 is not None
    ]
    return sum(scores) / len(scores) if scores else None


def _lti_user_id(request, run: AnalysisRun) -> str:
    return (
        request.query_params.get("lti_user_id")
        or (request.data.get("lti_user_id") if hasattr(request, "data") else None)
        or lti_user_from_submission(run)
    )


def _lineitem_url(request, run: AnalysisRun) -> str:
    explicit = ""
    if hasattr(request, "data") and isinstance(request.data, dict):
        explicit = (request.data.get("lineitem_url") or "").strip()
    if not explicit:
        explicit = (request.query_params.get("lineitem_url") or "").strip()
    return explicit or lineitem_from_assignment(run)


class RunAgsPreviewView(APIView):
    """Preview AGS score JSON for a run (no network call)."""

    permission_classes = [IsAuthenticated, GradevanceMarkAccess]

    def get(self, request, run_id):
        try:
            run = AnalysisRun.objects.select_related("submission__assignment").get(pk=run_id)
        except AnalysisRun.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)
        asg = run.submission.assignment
        try:
            payload = build_ags_score_for_run(
                lti_user_id=_lti_user_id(request, run),
                mode=asg.mode,
                released=run.released,
                advisory_bands=run.advisory_bands,
                mean_score_0_100=_mean_score(run),
            )
        except AgsPassbackError as exc:
            return Response({"detail": str(exc), "allowed": False}, status=409)
        return Response(
            {
                "allowed": True,
                "score": {
                    "userId": payload.user_id,
                    "scoreGiven": payload.score_given,
                    "scoreMaximum": payload.score_maximum,
                    "activityProgress": payload.activity_progress,
                    "gradingProgress": payload.grading_progress,
                    "comment": payload.comment,
                },
                "lineitem_url": _lineitem_url(request, run) or None,
                "note": "POST /ags-passback/ to send (dry-run default). Release also triggers when lineitem set.",
            }
        )


class RunAgsPassbackView(APIView):
    """Build + POST AGS score. Default dry-run; set GRADEVANCE_LTI_AGS_DRY_RUN=false."""

    permission_classes = [IsAuthenticated, GradevanceMarkAccess]

    def post(self, request, run_id):
        try:
            run = (
                AnalysisRun.objects.select_related("submission__assignment")
                .prefetch_related("rubric_scores")
                .get(pk=run_id)
            )
        except AnalysisRun.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)
        lineitem = _lineitem_url(request, run)
        if not lineitem:
            return Response(
                {
                    "detail": "lineitem_url required (body or assignment.brief.lti.ags_lineitem_url)",
                },
                status=400,
            )
        dry = request.data.get("dry_run")
        dry_run = None if dry is None else bool(dry)
        result = attempt_ags_passback(
            run,
            lineitem_url=lineitem,
            dry_run=dry_run,
            lti_user_id=_lti_user_id(request, run),
        )
        if result.get("error") and not result.get("ok"):
            # Distinguish withhold (409) vs transport failure (502).
            if "withheld" in (result.get("error") or "").lower() or "not released" in (
                result.get("error") or ""
            ).lower():
                return Response({"detail": result["error"], "allowed": False}, status=409)
        record_ags_on_run(run, result)
        http_status = status.HTTP_200_OK if result.get("ok") else status.HTTP_502_BAD_GATEWAY
        if not result.get("attempted"):
            http_status = status.HTTP_400_BAD_REQUEST
        return Response(
            {
                "allowed": True,
                "dry_run": result.get("dry_run"),
                "ok": result.get("ok"),
                "status_code": result.get("status_code"),
                "url": result.get("url"),
                "body": result.get("body"),
                "error": result.get("error"),
            },
            status=http_status,
        )
