"""Readiness machinery tests: default deny, default unpublished, no hardcoded rung.

All student/cohort/consent values below are **synthetic fixtures**, not real
data. ``repo_inputs()`` reads the committed gold; the fixtures never touch it.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from ai.moodle_readiness import (
    Cohort,
    ConsentRecord,
    GateReason,
    NoticeDraftError,
    NoticeRegistry,
    ReadinessInputs,
    StudentSurfaceContext,
    consult_student_surface,
    evaluate,
    repo_inputs,
)
from ai.moodle_readiness.evaluator import PLUGIN_VERSION_MIN

BACKEND = Path(__file__).resolve().parents[2]

COURSE = "NMD1103"
STUDENT = "fixture-student-1"
COHORT_ID = "fixture-cohort"


def _consent(*, granted: bool = True, course: str = COURSE, policy_version: int = 1) -> ConsentRecord:
    return ConsentRecord(
        subject_id=STUDENT,
        course_shortname=course,
        policy_version=policy_version,
        granted=granted,
        granted_at="2026-01-01T00:00:00Z" if granted else None,
    )


def _allow_context(**overrides) -> StudentSurfaceContext:
    """A fixture that satisfies every gate. Tests remove one field at a time."""
    base = dict(
        user_id=STUDENT,
        course_shortname=COURSE,
        cohort=Cohort(staff_ids=frozenset({"fixture-staff"}), student_ids=frozenset({STUDENT})),
        consent=_consent(),
        enabled_courses=frozenset({COURSE}),
        can_open_course=True,
        l5_passable=True,
        student_notice_published=True,
        policy_version=1,
    )
    base.update(overrides)
    return StudentSurfaceContext(**base)


# ── Gate ─────────────────────────────────────────────────────────────────────


def test_gate_defaults_to_deny():
    decision = consult_student_surface(StudentSurfaceContext())
    assert decision.allowed is False
    assert decision.reason is GateReason.COURSE_NOT_LISTED
    assert not decision  # falsy


def test_gate_allows_only_when_every_artifact_present():
    decision = consult_student_surface(_allow_context())
    assert decision.allowed is True
    assert decision.reason is GateReason.ALLOW


@pytest.mark.parametrize(
    "overrides,reason",
    [
        ({"enabled_courses": frozenset()}, GateReason.COURSE_NOT_LISTED),
        ({"cohort": Cohort()}, GateReason.STUDENT_COHORTS_EMPTY),
        ({"cohort": Cohort(student_ids=frozenset({"someone-else"}))}, GateReason.NOT_IN_STUDENT_COHORT),
        ({"l5_passable": False}, GateReason.L5_NOT_PASSABLE),
        ({"student_notice_published": False}, GateReason.STUDENT_NOTICE_UNPUBLISHED),
        ({"can_open_course": False}, GateReason.COURSE_NOT_OPENABLE),
        ({"consent": None}, GateReason.NO_CONSENT),
        ({"consent": _consent(granted=False)}, GateReason.CONSENT_REVOKED),
        ({"consent": _consent(course="MED520")}, GateReason.CONSENT_COURSE_MISMATCH),
        ({"consent": _consent(policy_version=9)}, GateReason.CONSENT_POLICY_STALE),
    ],
)
def test_gate_denies_each_missing_artifact_with_a_typed_reason(overrides, reason):
    assert consult_student_surface(_allow_context(**overrides)).reason is reason


def test_gate_student_cohorts_empty_blocks_before_membership():
    ctx = _allow_context(cohort=Cohort(student_ids=frozenset({STUDENT})))
    assert ctx.cohort.students_empty is False
    empty = _allow_context(cohort=Cohort())
    assert empty.cohort.students_empty is True
    assert consult_student_surface(empty).reason is GateReason.STUDENT_COHORTS_EMPTY


# ── Notices ──────────────────────────────────────────────────────────────────


def test_notice_registry_defaults_unpublished():
    registry = NoticeRegistry()
    assert registry.is_published("staff") is False
    assert registry.is_published("student") is False
    assert registry.get("staff").published_at is None
    assert registry.get("staff").shortnames == ()


def test_notice_publish_requires_cohort_and_shortnames():
    registry = NoticeRegistry()
    with pytest.raises(NoticeDraftError):
        registry.publish("staff", cohort_idnumbers=(), shortnames=("NMD1103",),
                         does_not=registry.get("staff").does_not, published_at="t")
    with pytest.raises(NoticeDraftError):
        registry.publish("staff", cohort_idnumbers=("c1",), shortnames=(),
                         does_not=registry.get("staff").does_not, published_at="t")


def test_notice_publish_requires_r18_clauses():
    registry = NoticeRegistry()
    with pytest.raises(NoticeDraftError):
        registry.publish("staff", cohort_idnumbers=("c1",), shortnames=("NMD1103",),
                         does_not=("no_grade",), published_at="t")


def test_notice_publish_then_unpublish_round_trip():
    from ai.moodle_readiness import REQUIRED_DOES_NOT

    registry = NoticeRegistry()
    notice = registry.publish(
        "staff",
        cohort_idnumbers=("fixture-cohort",),
        shortnames=("NMD1103",),
        does_not=REQUIRED_DOES_NOT,
        published_at="2026-01-01T00:00:00Z",
    )
    assert notice.published is True
    assert registry.is_published("staff") is True
    registry.unpublish("staff")
    assert registry.is_published("staff") is False
    # The student notice is a separate decision and stays unpublished.
    assert registry.is_published("student") is False


# ── Evaluator ────────────────────────────────────────────────────────────────


def test_evaluator_is_not_pass_on_empty_inputs():
    report = evaluate(ReadinessInputs())
    assert report.by_id["K10"].passed is False
    assert report.by_id["K11"].passed is False
    assert report.by_id["B5"].passed is False
    assert report.by_id["B6"].passed is False
    assert report.by_id["C7"].passed is False


def test_evaluator_k10_pass_only_when_all_staff_artifacts_present():
    report = evaluate(ReadinessInputs(
        production_installed=True,
        plugin_version=PLUGIN_VERSION_MIN,
        hmac_configured=True,
        staff_cohorts_non_empty=True,
        listed_courses_all_have_c6_gold=True,
        staff_notice_published=True,
    ))
    assert report.by_id["K10"].passed is True
    assert report.by_id["K11"].passed is False  # students are a separate decision


def test_evaluator_k11_pass_only_when_all_student_artifacts_present():
    report = evaluate(ReadinessInputs(
        l5_status="passable",
        l5_sample_size=100,
        l5_min_passage_cite=95,
        l5_max_extra_fact=2,
        r11_frozen_n=4,
        r12_frozen_n=2,
        student_notice_published=True,
        student_cohorts_non_empty=True,
        consent_gate_present=True,
        rbac_path_present=True,
        audit_path_present=True,
    ))
    assert report.by_id["K11"].passed is True


@pytest.mark.parametrize(
    "field",
    [
        "student_notice_published",
        "student_cohorts_non_empty",
        "consent_gate_present",
        "rbac_path_present",
        "audit_path_present",
    ],
)
def test_k11_flips_to_not_pass_when_one_artifact_is_missing(field):
    full = dict(
        l5_status="passable", l5_sample_size=100, l5_min_passage_cite=95,
        l5_max_extra_fact=2, r11_frozen_n=4, r12_frozen_n=2,
        student_notice_published=True, student_cohorts_non_empty=True,
        consent_gate_present=True, rbac_path_present=True, audit_path_present=True,
    )
    full[field] = False
    assert evaluate(ReadinessInputs(**full)).by_id["K11"].passed is False


def test_evaluator_b5_requires_cohort_consent_audit_and_r12():
    base = dict(
        memory_long_store_present=True,
        student_cohorts_non_empty=True,
        consent_gate_present=True,
        audit_path_present=True,
        r12_frozen_n=2,
    )
    assert evaluate(ReadinessInputs(**base)).by_id["B5"].passed is True
    for field in ("memory_long_store_present", "student_cohorts_non_empty",
                  "consent_gate_present", "audit_path_present"):
        broken = dict(base)
        broken[field] = False
        assert evaluate(ReadinessInputs(**broken)).by_id["B5"].passed is False


def test_evaluator_c7_requires_c6_and_l5():
    full = dict(c6_green_all_listed=True, l5_status="passable", c7_edges_built=True)
    assert evaluate(ReadinessInputs(**full)).by_id["C7"].passed is True
    no_l5 = dict(full, l5_status="not_passable")
    assert evaluate(ReadinessInputs(**no_l5)).by_id["C7"].passed is False
    no_c6 = dict(full, c6_green_all_listed=False)
    assert evaluate(ReadinessInputs(**no_c6)).by_id["C7"].passed is False


def test_evaluator_b6_needs_graph_and_c6():
    assert evaluate(ReadinessInputs(graph_present=True, c6_green_all_listed=True)).by_id["B6"].passed is True
    assert evaluate(ReadinessInputs(graph_present=True)).by_id["B6"].passed is False


# ── Real repository state (no hardcoded rung) ────────────────────────────────


def test_repo_inputs_reads_gold_not_a_hardcoded_status():
    inputs = repo_inputs()
    assert inputs.l5_status == "passable"
    assert inputs.l5_sample_size == 100
    assert inputs.l5_min_passage_cite == 95
    assert inputs.l5_max_extra_fact == 2
    assert inputs.r11_frozen_n == 4
    assert inputs.r12_frozen_n == 2
    # The pilot cohort/consent/audit are NOT read from the bare repo: without
    # the pilot mirror, students stay off (default deny).
    assert inputs.student_cohorts_non_empty is False


def test_repo_report_keeps_students_and_graph_not_pass():
    report = evaluate(repo_inputs())
    assert report.by_id["K10"].passed is False
    assert report.by_id["K11"].passed is False
    assert report.by_id["B5"].passed is False
    assert report.by_id["B6"].passed is False
    assert report.by_id["C7"].passed is False


def test_b4_is_an_input_that_flips():
    assert evaluate(repo_inputs()).by_id["B4"].passed is True
    assert evaluate(repo_inputs(memory_short_typed=False)).by_id["B4"].passed is False


# ── Default-OFF proof ────────────────────────────────────────────────────────


def test_turn_path_never_names_readiness():
    roots = [
        BACKEND / "ai" / "moodle_host.py",
        BACKEND / "ai" / "moodle_page.py",
        BACKEND / "ai" / "moodle_host_api.py",
        BACKEND / "ai" / "moodle_bank.py",
        BACKEND / "ai" / "moodle_integrity.py",
        BACKEND / "ai" / "moodle_refusals.py",
        BACKEND / "ai" / "moodle_onboarding.py",
    ]
    for path in roots:
        assert "moodle_readiness" not in path.read_text(encoding="utf-8"), path
    for path in (BACKEND / "ai" / "engine").rglob("*.py"):
        assert "moodle_readiness" not in path.read_text(encoding="utf-8"), path


def test_host_import_does_not_pull_readiness():
    code = (
        "import sys, ai.moodle_host; "
        "leaked = [m for m in sys.modules if 'moodle_readiness' in m]; "
        "assert not leaked, leaked"
    )
    result = subprocess.run([sys.executable, "-c", code], cwd=BACKEND, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_readiness_import_is_django_free():
    code = (
        "import sys, ai.moodle_readiness; "
        "assert 'django' not in sys.modules, 'readiness pulled Django in'"
    )
    result = subprocess.run([sys.executable, "-c", code], cwd=BACKEND, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_normal_ask_turn_is_unchanged():
    from ai.moodle_host import prepare_ask

    listed = {
        "audience": "staff",
        "courseid": 11,
        "enrolled": True,
        "course": {"id": 11, "shortname": COURSE, "fullname": "Clinical Skills 1", "visible_to_user": True},
        "sections": [{"number": 1, "name": "Week 1", "visible": True}],
    }
    decision = prepare_ask({
        "pulse_mode": "ask",
        "message": "What is this course called?",
        "snapshot": listed,
        "host_context": {"audience": "staff", "courseid": 11},
        "moodle_user_id": 7,
    })
    assert decision.error is None
    assert decision.refusal is None
    assert decision.chat is None or decision.chat.get("process_mode") == "ask"
