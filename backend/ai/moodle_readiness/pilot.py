"""Recorded local consented student pilot — typed mirror + gate inputs.

Authority: ``docs/pulse/aast-med/PILOT-EXCEPTION.md`` (platform superuser,
3 Oct 2026, live session). Local dev only.

This module never stores student content. It reads **only** the typed consent
STATE (grant/revoke + ``policy_version`` + timestamp) and the published student
notice state mirrored from the Moodle plugin tables in
``docs/pulse/aast-med/evidence/pilot-consent-state.json``. Identity (the two
real Moodle student accounts) stays in Moodle; Carbon sees ids and typed state.

The gate is the same pure :func:`consult_student_surface`. Nothing here is
imported by the Ask turn, the engine, or the Moodle host seam.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ai.moodle_readiness.evaluator import ReadinessInputs, repo_inputs
from ai.moodle_readiness.gate import (
    Cohort,
    ConsentRecord,
    GateDecision,
    StudentSurfaceContext,
    consult_student_surface,
)

__all__ = [
    "PILOT_COHORT_IDNUMBER",
    "PILOT_COURSE",
    "PILOT_ENABLED_COURSES",
    "PILOT_POLICY_VERSION",
    "PILOT_STATE_PATH",
    "PILOT_STUDENT_USERNAMES",
    "consent_records",
    "is_pilot_user",
    "load_state",
    "pilot_cohort",
    "pilot_consent",
    "pilot_gate",
    "pilot_inputs",
    "pilot_student_ids",
]

REPO_ROOT = Path(__file__).resolve().parents[3]
PILOT_STATE_PATH = REPO_ROOT / "docs" / "pulse" / "aast-med" / "evidence" / "pilot-consent-state.json"

PILOT_COHORT_IDNUMBER = "pulse_student_pilot"
PILOT_COURSE = "NMD1103"
PILOT_POLICY_VERSION = 1
PILOT_STUDENT_USERNAMES = ("pilot_student_a", "pilot_student_b")

#: The 13 listed shortnames a pilot student may already open (RBAC input).
PILOT_ENABLED_COURSES = frozenset(
    {
        "NMD1000",
        "NMD1103",
        "NMD1301",
        "NMD1402",
        "NMD2101",
        "MED213",
        "NMD2303",
        "NMD2403",
        "NMD3101",
        "NMD3304",
        "NMD4201",
        "MED520",
        "MED5310",
    }
)

_EMPTY: dict[str, Any] = {"consent": {"policy_version": PILOT_POLICY_VERSION, "consent": [], "audit": []}}


def load_state(path: Path | None = None) -> dict[str, Any]:
    """Read the typed pilot mirror. Missing/corrupt file degrades to empty."""
    target = path if path is not None else PILOT_STATE_PATH
    try:
        data = json.loads(Path(target).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return dict(_EMPTY)
    return data if isinstance(data, dict) else dict(_EMPTY)


def _consent_block(state: dict[str, Any] | None) -> dict[str, Any]:
    block = (state or {}).get("consent")
    return block if isinstance(block, dict) else {}


def _latest_rows(state: dict[str, Any] | None) -> dict[tuple[str, str], dict[str, Any]]:
    """Latest consent row per (subject_id, course); the append-only tail wins."""
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for row in _consent_block(state).get("consent") or []:
        if not isinstance(row, dict):
            continue
        key = (str(row.get("userid") or ""), str(row.get("course") or ""))
        if not key[0] or not key[1]:
            continue
        if key not in latest or int(row.get("timecreated") or 0) >= int(latest[key].get("timecreated") or 0):
            latest[key] = row
    return latest


def policy_version(state: dict[str, Any] | None = None) -> int:
    data = state if state is not None else load_state()
    raw = _consent_block(data).get("policy_version")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return PILOT_POLICY_VERSION


def pilot_student_ids(state: dict[str, Any] | None = None) -> frozenset[str]:
    """The two real Moodle student ids that hold any consent row."""
    data = state if state is not None else load_state()
    ids = {key[0] for key in _latest_rows(data)}
    return frozenset(ids)


def is_pilot_user(user_id: str | int, state: dict[str, Any] | None = None) -> bool:
    return str(user_id or "") in pilot_student_ids(state)


def pilot_cohort(state: dict[str, Any] | None = None) -> Cohort:
    """Moodle system-cohort allow-list: the pilot students only."""
    return Cohort(student_ids=pilot_student_ids(state))


def pilot_consent(
    user_id: str | int,
    course: str = PILOT_COURSE,
    state: dict[str, Any] | None = None,
) -> ConsentRecord | None:
    """The typed consent record for (student, course), or None when absent."""
    data = state if state is not None else load_state()
    row = _latest_rows(data).get((str(user_id or ""), str(course or "")))
    if row is None:
        return None
    return ConsentRecord(
        subject_id=str(user_id or ""),
        course_shortname=str(row.get("course") or ""),
        policy_version=int(row.get("policy_version") or 0),
        granted=bool(row.get("granted")),
        granted_at=str(row.get("granted_at") or "") or None,
    )


def consent_records(state: dict[str, Any] | None = None) -> tuple[ConsentRecord, ...]:
    data = state if state is not None else load_state()
    out: list[ConsentRecord] = []
    for (userid, course), row in sorted(_latest_rows(data).items()):
        out.append(
            ConsentRecord(
                subject_id=userid,
                course_shortname=course,
                policy_version=int(row.get("policy_version") or 0),
                granted=bool(row.get("granted")),
                granted_at=str(row.get("granted_at") or "") or None,
            )
        )
    return tuple(out)


def student_notice_published(state: dict[str, Any] | None = None) -> bool:
    data = state if state is not None else load_state()
    notice = data.get("student_notice")
    return bool(isinstance(notice, dict) and notice.get("published"))


def pilot_gate(
    user_id: str | int,
    course: str = PILOT_COURSE,
    *,
    l5_passable: bool = True,
    notice_published: bool | None = None,
    can_open: bool = True,
    state: dict[str, Any] | None = None,
) -> GateDecision:
    """Run the real gate with the real pilot typed inputs."""
    data = state if state is not None else load_state()
    published = student_notice_published(data) if notice_published is None else bool(notice_published)
    ctx = StudentSurfaceContext(
        user_id=str(user_id or ""),
        course_shortname=str(course or ""),
        cohort=pilot_cohort(data),
        consent=pilot_consent(user_id, course, data),
        enabled_courses=PILOT_ENABLED_COURSES,
        can_open_course=bool(can_open),
        l5_passable=bool(l5_passable),
        student_notice_published=published,
        policy_version=policy_version(data),
    )
    return consult_student_surface(ctx)


def pilot_inputs(state: dict[str, Any] | None = None, **overrides: Any) -> ReadinessInputs:
    """Readiness inputs from the frozen gold plus the real pilot artifacts.

    The cohort, consent, notice, and audit come from the real Moodle pilot;
    the L5 sample/cite/extra and R11/R12 counts come from the frozen gold via
    :func:`repo_inputs`. This does **not** invent a production install: K10
    still requires ``production_installed`` which stays False.
    """
    data = state if state is not None else load_state()
    audit_rows = _consent_block(data).get("audit") or []
    return repo_inputs(
        student_cohorts_non_empty=len(pilot_student_ids(data)) > 0,
        student_notice_published=student_notice_published(data),
        consent_gate_present=True,
        rbac_path_present=True,
        audit_path_present=len(audit_rows) > 0,
        **overrides,
    )
