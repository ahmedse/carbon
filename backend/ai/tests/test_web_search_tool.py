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
