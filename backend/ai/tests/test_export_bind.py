"""Unit tests for deterministic export_document arg binding (RULE_20 pure)."""

from __future__ import annotations

import json

from ai.engine.cognition.plan.export_bind import (
    apply_bind_to_tool_calls,
    bind_export_args,
    content_is_placeholder,
    extract_structured_facts,
)


def test_content_is_placeholder_detects_stubs():
    assert content_is_placeholder("") is True
    assert content_is_placeholder("[Placeholder for insights]") is True
    assert content_is_placeholder("## Findings\n[Chart and table to be inserted]") is True
    assert content_is_placeholder("## Findings\n- Saudis average 12k") is False


def test_extract_structured_facts_from_code_execute():
    payload = {
        "tool_name": "code_execute",
        "result": json.dumps({
            "stdout": "ok",
            "image_b64": "a" * 200,
            "table_rows": [
                {"nationality": "Saudi", "avg": 12000},
                {"nationality": "Indian", "avg": 8000},
            ],
        }),
    }
    facts = extract_structured_facts(payload)
    assert facts["tables"]
    assert facts["tables"][0]["headers"] == ["nationality", "avg"]
    assert len(facts["images"]) == 1
    assert facts["images"][0]["image_b64"].startswith("aaa")


def test_extract_structured_facts_from_host_api_breakdown():
    payload = {
        "result": {
            "breakdown": [
                {"label": "Heavy Duty Driver", "count": 40},
                {"label": "Floorman", "count": 22},
            ],
        },
    }
    facts = extract_structured_facts(payload)
    assert facts["tables"]
    assert "label" in facts["tables"][0]["headers"]


def test_bind_export_args_fills_placeholder_from_priors():
    prior = [{
        "draft_text": "Saudi nationals earn more on average than contractors.",
        "tool_output": {
            "result": {
                "table_rows": [
                    {"nationality": "Saudi", "avg": 12000},
                    {"nationality": "Indian", "avg": 8000},
                ],
                "image_b64": "iVBORw0KGgo" + ("A" * 180),
            },
        },
    }]
    bound = bind_export_args(
        {
            "title": "Salary Distribution Analysis at GOFSCO",
            "format": "docx",
            "content": "[Placeholder for insights]\n[Chart and table to be inserted]",
        },
        prior,
    )
    assert content_is_placeholder(bound["content"]) is False
    assert "Saudi" in bound["content"] or "nationality" in bound["content"].lower()
    assert bound["table"]["headers"] == ["nationality", "avg"]
    assert bound["images"]
    assert "image_b64" in bound["images"][0]


def test_bind_keeps_real_llm_content():
    prior = [{
        "tool_output": {
            "result": {"table_rows": [{"a": 1}]},
        },
    }]
    bound = bind_export_args(
        {
            "title": "Report",
            "content": "## Key findings\n- Measured headcount rose 4%.",
            "table": {"headers": ["x"], "rows": [["1"]]},
        },
        prior,
    )
    assert "Measured headcount" in bound["content"]
    assert bound["table"]["headers"] == ["x"]


def test_apply_bind_to_tool_calls_and_synth_when_missing():
    prior = [{
        "tool_output": {
            "result": {"table_rows": [{"dim": "A", "n": 3}]},
        },
        "draft_text": "Dimension A leads.",
    }]
    calls = apply_bind_to_tool_calls(
        [{
            "id": "1",
            "function": {
                "name": "export_document",
                "arguments": json.dumps({
                    "title": "T",
                    "format": "docx",
                    "content": "[Placeholder]",
                }),
            },
        }],
        prior,
    )
    args = json.loads(calls[0]["function"]["arguments"])
    assert args["table"]["headers"] == ["dim", "n"]

    synth = apply_bind_to_tool_calls(
        [],
        prior,
        step_tool_name="export_document",
        step_tool_args={"format": "docx", "title": "Synth"},
    )
    assert len(synth) == 1
    assert synth[0]["function"]["name"] == "export_document"
    synth_args = json.loads(synth[0]["function"]["arguments"])
    assert synth_args["table"]
