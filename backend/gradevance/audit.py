"""Audit export — immutable run evidence package (P3)."""
from __future__ import annotations

from django.http import HttpResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from gradevance.models import AnalysisRun, ExpertEdit
from gradevance.permissions import GradevanceViewAccess


def build_audit_payload(run: AnalysisRun) -> dict:
    """Full JSON evidence package for a released/formative run."""
    assignment = run.submission.assignment
    release_edit = None
    for e in run.expert_edits.all().order_by("-created_at"):
        after = e.after if isinstance(e.after, dict) else {}
        if e.edit_kind == ExpertEdit.KIND_OTHER and after.get("released") is True:
            release_edit = e
            break
    segments = []
    for seg in run.segments.all().prefetch_related("codes"):
        segments.append(
            {
                "id": str(seg.id),
                "ordinal": seg.ordinal,
                "start_word": seg.start_word,
                "end_word": seg.end_word,
                "stage_guess": seg.stage_guess,
                "text": seg.text,
                "codes": [
                    {
                        "dimension": c.dimension,
                        "value": c.value,
                        "numeric": c.numeric,
                        "confidence": c.confidence,
                        "source": c.source,
                        "evidence": c.evidence,
                    }
                    for c in seg.codes.all()
                ],
            }
        )

    wave = (run.run_manifest or {}).get("wave") or {}
    coaching = run.coaching if isinstance(run.coaching, dict) else {}
    return {
        "run_id": str(run.id),
        "assignment": {
            "id": str(assignment.id),
            "title": assignment.title,
            "mode": assignment.mode,
            "profile_pack_id": assignment.profile_pack_id,
            "profile_version": assignment.profile_version,
        },
        "submission": {
            "id": str(run.submission.id),
            "external_student_key": run.submission.external_student_key,
            "word_count": run.submission.word_count,
        },
        "profile_pack_id": run.profile_pack_id,
        "profile_version": run.profile_version,
        "pipeline_snapshot": run.pipeline_snapshot,
        "run_manifest": run.run_manifest,
        "status": run.status,
        "gate_decision": run.gate_decision,
        "released": run.released,
        "mean_confidence": run.mean_confidence,
        "advisory_bands": run.advisory_bands,
        "coaching": run.coaching,
        "fairness": {
            "mode": assignment.mode,
            "advisory_only": bool(coaching.get("watermark") == "advisory") and not run.released,
            "watermark": coaching.get("watermark"),
            "gate_decision": run.gate_decision,
            "summative_requires_release": assignment.mode == assignment.MODE_SUMMATIVE,
            "released": run.released,
            "note": (
                "Formative/advisory outputs are not high-stakes grades. "
                "Summative marks require explicit HITL release before AGS/audit."
            ),
        },
        "wave": {
            "metrics": wave.get("metrics") if isinstance(wave, dict) else None,
            "point_count": len(wave.get("points") or []) if isinstance(wave, dict) else 0,
        },
        "segments": segments,
        "segment_count": len(segments),
        "rubric_scores": [
            {
                "criterion_id": s.criterion_id,
                "band": s.band,
                "score_0_100": s.score_0_100,
                "source": s.source,
                "rationale": s.rationale,
                "evidence_bindings": s.evidence_bindings,
            }
            for s in run.rubric_scores.all()
        ],
        "expert_edits": [
            {
                "id": str(e.id),
                "edit_kind": e.edit_kind,
                "created_at": e.created_at.isoformat(),
                "editor_id": e.editor_id,
                "rationale": e.rationale,
                "before": e.before,
                "after": e.after,
            }
            for e in run.expert_edits.all()
        ],
        "release": {
            "released": run.released,
            "actor_id": release_edit.editor_id if release_edit else None,
            "timestamp": release_edit.created_at.isoformat() if release_edit else None,
        },
        "ags_passback": (run.run_manifest or {}).get("ags_passback"),
        "export_format": "json_v2",
        "note": "JSON evidence package; PDF packaging optional for institutional archives.",
    }


class RunAuditExportView(APIView):
    permission_classes = [IsAuthenticated, GradevanceViewAccess]

    def get(self, request, run_id):
        try:
            run = (
                AnalysisRun.objects.select_related("submission__assignment")
                .prefetch_related("expert_edits", "rubric_scores", "segments__codes")
                .get(pk=run_id)
            )
        except AnalysisRun.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)

        assignment = run.submission.assignment
        if assignment.mode == assignment.MODE_SUMMATIVE and not run.released:
            return Response(
                {"detail": "Summative run not released — audit export withheld."},
                status=status.HTTP_409_CONFLICT,
            )

        payload = build_audit_payload(run)
        fmt = request.query_params.get("format", "json")
        if fmt == "download":
            import json

            body = json.dumps(payload, indent=2, default=str)
            resp = HttpResponse(body, content_type="application/json")
            resp["Content-Disposition"] = f'attachment; filename="gradevance-run-{run.id}.json"'
            return resp
        return Response(payload)
