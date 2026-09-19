"""Submission lifecycle helpers — draft / submit / review enqueue (Phase D)."""
from __future__ import annotations

from gradevance.models import AnalysisRun, Assignment, ReviewItem, Submission
from gradevance.services import FormativePipelineService


def resolve_create_status(*, requested, analyze: bool) -> str:
    """Default draft; analyze keeps draft unless client sets status=submitted."""
    if requested in (Submission.STATUS_DRAFT, Submission.STATUS_SUBMITTED):
        return requested
    return Submission.STATUS_DRAFT


def ensure_summative_submit_review(submission: Submission) -> ReviewItem | None:
    """On summative submit: ensure a run exists and an open ReviewItem for it."""
    assignment = submission.assignment
    if assignment.mode != Assignment.MODE_SUMMATIVE:
        return None

    run = (
        AnalysisRun.objects.filter(submission=submission)
        .order_by("-created_at")
        .first()
    )
    if run is None:
        run = FormativePipelineService().analyze_submission(submission)
        # analyze preserves draft; restore submitted after enqueue path.
        if submission.status != Submission.STATUS_SUBMITTED:
            submission.status = Submission.STATUS_SUBMITTED
            submission.save(update_fields=["status", "updated_at"])

    existing = (
        ReviewItem.objects.filter(run=run)
        .exclude(status=ReviewItem.STATUS_RESOLVED)
        .order_by("-created_at")
        .first()
    )
    if existing is not None:
        if existing.reason != "student submit":
            existing.reason = "student submit"
            existing.save(update_fields=["reason"])
        return existing

    return ReviewItem.objects.create(
        run=run,
        status=ReviewItem.STATUS_OPEN,
        priority=80,
        reason="student submit",
    )
