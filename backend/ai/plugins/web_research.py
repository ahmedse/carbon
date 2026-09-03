"""``web_research`` — keyless internet research tool (search + fetch).

Gives Pulse a real research primitive so a "deep study" brief can gather
evidence from the open web instead of only the internal knowledge base.

Two modes, both read-only (no mutation, no confirmation — RULE_21):

  * ``query`` — keyless web search.  Aggregates Wikipedia's search + intro
    extracts (authoritative, citable) and DuckDuckGo's Instant Answer API
    (direct abstract + related topics).  Returns a ranked list of
    ``{title, url, snippet, source}`` the drafting witness can synthesize.
  * ``url`` — fetch a specific page and extract readable text (plain-text
    HTML reduction, no external deps beyond ``httpx`` + ``html.parser``).

Guardrails honored (non-negotiable):

  * **RULE_20** — zero upward imports: only stdlib + ``httpx`` + the plugin
    base.  Nothing from ``dq``/``catalog``/``mdm``/``emissions``/``accounts``.
  * **RULE_21** — read-only: ``requires_confirmation=False``, nothing staged.
  * **Fail-visible** — network failures return ``{"error": ...}``, never a
    fabricated answer.  No search API key is required; when the keyless
    endpoints are unreachable the tool reports that plainly.
"""
from __future__ import annotations

import html
import logging
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx

from ai.engine.agent.plugins import ToolPlugin

logger = logging.getLogger("carbon.ai.plugins.web_research")

_WIKI_API = "https://en.wikipedia.org/w/api.php"
_DDG_API = "https://api.duckduckgo.com/"
_UA = "Carbon-Data-Trust-Research/1.0 (research agent; +contact: platform@example.com)"
_TIMEOUT = 12.0


def _strip_html(fragment: str) -> str:
    """Minimal HTML → text reduction (tags stripped, entities unescaped)."""
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", fragment or "", flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _now_iso() -> str:
    """UTC timestamp for external-source provenance (stdlib only, RULE_20)."""
    return datetime.now(timezone.utc).isoformat()


class WebResearch(ToolPlugin):
    name = "web_research"
    description = (
        "Search the open internet (keyless) or fetch a specific web page. "
        "Use it to research topics, standards, protocols, or systems that are "
        "not in the internal knowledge base — e.g. 'research the top carbon "
        "footprint standards (GHG Protocol, ISO 14064, PAS 2050)'. Returns "
        "ranked results with titles, URLs and snippets you can cite."
    )
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "The topic to research on the web. Provide one when you "
                    "want a search; omit it when fetching a specific URL."
                ),
            },
            "url": {
                "type": "string",
                "description": (
                    "A single URL to fetch and extract readable text from. "
                    "Use this to read a specific page (e.g. a standard's "
                    "official page)."
                ),
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum results to return (default 5, max 8).",
            },
        },
    }
    requires_confirmation = False
    capability: str | None = "ai:web_search"
    app_identifier: str | None = None

    async def execute(self, args: dict, *, ctx) -> dict:
        query = (args.get("query") or "").strip()
        url = (args.get("url") or "").strip()
        max_results = max(1, min(int(args.get("max_results") or 5), 8))

        if not query and not url:
            return {
                "error": (
                    "Provide a query to search, or a url to fetch — for "
                    "example: web_research(query='GHG Protocol vs ISO 14064')."
                ),
            }

        try:
            async with httpx.AsyncClient(
                timeout=_TIMEOUT, headers={"User-Agent": _UA}, follow_redirects=True
            ) as client:
                if url:
                    return await self._fetch(client, url)
                return await self._search(client, query, max_results)
        except httpx.HTTPError as exc:
            logger.warning("web_research network error: %s", exc)
            return {"error": f"Web research failed (network): {exc}"}

    async def _fetch(self, client: httpx.AsyncClient, url: str) -> dict:
        resp = await client.get(url)
        resp.raise_for_status()
        ctype = resp.headers.get("content-type", "")
        if "text/html" not in ctype and "text/plain" not in ctype:
            return {
                "url": url,
                "title": "",
                "text": resp.text[:4000],
                "note": f"Content type {ctype}; raw text returned.",
                "source": "external_web",
                "retrieved_at": _now_iso(),
            }
        body = resp.text
        title_match = re.search(r"<title[^>]*>(.*?)</title>", body, flags=re.S | re.I)
        title = _strip_html(title_match.group(1)) if title_match else url
        text = _strip_html(body)
        return {
            "url": url,
            "title": title[:300],
            "text": text[:6000],
            "length": len(text),
            "source": "external_web",
            "retrieved_at": _now_iso(),
        }

    async def _search(self, client: httpx.AsyncClient, query: str, max_results: int) -> dict:
        results: list[dict] = []
        seen_urls: set[str] = set()

        # 1) Wikipedia search (authoritative, citable, keyless).
        try:
            w = await client.get(
                _WIKI_API,
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "srlimit": max_results,
                    "format": "json",
                },
            )
            w.raise_for_status()
            hits = (w.json().get("query") or {}).get("search") or []
            titles = [h.get("title") for h in hits if h.get("title")]
            if titles:
                # Fetch intro extracts for the top titles in one batched query.
                ex = await client.get(
                    _WIKI_API,
                    params={
                        "action": "query",
                        "prop": "extracts",
                        "exintro": "1",
                        "explaintext": "1",
                        "titles": "|".join(titles[:max_results]),
                        "format": "json",
                    },
                )
                ex.raise_for_status()
                pages = (ex.json().get("query") or {}).get("pages") or {}
                page_by_title = {p.get("title"): p for p in pages.values()}
                for title in titles:
                    page = page_by_title.get(title) or {}
                    snippet = (page.get("extract") or "").strip() or (hits and _title_snippet(hits, title))
                    if not snippet:
                        snippet = next(
                            (h.get("snippet", "") for h in hits if h.get("title") == title), ""
                        )
                    page_url = f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"
                    if page_url in seen_urls:
                        continue
                    seen_urls.add(page_url)
                    results.append({
                        "title": title,
                        "url": page_url,
                        "snippet": _strip_html(snippet)[:800],
                        "source": "wikipedia",
                    })
        except httpx.HTTPError as exc:
            logger.warning("web_research wikipedia error: %s", exc)

        # 2) DuckDuckGo Instant Answer (direct abstract + related topics).
        try:
            d = await client.get(
                _DDG_API,
                params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
            )
            d.raise_for_status()
            data = d.json()
            abstract = (data.get("AbstractText") or "").strip()
            abstract_url = data.get("AbstractURL") or ""
            if abstract and abstract_url and abstract_url not in seen_urls:
                seen_urls.add(abstract_url)
                results.append({
                    "title": (data.get("Heading") or query)[:300],
                    "url": abstract_url,
                    "snippet": abstract[:800],
                    "source": "duckduckgo",
                })
            for rel in (data.get("RelatedTopics") or [])[:max_results]:
                if not isinstance(rel, dict):
                    continue
                rt = (rel.get("Text") or "").strip()
                rurl = rel.get("FirstURL") or ""
                if not rt or not rurl or rurl in seen_urls:
                    continue
                seen_urls.add(rurl)
                results.append({
                    "title": rt.split(" - ")[0][:300],
                    "url": rurl,
                    "snippet": rt[:800],
                    "source": "duckduckgo",
                })
        except httpx.HTTPError as exc:
            logger.warning("web_research duckduckgo error: %s", exc)

        if not results:
            return {
                "query": query,
                "results": [],
                "message": (
                    "No results were returned from the keyless web sources. "
                    "Consider fetching a specific URL instead."
                ),
                "source": "external_web",
                "retrieved_at": _now_iso(),
            }

        retrieved_at = _now_iso()
        for item in results:
            item["retrieved_at"] = retrieved_at
        return {
            "query": query,
            "results": results[:max_results],
            "count": len(results[:max_results]),
            "source": "external_web",
            "retrieved_at": retrieved_at,
        }


def _title_snippet(hits: list[dict], title: str) -> str:
    for h in hits:
        if h.get("title") == title:
            return h.get("snippet", "")
    return ""
