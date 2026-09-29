"""Control-room boards stay bounded to their evidence."""
from excellence.control_room import build_control_room


def test_control_room_keeps_unmeasured_cells_and_separates_scopes():
    room = build_control_room()
    assert [item["id"] for item in room["domains"]] == ["pulse", "nibras"]
    ask = room["cells"]["pulse"]["readiness"]["ask"]
    assert ask["correct"]["state"] in {"reached", "partial", "fail", "missing"}
    assert ask["continuous"]["state"] in {"fail", "partial", "missing", "unmeasured"}
    assert room["cells"]["pulse"]["readiness"]["memory"]["fast"]["state"] == "unmeasured"
    assert "Lab evidence" in room["cells"]["pulse"]["readiness"]["plan-lab"]["proven"]["limit"]
    production = room["cells"]["pulse"]["readiness"]["plan-prod"]["proven"]
    assert production["state"] in {"fail", "missing", "unmeasured"}
    assert "full run" in production["limit"] or production["state"] == "unmeasured"
    assert room["cells"]["nibras"]["readiness"]["stores"]["correct"]["state"] == "absent"
    assert room["cells"]["nibras"]["actualization"]["stores"]["configured"]["state"] == "missing"
    assert room["cells"]["nibras"]["readiness"]["people"]["proven"]["state"] == "partial"
    assert {item["id"] for item in room["definitions"]} >= {"readiness", "actualization", "unknown"}
