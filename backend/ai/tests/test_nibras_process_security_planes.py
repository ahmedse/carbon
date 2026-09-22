"""Honesty matrix: Nibras process SoD claims vs host enforcement (ADR-0045).

Process YAML ``separation_of_duties`` / ``refuse_if`` are dial contracts.
This test locks the documented security planes so SCOREBOARD/README cannot
claim host role-SoD where only Pulse dials exist.

When host SoD ships for a process, update ``HOST_SOD_PLANE`` here and ADR-0045
in the same change — never flip the claim without the host gate.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from django.conf import settings

from ai.engine.ports.domain import load_domain_pack

PACK_DIR = Path(settings.BASE_DIR).parent / "domain_packs" / "nibras"

# plane: "correspondence" | "host_gate" | "dial_only"
HOST_SOD_PLANE: dict[str, str] = {
    "leave.request.lifecycle": "correspondence",
    "loan.request.lifecycle": "correspondence",
    "payroll.run.lifecycle": "host_gate",
    "gosi_wps.sif.lifecycle": "host_gate",
    "employee.onboarding.lifecycle": "host_gate",
    "attendance.permission.lifecycle": "correspondence",
}


def _pack():
    return load_domain_pack(PACK_DIR)


def _doc(process_id: str) -> dict:
    return dict(next(p for p in _pack().processes() if p.get("id") == process_id))


@pytest.mark.parametrize("process_id,plane", sorted(HOST_SOD_PLANE.items()))
def test_honesty_matrix_covers_every_active_process(process_id, plane):
    assert plane in ("correspondence", "dial_only", "host_gate")
    doc = _doc(process_id)
    assert doc.get("id") == process_id
    human = [s for s in doc["steps"] if s.get("autonomy") == "human_only"]
    if human:
        assert any(
            (s.get("separation_of_duties") or []) for s in human
        ), f"{process_id}: human_only step without SoD roles"


def test_no_process_outside_honesty_matrix():
    known = {p.get("id") for p in _pack().processes()}
    assert known == set(HOST_SOD_PLANE), (
        "Update ADR-0045 + HOST_SOD_PLANE when adding/removing Nibras processes. "
        f"pack={sorted(known)} matrix={sorted(HOST_SOD_PLANE)}"
    )


def test_no_dial_only_rows_remain_after_nps1():
    """NPS-1 closed admin irreversibles; dial_only must stay empty unless new gaps."""
    dial = [pid for pid, plane in HOST_SOD_PLANE.items() if plane == "dial_only"]
    assert dial == [], f"Unexpected dial_only rows (update ADR-0045): {dial}"


@pytest.mark.parametrize(
    "process_id",
    [pid for pid, plane in HOST_SOD_PLANE.items() if plane == "host_gate"],
)
def test_host_gate_processes_keep_sod_dials(process_id):
    """Host-gated irreversibles still declare YAML SoD (dials + host)."""
    doc = _doc(process_id)
    human = [s for s in doc["steps"] if s.get("autonomy") == "human_only"]
    assert human, f"{process_id}: expected human_only gate"
    assert any(len(s.get("separation_of_duties") or []) >= 2 for s in human)


@pytest.mark.parametrize(
    "process_id",
    [pid for pid, plane in HOST_SOD_PLANE.items() if plane == "correspondence"],
)
def test_correspondence_plane_processes_keep_sod_dials(process_id):
    doc = _doc(process_id)
    review = next(s for s in doc["steps"] if s["id"] == "review")
    assert review["autonomy"] == "human_only"
    assert review.get("separation_of_duties") == ["requester", "approver"]


def test_adr_0045_exists():
    adr = (
        Path(settings.BASE_DIR).parent
        / ".ai-toolkit"
        / "decisions"
        / "0045-nibras-process-security-planes.md"
    )
    assert adr.is_file()
    text = adr.read_text(encoding="utf-8")
    assert "Host HR" in text or "Plane A" in text
    assert "host_gate" in text or "people.governance.sod" in text
    assert "Forbidden shortcuts" in text
