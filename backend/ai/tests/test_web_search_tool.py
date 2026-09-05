"""Wave I3-B — ``ai:web_search`` capability + external-source provenance.

Covers:
  * ``ai:web_search`` capability declared + registered + implied by
    ``ai:manage_console`` (no DB).
  * ``has_capability`` resolves for an admin (django_db).
  * ``web_research`` search + fetch results carry ``source="external_web"``
    + ``retrieved_at`` (mock ``httpx.AsyncClient`` — no network, no DB).
  * ``_build_external_sources`` extracts only external-web results and is
    provenance-safe on empty/malformed payloads (no DB).
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from ai.engine_runtime import _build_external_sources
from ai.plugins.web_research import WebResearch


# ── No-DB capability plumbing ───────────────────────────────────────────

def test_capability_declared_and_registered():
    from accounts.capabilities import ALL_CAPABILITIES, AI_WEB_SEARCH

    assert WebResearch.capability == "ai:web_search"
    assert AI_WEB_SEARCH.key in ALL_CAPABILITIES


def test_implies_expansion_includes_web_search():
    from accounts.capabilities import AI_MANAGE_CONSOLE, _expand_capabilities

    assert "ai:web_search" in _expand_capabilities({AI_MANAGE_CONSOLE.key})


@pytest.mark.django_db
def test_has_capability_resolves_for_admin():
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Group

    from accounts.capabilities import has_capability
    from accounts.models import ScopedRole

    User = get_user_model()
    user = User.objects.create_user(username="webadmin", password="test")
    group, _ = Group.objects.get_or_create(name="admin")
    ScopedRole.objects.create(user=user, group=group, is_active=True)

    assert has_capability(user, "ai:web_search") is True


# ── httpx.AsyncClient mocks (no network) ────────────────────────────────

class _Resp:
    def __init__(self, payload=None, text="", headers=None):
        self._payload = payload
        self.text = text
        self.headers = headers or {}

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _fake_client_class(router):
    class _FakeClient:
        def __init__(self, timeout=None, headers=None, follow_redirects=None):
            self._router = router

        async def get(self, url, *, params=None, **kwargs):
            return self._router(url, params or {})

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    return _FakeClient


def _search_router(url, params):
    if "api.duckduckgo.com" in url:
        return _Resp({
            "AbstractText": "The GHG Protocol provides standards.",
            "AbstractURL": "https://ghgprotocol.org",
            "Heading": "GHG Protocol",
            "RelatedTopics": [
                {"Text": "ISO 14064 - a standard", "FirstURL": "https://example.com/iso14064"},
            ],
        })
    if params.get("list") == "search":
        return _Resp({"query": {"search": [
            {"title": "GHG Protocol"},
            {"title": "Greenhouse gas"},
        ]}})
    if params.get("prop") == "extracts":
        return _Resp({"query": {"pages": {
            "1": {"title": "GHG Protocol", "extract": "The GHG Protocol is a standard."},
            "2": {"title": "Greenhouse gas", "extract": "A greenhouse gas traps heat."},
        }}})
    raise AssertionError(f"Unexpected URL/params: {url} {params}")


@pytest.mark.asyncio
async def test_search_result_is_external_labelled():
    with patch(
        "ai.plugins.web_research.httpx.AsyncClient",
        new=_fake_client_class(_search_router),
    ):
        result = await WebResearch().execute({"query": "GHG Protocol"}, ctx=None)

    assert result["source"] == "external_web"
    assert isinstance(result["retrieved_at"], str) and result["retrieved_at"]
    assert result["results"]
    for item in result["results"]:
        assert item.get("url")
        assert item.get("source")
        assert item.get("retrieved_at")


def _fetch_router(url, params):
    return _Resp(
        text=(
            "<html><head><title>Example Page</title></head>"
            "<body><p>Hello world.</p></body></html>"
        ),
        headers={"content-type": "text/html; charset=utf-8"},
    )


@pytest.mark.asyncio
async def test_fetch_result_is_external_labelled():
    with patch(
        "ai.plugins.web_research.httpx.AsyncClient",
        new=_fake_client_class(_fetch_router),
    ):
        result = await WebResearch().execute({"url": "https://example.com/x"}, ctx=None)

    assert result["source"] == "external_web"
    assert isinstance(result["retrieved_at"], str) and result["retrieved_at"]


# ── _build_external_sources extraction ──────────────────────────────────

def test_build_external_sources_extracts_only_external_web():
    completed = [
        {
            "tool_name": "web_research",
            "result": json.dumps({
                "source": "external_web",
                "retrieved_at": "2026-09-03T10:00:00+00:00",
                "results": [
                    {"title": "A", "url": "https://a.example", "source": "wikipedia",
                     "retrieved_at": "2026-09-03T10:00:00+00:00"},
                    {"title": "B", "url": "https://b.example", "source": "duckduckgo",
                     "retrieved_at": "2026-09-03T10:00:00+00:00"},
                ],
            }),
        },
        {
            "tool_name": "search_knowledge",
            "result": json.dumps({"results": [{"title": "internal"}]}),
        },
        {"tool_name": "broken", "error": "x"},
    ]
    sources = _build_external_sources(completed)
    assert len(sources) == 2
    for s in sources:
        assert set(s.keys()) == {"title", "url", "source", "retrieved_at"}
    assert [s["url"] for s in sources] == ["https://a.example", "https://b.example"]


def test_build_external_sources_empty_search_is_safe():
    completed = [
        {
            "tool_name": "web_research",
            "result": json.dumps({"source": "external_web", "results": []}),
        },
    ]
    assert _build_external_sources(completed) == []


# ── Live weather (Open-Meteo, keyless) ─────────────────────────────────

def _weather_router(url, params):
    if "geocoding-api.open-meteo.com" in url:
        assert params.get("name") == "Cairo", params
        return _Resp({"results": [
            {"name": "Cairo", "country": "Egypt", "latitude": 30.04, "longitude": 31.23},
        ]})
    if "api.open-meteo.com" in url:
        return _Resp({"current": {
            "temperature_2m": 30.9,
            "apparent_temperature": 31.6,
            "relative_humidity_2m": 44,
            "wind_speed_10m": 12.4,
            "weather_code": 1,
            "is_day": 0,
            "time": "2026-09-03T21:00",
        }})
    raise AssertionError(f"Unexpected URL/params: {url} {params}")


@pytest.mark.asyncio
async def test_weather_query_returns_live_reading():
    with patch(
        "ai.plugins.web_research.httpx.AsyncClient",
        new=_fake_client_class(_weather_router),
    ):
        result = await WebResearch().execute(
            {"query": "what's the weather in Cairo today?"}, ctx=None
        )

    assert result["source"] == "external_web"
    assert result["results"][0]["source"] == "open-meteo"
    assert result["results"][0]["url"] == "https://open-meteo.com/"
    w = result["weather"]
    assert w["location"] == "Cairo"
    assert w["country"] == "Egypt"
    assert w["temperature_c"] == 30.9
    assert w["conditions"] == "mainly clear"
    assert "30.9°C" in result["results"][0]["snippet"]


def test_weather_location_extraction():
    from ai.plugins.web_research import _extract_weather_location

    assert _extract_weather_location("what's the weather in Cairo today?") == "Cairo"
    assert _extract_weather_location("how hot is it in New York?") == "New York"
    assert _extract_weather_location("weather in Tokyo") == "Tokyo"
    assert _extract_weather_location("forecast for London") == "London"
    assert _extract_weather_location("what's the weather in north coast egypt today?") == "north coast egypt"


def _weather_region_router(url, params):
    if "geocoding-api.open-meteo.com" in url:
        # A region like "north coast egypt" resolves to NO place → empty.
        assert params.get("name") == "north coast egypt", params
        return _Resp({"results": []})
    # Any other endpoint (forecast, wikipedia, duckduckgo) means fall-through —
    # which must NOT happen for a weather no_match.
    raise AssertionError(f"Fall-through detected (should be no_match): {url} {params}")


@pytest.mark.asyncio
async def test_weather_region_returns_no_match():
    with patch(
        "ai.plugins.web_research.httpx.AsyncClient",
        new=_fake_client_class(_weather_region_router),
    ):
        result = await WebResearch().execute(
            {"query": "what's the weather in north coast egypt today?"}, ctx=None
        )

    assert result["status"] == "no_match"
    assert result["hint"] == "north coast egypt"
    assert "results" not in result  # no Wikipedia/DDG fall-through


def test_weather_query_detection_ignores_non_weather():
    from ai.plugins.web_research import _is_weather_query

    assert _is_weather_query("what's the weather in Cairo today?") is True
    assert _is_weather_query("explain the GHG Protocol") is False
    assert _is_weather_query("what is 2+2?") is False


# ── Weather follow-through (WEATHER-FT) ────────────────────────────────────

def test_pending_weather_rewrite_triggers_weather_query():
    """A bare location reply ('El Alamein, Egypt') after a pending_weather
    focus becomes 'weather in El Alamein, Egypt', which passes _is_weather_query."""
    from ai.plugins.web_research import _is_weather_query

    bare_location = "El Alamein, Egypt"
    assert not _is_weather_query(bare_location), "Bare location must NOT match before rewrite"

    rewritten = f"weather in {bare_location}"
    assert _is_weather_query(rewritten), "Rewritten query must match _is_weather_query"


def test_normalize_weather_location_corrects_typo():
    """The location normalizer corrects a misspelled place into a
    geocoder-ready 'City, Country' via the LLM."""
    import asyncio
    from unittest.mock import patch, AsyncMock

    from ai.engine.cognition.turn.runner import _normalize_weather_location

    with patch(
        "ai.engine.llm.router.route_chat",
        new=AsyncMock(return_value={"content": "El Alamein, Egypt", "input_tokens": 10, "output_tokens": 4, "model": "test"}),
    ):
        out = asyncio.run(
            _normalize_weather_location(
                instance_id="inst",
                conversation_id="conv",
                original_question="weather in northcost egypt?",
                user_reply="alamien",
            )
        )
    assert out == "El Alamein, Egypt"


def test_normalize_weather_location_uses_conversation_context():
    """The normalizer threads recent turns (the assistant's clarification with
    its offered candidates) into the LLM prompt so a typo'd reply resolves from
    context, not a blind guess."""
    import asyncio
    from unittest.mock import patch, AsyncMock

    from ai.engine.cognition.turn.runner import _normalize_weather_location

    captured = {}

    async def _fake_route_chat(**kwargs):
        captured["messages"] = kwargs.get("messages")
        return {"content": "El Alamein, Egypt", "input_tokens": 10, "output_tokens": 4, "model": "test"}

    history = [
        {"role": "user", "content": "tell me abt the todays weather in northcost egypt?"},
        {"role": "assistant", "content": "Could you clarify which location? For example: El Alamein, Marsa Matruh, Alexandria"},
    ]

    with patch("ai.engine.llm.router.route_chat", new=AsyncMock(side_effect=_fake_route_chat)):
        out = asyncio.run(
            _normalize_weather_location(
                instance_id="inst",
                conversation_id="conv",
                original_question="tell me abt the todays weather in northcost egypt?",
                user_reply="alamien",
                conversation_history=history,
            )
        )

    assert out == "El Alamein, Egypt"
    user_prompt = captured["messages"][-1]["content"]
    assert "El Alamein" in user_prompt
    assert "Marsa Matruh" in user_prompt
    assert "alamien" in user_prompt


def test_normalize_weather_location_falls_back_on_error():
    """When the LLM call fails, normalization returns the raw reply unchanged
    (never blocks the turn)."""
    import asyncio
    from unittest.mock import patch, AsyncMock

    from ai.engine.cognition.turn.runner import _normalize_weather_location

    with patch(
        "ai.engine.llm.router.route_chat",
        new=AsyncMock(side_effect=RuntimeError("llm down")),
    ):
        out = asyncio.run(
            _normalize_weather_location(
                instance_id="inst",
                conversation_id="conv",
                original_question="weather?",
                user_reply="Cairo",
            )
        )
    assert out == "Cairo"


def test_normalize_weather_location_rejects_sentence_like_output():
    """A sentence-like LLM response (>60 chars) is rejected → raw reply kept."""
    import asyncio
    from unittest.mock import patch, AsyncMock

    from ai.engine.cognition.turn.runner import _normalize_weather_location

    long_junk = "I think you probably mean a city somewhere on the north coast of Egypt near"
    with patch(
        "ai.engine.llm.router.route_chat",
        new=AsyncMock(return_value={"content": long_junk, "input_tokens": 10, "output_tokens": 4, "model": "test"}),
    ):
        out = asyncio.run(
            _normalize_weather_location(
                instance_id="inst",
                conversation_id="conv",
                original_question="weather?",
                user_reply="alamien",
            )
        )
    assert out == "alamien"


def test_normalize_weather_question_resolves_full_question_to_place():
    """A full weather question (greeting + typo + region + trailing suitability
    sub-question) resolves to a single geocoder-ready 'City, Country'."""
    import asyncio
    from unittest.mock import patch, AsyncMock

    from ai.engine.cognition.turn.runner import _normalize_weather_question

    with patch(
        "ai.engine.llm.router.route_chat",
        new=AsyncMock(return_value={"content": "El Alamein, Egypt", "input_tokens": 10, "output_tokens": 4, "model": "test"}),
    ):
        out = asyncio.run(
            _normalize_weather_question(
                instance_id="inst",
                conversation_id="conv",
                question="hi, what is the weather in north cost egypt toay, is it suitable for beach swiming ?",
            )
        )
    assert out == "El Alamein, Egypt"


def test_normalize_weather_question_falls_back_on_error():
    """When the LLM call fails, normalization falls back to the regex extractor
    (never blocks the turn)."""
    import asyncio
    from unittest.mock import patch, AsyncMock

    from ai.engine.cognition.turn.runner import _normalize_weather_question

    with patch(
        "ai.engine.llm.router.route_chat",
        new=AsyncMock(side_effect=RuntimeError("llm down")),
    ):
        out = asyncio.run(
            _normalize_weather_question(
                instance_id="inst",
                conversation_id="conv",
                question="weather in Cairo today?",
            )
        )
    # The regex fallback strips 'weather in' + 'today' → 'Cairo'.
    assert "Cairo" in out


def test_synthesize_tool_results_marks_clarification_and_hints():
    """_synthesize_tool_results returns is_clarification + clarification_hints
    when no_match results are present and no usable results exist."""
    import asyncio
    import json
    from unittest.mock import patch, AsyncMock

    from ai.engine.cognition.turn.runner import _synthesize_tool_results
    from ai.engine.core.resolution import no_match

    nm_result = no_match("unresolved_location", hint="north coast egypt")
    completed_tools = [
        {
            "tool_name": "web_research",
            "result": json.dumps(nm_result),
            "error": None,
            "requires_confirmation": False,
        }
    ]

    mock_clarify = {"text": "Which location do you mean?", "tokens": 50, "model": "test"}

    with patch(
        "ai.engine.cognition.turn.runner._clarify_no_matches",
        new=AsyncMock(return_value=mock_clarify),
    ):
        result = asyncio.run(
            _synthesize_tool_results(
                instance_id="inst",
                conversation_id="conv",
                user_message="what's the weather on the north coast egypt?",
                completed_tools=completed_tools,
                draft_text="",
                model="test",
            )
        )

    assert result is not None
    assert result["text"] == "Which location do you mean?"
    assert result.get("is_clarification") is True
    assert "north coast egypt" in result.get("clarification_hints", [])
    assert result.get("clarification_user_message") == "what's the weather on the north coast egypt?"


def test_synthesize_tool_results_no_clarification_marker_on_usable():
    """When tool results are usable (no no_match), is_clarification is absent."""
    import asyncio
    import json
    from unittest.mock import patch, AsyncMock

    from ai.engine.cognition.turn.runner import _synthesize_tool_results

    completed_tools = [
        {
            "tool_name": "web_research",
            "result": {"results": [{"title": "Cairo weather", "snippet": "30°C", "url": "http://x.com"}]},
            "error": None,
            "requires_confirmation": False,
        }
    ]

    mock_synth = {"text": "Cairo is 30°C and sunny.", "tokens": 40, "model": "test"}

    with patch(
        "ai.engine.llm.router.route_chat",
        new=AsyncMock(return_value={"content": "Cairo is 30°C and sunny.", "input_tokens": 20, "output_tokens": 20, "model": "test"}),
    ):
        result = asyncio.run(
            _synthesize_tool_results(
                instance_id="inst",
                conversation_id="conv",
                user_message="weather in Cairo",
                completed_tools=completed_tools,
                draft_text="",
                model="test",
            )
        )

    # Regardless of synthesis success, is_clarification must NOT be set
    if result is not None:
        assert not result.get("is_clarification")
