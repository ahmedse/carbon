"""S1.5 Intent resolution — LLM-as-classifier (ADR-0023).

These tests cover the pure, LLM-free decision surface of ``intent.py``
(prompt label set, JSON parsing, confidence ladder) plus the resolver's
graceful-degradation guarantees (empty catalog / bad JSON / LLM error all
return ``None`` so the turn never breaks).
"""
import pytest

from ai.engine.cognition.turn.intent import (
    IntentCandidate,
    IntentResolution,
    IntentResolver,
    _apply_ladder,
    _build_label_set,
    _endpoint_to_domain_phrase,
    _parse_json,
    _to_resolution,
)


# ── Domain phrase / label set ───────────────────────────────────────────────

def test_endpoint_to_domain_phrase_strips_read_prefix():
    assert _endpoint_to_domain_phrase("list_emission_factors") == "emission factors"
    assert _endpoint_to_domain_phrase("get_calculation_summary") == "calculation summary"
    assert _endpoint_to_domain_phrase("search_orders") == "orders"


def test_build_label_set_includes_only_read_endpoints():
    catalog = [
        {"name": "list_emission_factors", "method": "GET", "description": "x"},
        {"name": "create_table", "method": "POST", "description": "mutating"},
        {"name": "get_chairman_overview", "method": "GET", "description": "y"},
        {"name": "create_dq_rule", "method": "POST", "requires_confirmation": True},
    ]
    labels = _build_label_set(catalog)
    assert [l["name"] for l in labels] == ["list_emission_factors", "get_chairman_overview"]
    assert labels[0]["phrase"] == "emission factors"


# ── JSON parsing ────────────────────────────────────────────────────────────

def test_parse_json_clean_object():
    assert _parse_json('{"action": "answer", "confidence": 0.9}') == {
        "action": "answer", "confidence": 0.9,
    }


def test_parse_json_strips_fences():
    content = '```json\n{"action": "answer"}\n```'
    assert _parse_json(content) == {"action": "answer"}


def test_parse_json_extracts_embedded_object():
    content = 'Here is the result: {"action": "answer"} trailing'
    assert _parse_json(content) == {"action": "answer"}


def test_parse_json_garbage_returns_none():
    assert _parse_json("not json at all") is None
    assert _parse_json(None) is None
    assert _parse_json("") is None


# ── Resolution mapping ──────────────────────────────────────────────────────

def test_to_resolution_sorts_candidates_desc():
    data = {
        "action": "answer",
        "intent": "show emission factors",
        "candidates": [
            {"name": "list_gwp_gases", "confidence": 0.4},
            {"name": "list_emission_factors", "confidence": 0.95, "reason": "direct"},
        ],
        "confidence": 0.95,
        "needs_host_data": True,
    }
    res = _to_resolution(data)
    assert res.action == "answer"
    assert res.candidates[0].name == "list_emission_factors"
    assert res.candidates[0].confidence == 0.95
    assert res.needs_host_data is True


def test_to_resolution_clamps_confidence():
    res = _to_resolution({"candidates": [{"name": "x", "confidence": 5.0}]})
    assert res.candidates[0].confidence == 1.0


def test_to_resolution_accepts_flat_endpoint_field():
    # The model naturally emits a flat `endpoint` string, not a candidates array.
    res = _to_resolution({
        "action": "answer",
        "endpoint": "list_gwp_gases",
        "confidence": 0.95,
    })
    assert res.action == "answer"
    assert res.candidates[0].name == "list_gwp_gases"
    assert res.candidates[0].confidence == 0.95
    assert res.needs_host_data is True


def test_to_resolution_delivery_axis_parses_explicit_mode():
    res = _to_resolution({
        "action": "answer",
        "endpoint": "list_emission_factors",
        "confidence": 0.95,
        "delivery": "list",
    })
    assert res.delivery == "list"


def test_to_resolution_delivery_defaults_to_explain():
    # A bare "show me X" with no delivery hint must default to understanding,
    # not enumeration.
    res = _to_resolution({
        "action": "answer",
        "endpoint": "list_emission_factors",
        "confidence": 0.95,
    })
    assert res.delivery == "explain"


def test_to_resolution_delivery_coerces_unknown_to_explain():
    res = _to_resolution({
        "action": "answer",
        "endpoint": "list_emission_factors",
        "confidence": 0.95,
        "delivery": "make-it-fancy",
    })
    assert res.delivery == "explain"


def test_to_resolution_explicit_clarify_without_candidates():
    res = _to_resolution({
        "action": "clarify",
        "endpoint": None,
        "confidence": 0.3,
        "clarification": "Which data product?",
    })
    assert res.action == "clarify"
    assert res.clarification == "Which data product?"
    assert res.candidates == []


# ── Confidence ladder ───────────────────────────────────────────────────────

def _res(cands, action="answer", confidence=None, options=None, clarification="", delivery="explain"):
    candidates = [
        IntentCandidate(name=n, confidence=c) for n, c in cands
    ]
    return IntentResolution(
        action=action,
        delivery=delivery,
        candidates=candidates,
        confidence=confidence if confidence is not None else (cands[0][1] if cands else 0.0),
        options=options or [],
        clarification=clarification,
    )


def test_ladder_single_confident_candidate_answers():
    labels = [{"name": "list_emission_factors"}, {"name": "list_gwp_gases"}]
    res = _apply_ladder(
        _res([("list_emission_factors", 0.95)]),
        labels, min_confidence=0.6, ambiguity_gap=0.15,
    )
    assert res.action == "answer"
    assert res.needs_host_data is True


def test_ladder_preserves_delivery_axis():
    # The ladder reclassifies action/confidence but must NOT clobber the
    # cognitive-intent (delivery) axis the classifier emitted.
    labels = [{"name": "list_emission_factors"}, {"name": "list_gwp_gases"}]
    res = _apply_ladder(
        _res([("list_emission_factors", 0.95)], delivery="analyze"),
        labels, min_confidence=0.6, ambiguity_gap=0.15,
    )
    assert res.action == "answer"
    assert res.delivery == "analyze"


def test_ladder_two_close_candidates_disambiguate():
    labels = [{"name": "list_emission_factors"}, {"name": "list_gwp_gases"}]
    res = _apply_ladder(
        _res([("list_emission_factors", 0.7), ("list_gwp_gases", 0.62)]),
        labels, min_confidence=0.6, ambiguity_gap=0.15,
    )
    assert res.action == "disambiguate"
    assert res.options  # short human options populated


def test_ladder_low_confidence_clarifies():
    labels = [{"name": "list_emission_factors"}]
    res = _apply_ladder(
        _res([("list_emission_factors", 0.4)]),
        labels, min_confidence=0.6, ambiguity_gap=0.15,
    )
    assert res.action == "clarify"
    assert res.clarification


def test_ladder_strips_hallucinated_candidate():
    labels = [{"name": "list_emission_factors"}]
    res = _apply_ladder(
        _res([("drop_all_tables", 0.99)]),
        labels, min_confidence=0.6, ambiguity_gap=0.15,
    )
    # The hallucinated name is removed → no candidate → plain answer, no host data.
    assert res.candidates == []
    assert res.needs_host_data is False
    assert res.action == "answer"


def test_ladder_no_candidates_answers_without_host_data():
    res = _apply_ladder(
        _res([]), [], min_confidence=0.6, ambiguity_gap=0.15,
    )
    assert res.action == "answer"
    assert res.needs_host_data is False


def test_ladder_respects_explicit_disambiguate_with_options():
    res = IntentResolution(action="disambiguate", options=["emission factors", "GWP gases"])
    res = _apply_ladder(res, [], min_confidence=0.6, ambiguity_gap=0.15)
    assert res.action == "disambiguate"
    assert res.options == ["emission factors", "GWP gases"]


# ── Resolver graceful degradation (no network) ──────────────────────────────

@pytest.mark.asyncio
async def test_resolve_empty_catalog_returns_none():
    resolver = IntentResolver()
    result = await resolver.resolve(user_message="hi", api_catalog=[])
    assert result is None


@pytest.mark.asyncio
async def test_resolve_no_read_endpoints_returns_none():
    resolver = IntentResolver()
    result = await resolver.resolve(
        user_message="hi",
        api_catalog=[{"name": "create_table", "method": "POST"}],
    )
    assert result is None


@pytest.mark.asyncio
async def test_resolve_mocked_llm_returns_resolution(monkeypatch):
    import ai.engine.llm.router as router_mod

    async def fake_route_chat(**kwargs):
        assert kwargs["response_format"] == {"type": "json_object"}
        assert kwargs["temperature"] == 0
        return {
            "content": (
                '{"action":"answer","endpoint":"list_emission_factors",'
                '"confidence":0.97}'
            ),
            "input_tokens": 50,
            "output_tokens": 30,
            "model": "test-model",
        }

    monkeypatch.setattr(router_mod, "route_chat", fake_route_chat)
    resolver = IntentResolver()
    result = await resolver.resolve(
        user_message="what emission factors do we have here?",
        api_catalog=[
            {"name": "list_emission_factors", "method": "GET", "description": "factors"},
            {"name": "list_gwp_gases", "method": "GET", "description": "gwp"},
        ],
    )
    assert result is not None
    assert result.action == "answer"
    assert result.candidates[0].name == "list_emission_factors"
    assert result.input_tokens == 50
    assert result.output_tokens == 30


@pytest.mark.asyncio
async def test_resolve_mocked_bad_json_returns_none(monkeypatch):
    import ai.engine.llm.router as router_mod

    async def fake_route_chat(**kwargs):
        return {"content": "sorry, no JSON here", "input_tokens": 1, "output_tokens": 1}

    monkeypatch.setattr(router_mod, "route_chat", fake_route_chat)
    result = await IntentResolver().resolve(
        user_message="hi",
        api_catalog=[{"name": "list_emission_factors", "method": "GET", "description": "x"}],
    )
    assert result is None


@pytest.mark.asyncio
async def test_resolve_mocked_llm_error_returns_none(monkeypatch):
    import ai.engine.llm.router as router_mod

    async def fake_route_chat(**kwargs):
        raise RuntimeError("provider down")

    monkeypatch.setattr(router_mod, "route_chat", fake_route_chat)
    result = await IntentResolver().resolve(
        user_message="hi",
        api_catalog=[{"name": "list_emission_factors", "method": "GET", "description": "x"}],
    )
    assert result is None
