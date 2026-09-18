"""Shared AGS passback orchestration for release + API views."""
from __future__ import annotations

import logging
from typing import Any

from gradevance.lti.ags import AgsPassbackError, build_ags_score_for_run
from gradevance.lti.ags_client import post_ags_score
from gradevance.models import AnalysisRun

logger = logging.getLogger(__name__)


def _mean_score(run: AnalysisRun) -> float | None:
    scores = [
        s.score_0_100
        for s in run.rubric_scores.all()
        if s.score_0_100 is not None
    ]
    return sum(scores) / len(scores) if scores else None


def lineitem_from_assignment(run: AnalysisRun) -> str:
    brief = run.submission.assignment.brief or {}
    if not isinstance(brief, dict):
        return ""
    lti = brief.get("lti") if isinstance(brief.get("lti"), dict) else {}
    return (lti.get("ags_lineitem_url") or lti.get("lineitem") or "").strip()


def lti_user_from_submission(run: AnalysisRun) -> str:
    return (run.submission.external_student_key or "").strip() or "unknown"


def attempt_ags_passback(
    run: AnalysisRun,
    *,
    lineitem_url: str | None = None,
    dry_run: bool | None = None,
    lti_user_id: str | None = None,
) -> dict[str, Any]:
    """Build + POST (or dry-run) AGS score. Returns a JSON-serialisable result dict."""
    lineitem = (lineitem_url or lineitem_from_assignment(run) or "").strip()
    if not lineitem:
        return {"attempted": False, "reason": "no_lineitem_url"}

    asg = run.submission.assignment
    try:
        score = build_ags_score_for_run(
            lti_user_id=lti_user_id or lti_user_from_submission(run),
            mode=asg.mode,
            released=run.released,
            advisory_bands=run.advisory_bands,
            mean_score_0_100=_mean_score(run),
        )
        result = post_ags_score(lineitem_url=lineitem, score=score, dry_run=dry_run)
    except AgsPassbackError as exc:
        return {"attempted": True, "ok": False, "error": str(exc)}

    return {
        "attempted": True,
        "ok": result.ok,
        "dry_run": result.dry_run,
        "status_code": result.status_code,
        "url": result.url,
        "body": result.body,
        "error": result.error or None,
    }


def record_ags_on_run(run: AnalysisRun, result: dict[str, Any]) -> None:
    """Persist last AGS attempt onto run_manifest (best-effort)."""
    if not result.get("attempted"):
        return
    manifest = dict(run.run_manifest or {})
    manifest["ags_passback"] = result
    run.run_manifest = manifest
    run.save(update_fields=["run_manifest"])
