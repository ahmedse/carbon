"""Contract + parser + service tests for the Answer Envelope (PAQ-2A).

Deterministic and fully offline: no live LLM is ever called — ``route_chat``
is monkeypatched wherever the service / synthesis path would otherwise hit the
provider.
"""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

import ai.engine.cognition.turn.runner as runner_mod
import ai.engine.llm.router as router_mod
from ai.envelope import envelope_from_json, envelope_json_schema
from ai.envelope_prompt import build_envelope_system_prompt
from ai.envelope_service import enrich_envelope_charts, synthesize_envelope


# ── fixtures / helpers ──────────────────────────────────────────────────────

_VALID_ENVELOPE = {
    "headline": "Male employees outnumber female employees 6 to 2.",
    "prose": [
        "Here is a **bold** summary of the distribution.",
        "A second short paragraph with *emphasis*.",
    ],
    "tables": [
        {
            "title": "Gender breakdown",
            "columns": ["Gender", "Employees"],
            "rows": [["male", 6], ["female", 2]],
        }
    ],
    "charts": [
        {
            "chart_type": "bar",
            "title": "Employees by gender",
            "series": [{"name": "Employees", "data": [["male", 6], ["female", 2]]}],
        }
    ],
    "caveats": [
        {"level": "warning", "text": "8% have no gender recorded."},
    ],
    "sources": [
        {"tool": "analyze_employees", "rows_returned": 2, "truncated": False},
    ],
}


def _envelope(**overrides) -> dict:
    env = deepcopy(_VALID_ENVELOPE)
    env.update(overrides)
    return env


def _stub_route_chat(monkeypatch, content: str):
    """Stub the LLM router to return a fixed ``content`` string."""

    async def fake_route_chat(**kwargs):
        return {
            "content": content,
            "input_tokens": 10,
            "output_tokens": 20,
            "model": "test-model",
        }

    monkeypatch.setattr(router_mod, "route_chat", fake_route_chat)


def _set_envelope_flag(monkeypatch, enabled: bool):
    monkeypatch.setattr(
        runner_mod, "get_settings",
        lambda: SimpleNamespace(PULSE_ENVELOPE_ENABLED=enabled),
    )


# ── envelope_from_json — round-trip / fences ────────────────────────────────

def test_envelope_from_json_round_trips_full_envelope():
    env = envelope_from_json(json.dumps(_VALID_ENVELOPE))
    assert env.headline == _VALID_ENVELOPE["headline"]
    assert len(env.prose) == 2
    assert env.tables[0].title == "Gender breakdown"
    assert env.tables[0].rows == [["male", 6], ["female", 2]]
    assert env.charts[0].chart_type == "bar"
    assert env.caveats[0].level == "warning"
    assert env.sources[0].tool == "analyze_employees"


def test_envelope_from_json_strips_json_fences():
    raw = "```json\n" + json.dumps(_VALID_ENVELOPE) + "\n```"
    env = envelope_from_json(raw)
    assert env.headline == _VALID_ENVELOPE["headline"]
    assert env.tables[0].rows == [["male", 6], ["female", 2]]


# ── validation REJECTS ──────────────────────────────────────────────────────

def test_rejects_row_length_mismatch():
    env = _envelope(tables=[{
        "title": "bad", "columns": ["a", "b"], "rows": [["only-one", 1, "extra"]],
    }])
    with pytest.raises(ValueError):
        envelope_from_json(json.dumps(env))


def test_rejects_markdown_bold_in_table_cell():
    env = _envelope(tables=[{
        "title": "bad", "columns": ["a", "b"], "rows": [["**male**", 6]],
    }])
    with pytest.raises(ValueError):
        envelope_from_json(json.dumps(env))


def test_rejects_markdown_pipe_in_table_cell():
    env = _envelope(tables=[{
        "title": "bad", "columns": ["a", "b"], "rows": [["a|b", 6]],
    }])
    with pytest.raises(ValueError):
        envelope_from_json(json.dumps(env))


def test_rejects_unknown_chart_type():
    env = _envelope(charts=[{
        "chart_type": "donut", "title": "x", "series": [],
    }])
    with pytest.raises(ValueError):
        envelope_from_json(json.dumps(env))


def test_rejects_data_blocks_without_sources():
    env = _envelope(sources=[])
    with pytest.raises(ValueError):
        envelope_from_json(json.dumps(env))


def test_rejects_invalid_json():
    with pytest.raises(ValueError):
        envelope_from_json("{ this is not valid json")


# ── schema / prompt ─────────────────────────────────────────────────────────

def test_envelope_json_schema_has_top_level_keys():
    schema = envelope_json_schema()
    assert isinstance(schema, dict)
    properties = schema["properties"]
    for key in ("headline", "prose", "tables", "charts", "caveats", "sources"):
        assert key in properties
    assert "headline" in schema["required"]
    assert "prose" in schema["required"]


def test_build_envelope_system_prompt_mentions_keys_and_chart_rule():
    prompt = build_envelope_system_prompt()
    for key in ("headline", "prose", "tables", "charts", "caveats", "sources"):
        assert key in prompt
    assert "suggested_chart_type" in prompt
    assert "aggregate_entity" in prompt
    assert "empty `series`" in prompt
    assert "single-bar" in prompt or "≥2 categories" in prompt


# ── enrich_envelope_charts (drop empty / single-point) ──────────────────────

def test_enrich_drops_empty_series_even_with_scalar():
    """Single-metric bars are never worth shipping — prose carries the scalar."""
    raw = _envelope(
        headline="We have 530 active employees.",
        prose=["Active headcount grounded on is_active=True."],
        tables=[],
        charts=[{
            "chart_type": "bar",
            "title": "Active Employee Count",
            "series": [],
        }],
        sources=[{"tool": "aggregate_entity", "rows_returned": 1, "truncated": False}],
    )
    env = envelope_from_json(json.dumps(raw))
    usable = [{
        "tool_name": "aggregate_entity",
        "result": {
            "metric": "headcount",
            "value": 530,
            "description": "Total active employees",
            "filter": {"is_active": True},
            "entity_type": "employee",
            "cited_fields": ["is_active"],
        },
    }]
    enriched = enrich_envelope_charts(env, usable)
    assert enriched.charts == []


def test_enrich_drops_empty_chart_without_scalar():
    raw = _envelope(
        tables=[],
        charts=[{
            "chart_type": "bar",
            "title": "Active Employee Count",
            "series": [],
        }],
        sources=[{"tool": "analyze_employees", "rows_returned": 0, "truncated": False}],
    )
    env = envelope_from_json(json.dumps(raw))
    enriched = enrich_envelope_charts(env, [{"tool_name": "x", "result": {"rows": []}}])
    assert enriched.charts == []


def test_enrich_drops_single_point_and_does_not_synthesise():
    raw = _envelope(
        headline="We have 530 active employees.",
        prose=["Grounded on aggregate_entity."],
        tables=[],
        charts=[{
            "chart_type": "bar",
            "title": "Total active employees",
            "series": [{"name": "Total", "data": [["Total active employees", 530]]}],
        }],
        sources=[{"tool": "aggregate_entity", "rows_returned": 1, "truncated": False}],
    )
    env = envelope_from_json(json.dumps(raw))
    usable = [{
        "tool_name": "aggregate_entity",
        "result": {
            "metric": "headcount",
            "value": 530,
            "description": "Total active employees",
        },
    }]
    enriched = enrich_envelope_charts(env, usable)
    assert enriched.charts == []


def test_enrich_keeps_multi_bucket_chart():
    raw = _envelope(
        tables=[],
        charts=[{
            "chart_type": "bar",
            "title": "By status",
            "series": [{"name": "Runs", "data": [
                ["Committed", 16], ["Draft", 2], ["Failed", 2],
            ]}],
        }],
        sources=[{"tool": "analyze_payroll", "rows_returned": 3, "truncated": False}],
    )
    env = envelope_from_json(json.dumps(raw))
    enriched = enrich_envelope_charts(env, [])
    assert len(enriched.charts) == 1


def test_enrich_injects_charts_from_analyze_breakdown():
    """Transcript bug: tables present, charts=[], despite multi-bucket analyze_*."""
    raw = _envelope(
        headline="555 active employees across departments.",
        prose=["Drilling leads headcount."],
        tables=[{
            "title": "Headcount by Department",
            "columns": ["Unit", "Count"],
            "rows": [["Drilling", 133], ["Coiled Tubing", 93]],
        }],
        charts=[],
        sources=[{"tool": "call_host_api", "rows_returned": 16, "truncated": True}],
    )
    env = envelope_from_json(json.dumps(raw))
    usable = [{
        "tool_name": "call_host_api",
        "result": {
            "status_code": 200,
            "data": {
                "dimension": "org_unit",
                "suggested_chart_type": "bar",
                "breakdown": [
                    {"label": "Drilling", "count": 133, "pct": 24.0},
                    {"label": "Coiled Tubing", "count": 93, "pct": 16.8},
                    {"label": "PCP", "count": 52, "pct": 9.4},
                ],
            },
        },
    }]
    enriched = enrich_envelope_charts(env, usable)
    assert len(enriched.charts) == 1
    assert enriched.charts[0].chart_type == "bar"
    series = enriched.charts[0].series or []
    points = (series[0].get("data") if series else None) or []
    assert len(points) >= 2
    assert points[0][0] == "Drilling"


def test_sanitize_drops_sample_payslip_table():
    from ai.envelope_service import sanitize_envelope_tables

    raw = _envelope(
        tables=[
            {
                "title": "Payroll Run Status Summary",
                "columns": ["Status", "Count"],
                "rows": [["Committed", 16], ["Draft", 2]],
            },
            {
                "title": "Sample Payslip Line Items (First 10 Employees)",
                "columns": ["EMPLOYEE NAME", "EMPLOYEE NO", "GROSS", "GOSI/PIFSS", "NET"],
                "rows": [["Wellie", "1001", 420, 0, -853]],
            },
        ],
    )
    env = envelope_from_json(json.dumps(raw))
    cleaned = sanitize_envelope_tables(env)
    assert len(cleaned.tables) == 1
    assert cleaned.tables[0].title == "Payroll Run Status Summary"


@pytest.mark.asyncio
async def test_synthesize_envelope_drops_empty_headcount_chart(monkeypatch):
    """End-to-end: LLM empty/single series → no chart shipped."""
    llm_payload = _envelope(
        headline="We have 530 active employees.",
        prose=["Active employees only."],
        tables=[],
        charts=[{
            "chart_type": "bar",
            "title": "Active Employee Count",
            "series": [],
        }],
        sources=[{"tool": "aggregate_entity", "rows_returned": 1, "truncated": False}],
    )
    _stub_route_chat(monkeypatch, json.dumps(llm_payload))
    env = await synthesize_envelope(
        instance_id="i",
        conversation_id="c",
        user_message="how many active employees?",
        usable_tools=[{
            "tool_name": "aggregate_entity",
            "result": {
                "metric": "headcount",
                "value": 530,
                "description": "Total active employees",
            },
        }],
    )
    assert env is not None
    assert env.charts == []
    assert "530" in env.headline


# ── synthesize_envelope (async, mocked LLM) ─────────────────────────────────

@pytest.mark.asyncio
async def test_synthesize_envelope_returns_populated_envelope(monkeypatch):
    _stub_route_chat(monkeypatch, json.dumps(_VALID_ENVELOPE))
    env = await synthesize_envelope(
        instance_id="i",
        conversation_id="c",
        user_message="what is the gender breakdown?",
        usable_tools=[{
            "tool_name": "analyze_employees",
            "result": {"status_code": 200, "data": {
                "breakdown": [], "suggested_chart_type": "bar",
            }},
        }],
    )
    assert env is not None
    assert env.headline == _VALID_ENVELOPE["headline"]
    assert env.tables[0].title == "Gender breakdown"
    assert env.sources[0].tool == "analyze_employees"


@pytest.mark.asyncio
async def test_synthesize_envelope_invalid_json_returns_none(monkeypatch):
    _stub_route_chat(monkeypatch, "### not json at all")
    env = await synthesize_envelope(
        instance_id="i",
        conversation_id="c",
        user_message="what is the gender breakdown?",
        usable_tools=[{
            "tool_name": "analyze_employees",
            "result": {"status_code": 200, "data": {"breakdown": []}},
        }],
    )
    assert env is None


@pytest.mark.asyncio
async def test_synthesize_envelope_no_usable_tools_returns_none():
    # No route_chat stub here: the service must short-circuit before any LLM call.
    env = await synthesize_envelope(
        instance_id="i",
        conversation_id="c",
        user_message="hi",
        usable_tools=[{"tool_name": "x", "result": None, "error": "boom"}],
    )
    assert env is None


# ── flag gating in _synthesize_tool_results ─────────────────────────────────

@pytest.mark.asyncio
async def test_flag_off_returns_no_envelope_key(monkeypatch):
    _set_envelope_flag(monkeypatch, enabled=False)
    _stub_route_chat(monkeypatch, "Here is the **markdown** answer with real values.")
    result = await runner_mod._synthesize_tool_results(
        instance_id="i",
        conversation_id="c",
        user_message="what is the gender breakdown?",
        completed_tools=[{
            "tool_name": "analyze_employees",
            "result": {"status_code": 200, "data": {"breakdown": []}},
        }],
        draft_text="",
        envelope_synthesizer=synthesize_envelope,
    )
    assert result is not None
    assert "text" in result
    assert "envelope" not in result


@pytest.mark.asyncio
async def test_flag_on_attaches_envelope_alongside_markdown(monkeypatch):
    _set_envelope_flag(monkeypatch, enabled=True)

    async def fake_route_chat(**kwargs):
        if kwargs.get("response_format"):
            return {
                "content": json.dumps(_VALID_ENVELOPE),
                "input_tokens": 10, "output_tokens": 20, "model": "test-model",
            }
        return {
            "content": "Here is the **markdown** answer.",
            "input_tokens": 10, "output_tokens": 20, "model": "test-model",
        }

    monkeypatch.setattr(router_mod, "route_chat", fake_route_chat)

    result = await runner_mod._synthesize_tool_results(
        instance_id="i",
        conversation_id="c",
        user_message="what is the gender breakdown?",
        completed_tools=[{
            "tool_name": "analyze_employees",
            "result": {"status_code": 200, "data": {
                "breakdown": [], "suggested_chart_type": "bar",
            }},
        }],
        draft_text="",
        envelope_synthesizer=synthesize_envelope,
    )
    assert result is not None
    assert "text" in result          # markdown still produced
    assert "envelope" in result      # additive typed block
    assert result["envelope"]["headline"] == _VALID_ENVELOPE["headline"]


# ── envelope propagation to the persisted message (PAQ-2B contract) ─────────

@pytest.fixture
def user(db):
    from accounts.models import User

    return User.objects.create_user(username="envelope-worker", password="secret123")


@pytest.fixture
def conversation(db, user):
    from ai.models import AIConversation

    return AIConversation.objects.create(
        user=user,
        title="Envelope chat",
        conversation_type="chat",
        app_identifier="carbon",
        task_payload_json={},
        scope_json={},
    )


@pytest.mark.django_db
def test_build_ai_message_persists_envelope_in_metadata(user, conversation):
    """The envelope must survive to the serialized message so the frontend can
    render it deterministically (mirrors the ``code_result`` delivery path)."""
    from ai.intelligence import CarbonIntelligence
    from ai.models import AIMessage

    CarbonIntelligence()._build_ai_message(
        conversation,
        "completed",
        "Here is the markdown answer.",
        follow_up_questions=[],
        envelope=_VALID_ENVELOPE,
    )

    message = AIMessage.objects.filter(conversation=conversation, role="assistant").get()
    stored = message.metadata_json.get("envelope")
    assert stored is not None
    assert stored["headline"] == _VALID_ENVELOPE["headline"]
    assert stored["tables"][0]["rows"] == [["male", 6], ["female", 2]]


@pytest.mark.django_db
def test_build_ai_message_without_envelope_omits_key(user, conversation):
    """No envelope → no empty ``envelope`` key (the frontend fallback stays clean)."""
    from ai.intelligence import CarbonIntelligence
    from ai.models import AIMessage

    CarbonIntelligence()._build_ai_message(
        conversation,
        "completed",
        "Plain markdown answer.",
        follow_up_questions=[],
        envelope=None,
    )

    message = AIMessage.objects.filter(conversation=conversation, role="assistant").get()
    assert "envelope" not in (message.metadata_json or {})
