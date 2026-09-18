"""LTI Assignment and Grade Services (AGS) passback scaffold."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from gradevance.lti import ags_passback_allowed


@dataclass
class AgsScore:
    user_id: str
    score_given: float | None
    score_maximum: float
    activity_progress: str  # Initialized | Started | InProgress | Submitted | Completed
    grading_progress: str  # FullyGraded | Pending | PendingManual | Failed | NotReady
    comment: str = ""


class AgsPassbackError(Exception):
    pass


def build_ags_score_for_run(
    *,
    lti_user_id: str,
    mode: str,
    released: bool,
    advisory_bands: dict[str, Any] | None,
    mean_score_0_100: float | None,
) -> AgsScore:
    """Build an AGS score payload — does not HTTP POST yet."""
    if not ags_passback_allowed(released=released, mode=mode):
        raise AgsPassbackError("Summative run not released — AGS passback withheld")

    if mode == "summative" and released:
        return AgsScore(
            user_id=lti_user_id,
            score_given=mean_score_0_100,
            score_maximum=100.0,
            activity_progress="Completed",
            grading_progress="FullyGraded",
            comment="Released via GradeVance HITL",
        )

    # Formative — comment-only advisory (no score_given)
    bands = advisory_bands or {}
    comment = "Advisory bands: " + ", ".join(f"{k}={v}" for k, v in bands.items())
    return AgsScore(
        user_id=lti_user_id,
        score_given=None,
        score_maximum=100.0,
        activity_progress="InProgress",
        grading_progress="NotReady",
        comment=comment[:500],
    )


def ags_lineitem_url_from_claim(claims: dict) -> str | None:
    endpoint = claims.get("https://purl.imsglobal.org/spec/lti-ags/claim/endpoint") or {}
    if isinstance(endpoint, dict):
        return endpoint.get("lineitem") or (endpoint.get("lineitems") or [None])[0]
    return None
