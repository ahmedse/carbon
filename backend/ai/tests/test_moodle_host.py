"""Moodle host seam. The live door calls dispatch_task; these checks do not."""
import hashlib
import hmac

from ai.moodle_host import (
    INSTANCE_ID,
    chat_payload,
    page_context_from_snapshot,
    reject_dial,
    verify_signature,
)

_SNAPSHOT = {
    "audience": "staff",
    "courseid": 11,
    "enrolled": True,
    "course": {
        "id": 11,
        "shortname": "NMD1103",
        "fullname": "Clinical Skills 1",
        "category": "Semester 1",
        "format": "weeks",
        "visible_to_user": True,
    },
    "sections": [{"number": 1, "name": "Week 1", "visible": True}],
}


def test_plan_and_agent_are_rejected():
    assert reject_dial("ask") is None
    assert reject_dial(None) is None
    assert reject_dial("plan") == "ask_only"
    assert reject_dial("agent") == "ask_only"


def test_hmac_round_trip():
    secret = "test-secret"
    body = b'{"pulse_mode":"ask"}'
    ts = "1700000000"
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    assert verify_signature(secret, ts, body, sig, now=1700000000)
    assert not verify_signature(secret, ts, body, sig, now=1700000200)
    assert not verify_signature("other", ts, body, sig, now=1700000000)


def test_chat_payload_is_ask_on_aast_med_page():
    payload = chat_payload(
        "What is on this page?",
        {"audience": "staff", "courseid": 11},
        _SNAPSHOT,
        42,
    )
    assert INSTANCE_ID == "aast-med"
    assert payload["process_mode"] == "ask"
    assert payload["host_user_id"] == "moodle:42"
    assert payload["app_identifier"] == "moodle"
    assert "NMD1103" in payload["page_context"]
    assert "Week 1" in payload["page_context"]
    assert payload["message"] == "What is on this page?"
    assert "NMD1103" not in payload["message"]


def test_inventory_is_opt_in_per_pack():
    from ai.engine.cognition.turn.capability import (
        inventory_provider,
        tool_capabilities,
        wants_platform_inventory,
    )
    from ai.engine_runtime import _instance_config

    assert inventory_provider("aast-med") == ""
    assert inventory_provider("nibras") == "host_rbac"
    assert inventory_provider("carbon") == "host_rbac"
    assert inventory_provider("eduos") == "host_rbac"
    assert wants_platform_inventory({}) is False
    assert wants_platform_inventory({"inventory": "host_rbac"}) is True

    medicine = _instance_config("aast-med", "moodle-2")
    assert medicine["instance_id"] == "aast-med"
    assert medicine["app_identifier"] == "moodle"
    assert medicine["user_access"] == {}
    assert medicine["inventory"] == ""
    surfaced = {entry["name"] for entry in tool_capabilities(medicine)}
    assert "list_my_capabilities" not in surfaced

    people = _instance_config("nibras", None)
    assert people["inventory"] == "host_rbac"
    assert "apps" in people["user_access"]


def test_hidden_course_is_a_refusal_context():
    text = page_context_from_snapshot(
        {"audience": "student"},
        {"course": {"shortname": "QB", "visible_to_user": False}, "sections": []},
    )
    assert "cannot see" in text
    assert "QB" not in text
