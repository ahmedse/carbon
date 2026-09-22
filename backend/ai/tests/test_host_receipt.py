"""Host navigate receipt — shared Chat + Agent Output contract."""
from ai.host_receipt import (
    attach_receipt,
    collect_navigate_actions,
    correspondence_navigate_receipt,
    format_actions_markdown,
    navigate_receipt,
)


def test_correspondence_receipt_deep_links_request():
    receipt = correspondence_navigate_receipt(
        {
            "id": 42,
            "reference_no": "CRS-2026-0099",
            "corr_type_label": "Leave request",
            "title": "Leave request annual 2026-09-22→2026-09-22",
            "status": "submitted",
            "payload": {
                "leave_type": "annual",
                "start_date": "2026-09-22",
                "end_date": "2026-09-22",
                "days": "1.00",
            },
        },
    )
    assert receipt["action"] == "navigate"
    assert receipt["route"] == "/my/requests/42"
    assert "Leave request" in receipt["label"]
    assert "CRS-2026-0099" in receipt["summary"]


def test_attach_receipt_is_top_level_for_chat_derive():
    result = attach_receipt(
        {"status_code": 201, "data": {"id": 7}},
        navigate_receipt(
            route="/my/requests/7",
            label="Open request",
            summary="ref CRS-1",
        ),
    )
    assert result["status_code"] == 201
    assert result["action"] == "navigate"
    assert result["route"] == "/my/requests/7"


def test_collect_navigate_actions_from_host_wrap():
    actions = collect_navigate_actions([
        {
            "status_code": 201,
            "data": {"id": 1},
            "action": "navigate",
            "route": "/my/requests/1",
            "label": "Open leave request",
            "summary": "annual · 2026-09-22",
        },
    ])
    assert actions == [{
        "type": "navigate",
        "route": "/my/requests/1",
        "label": "Open leave request",
        "summary": "annual · 2026-09-22",
    }]
    md = format_actions_markdown(actions)
    assert "/my/requests/1" in md
    assert "Open leave request" in md
