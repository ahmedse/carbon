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
_OPEN_METEO_GEO = "https://geocoding-api.open-meteo.com/v1/search"
_OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast"
_UA = "Carbon-Data-Trust-Research/1.0 (research agent; +contact: platform@example.com)"
_TIMEOUT = 12.0

# WMO weather interpretation codes → human-readable condition (Open-Meteo).
_WEATHER_CODES: dict[int, str] = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    56: "light freezing drizzle",
    57: "dense freezing drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    66: "light freezing rain",
    67: "heavy freezing rain",
    71: "slight snow",
    73: "moderate snow",
    75: "heavy snow",
    77: "snow grains",
    80: "slight rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    85: "slight snow showers",
    86: "heavy snow showers",
    95: "thunderstorm",
    96: "thunderstorm with slight hail",
    99: "thunderstorm with heavy hail",
}

# A query is a *live weather* question only when it names weather/forecast/
# temperature intent (or "how hot/cold is it in …"). This deliberately does
# NOT match "acid rain", "does it snow in the Sahara", etc.
_WEATHER_PATTERN = re.compile(
    r"\b(?:weather|forecast|temperature|temp)\b|"
    r"how\s+(?:hot|cold|warm|cool)\s+is\s+it|"
    r"is\s+it\s+(?:raining|snowing|sunny|cloudy)",
    re.IGNORECASE,
)


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


def _is_weather_query(query: str) -> bool:
    """True when the query asks for live weather/forecast/temperature."""
    return bool(_WEATHER_PATTERN.search(query or ""))


def _extract_weather_location(query: str) -> str:
    """Pull the place name out of a weather question.

    Handles the common phrasings so "what's the weather in Cairo today?"
    → "Cairo", "how hot is it in New York?" → "New York". Falls back to a
    best-effort strip when no known pattern matches.
    """
    q = (query or "").strip()
    q = re.sub(r"^(?:what'?s|what is|whats|how'?s|how is|tell me)\s+", "", q, flags=re.I)
    q = re.sub(
        r"^(?:the\s+)?(?:current\s+)?(?:weather|forecast|temperature|temp)\s+"
        r"(?:like\s+)?(?:in|for|at)\s+",
        "",
        q,
        flags=re.I,
    )
    q = re.sub(
        r"^how\s+(?:hot|cold|warm|cool)\s+is\s+it\s+(?:in|at)\s+",
        "",
        q,
        flags=re.I,
    )
    # Strip trailing punctuation BEFORE the time-word strip so "today?" →
    # "today" (otherwise the "?" blocks the end-anchored match).
    q = q.strip(" .,;!?")
    q = re.sub(
        r"\s+(?:today|tonight|tomorrow|now|right now|this week|currently|at the moment)\s*$",
        "",
        q,
        flags=re.I,
    )
    return q.strip(" .,;!?")


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
                if _is_weather_query(query):
                    weather = await self._weather(client, query)
                    if weather is not None:
                        return weather
                    # Location couldn't be resolved — fall back to search so
                    # the user still gets something rather than a refusal.
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

    async def _weather(self, client: httpx.AsyncClient, query: str) -> dict | None:
        """Live weather via Open-Meteo (keyless — no API key, RULE_20).

        Returns ``None`` when the location can't be geocoded (caller falls back
        to a generic web search). A geocoded-but-failed forecast returns an
        explicit ``error`` result so the drafting witness reports the failure
        honestly instead of fabricating a reading.
        """
        location = _extract_weather_location(query)
        if not location:
            return None

        # 1) Geocode the place name → lat/lon.
        try:
            g = await client.get(
                _OPEN_METEO_GEO,
                params={"name": location, "count": 1, "language": "en", "format": "json"},
            )
            g.raise_for_status()
            matches = (g.json().get("results") or [])
        except httpx.HTTPError as exc:
            logger.warning("web_research geocoding error: %s", exc)
            return None

        if not matches:
            return None
        top = matches[0]
        lat = top.get("latitude")
        lon = top.get("longitude")
        if lat is None or lon is None:
            return None
        name = (top.get("name") or location).strip() or location
        country = (top.get("country") or "").strip()

        # 2) Current conditions for the resolved coordinates.
        try:
            w = await client.get(
                _OPEN_METEO_FORECAST,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": (
                        "temperature_2m,relative_humidity_2m,apparent_temperature,"
                        "is_day,weather_code,wind_speed_10m"
                    ),
                    "timezone": "auto",
                },
            )
            w.raise_for_status()
            current = (w.json().get("current") or {})
        except httpx.HTTPError as exc:
            logger.warning("web_research forecast error: %s", exc)
            return {
                "query": query,
                "results": [],
                "error": f"Could not fetch current weather for {name}: {exc}",
                "source": "external_web",
                "retrieved_at": _now_iso(),
            }

        code = int(current.get("weather_code") or 0)
        conditions = _WEATHER_CODES.get(code, "unknown conditions")
        temp = current.get("temperature_2m")
        feels = current.get("apparent_temperature")
        humidity = current.get("relative_humidity_2m")
        wind = current.get("wind_speed_10m")
        is_day = current.get("is_day")

        retrieved_at = _now_iso()
        place = f"{name}, {country}" if country else name
        snippet_bits = [f"{place}:"]
        if temp is not None:
            snippet_bits.append(f"{temp}°C")
        if feels is not None:
            snippet_bits.append(f"feels like {feels}°C")
        snippet_bits.append(conditions)
        if humidity is not None:
            snippet_bits.append(f"humidity {humidity}%")
        if wind is not None:
            snippet_bits.append(f"wind {wind} km/h")
        snippet = " ".join(snippet_bits) + "."

        weather = {
            "location": name,
            "country": country,
            "temperature_c": temp,
            "feels_like_c": feels,
            "humidity_percent": humidity,
            "wind_kmh": wind,
            "conditions": conditions,
            "is_day": bool(is_day) if is_day is not None else None,
            "time": current.get("time"),
            "timezone": current.get("timezone"),
        }

        return {
            "query": query,
            "results": [{
                "title": f"Current weather in {place}",
                "url": "https://open-meteo.com/",
                "snippet": snippet,
                "source": "open-meteo",
                "retrieved_at": retrieved_at,
            }],
            "weather": weather,
            "count": 1,
            "source": "external_web",
            "retrieved_at": retrieved_at,
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
