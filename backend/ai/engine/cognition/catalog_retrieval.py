"""Lexical top-k over a tool catalog (ADR-0049 P2/P8).

Embedding retrieval can replace ``rank_tools`` later. This scorer needs no
model and no network. It ranks by token overlap with name, description, and
examples. Ties keep catalog order.
"""
from __future__ import annotations

from typing import Any


def _tokens(text: str | None) -> set[str]:
    out: set[str] = set()
    word: list[str] = []
    for ch in text or "":
        if ch.isalnum() or "\u0600" <= ch <= "\u06ff":
            word.append(ch)
        elif word:
            if len(word) > 1:
                out.add("".join(word).lower())
            word = []
    if len(word) > 1:
        out.add("".join(word).lower())
    return out


def _tool_blob(tool: dict) -> str:
    parts = [
        str(tool.get("name") or ""),
        str(tool.get("description") or ""),
        str(tool.get("not_for") or ""),
        str(tool.get("domain") or ""),
    ]
    examples = tool.get("examples") or []
    if isinstance(examples, list):
        for ex in examples:
            if isinstance(ex, dict):
                parts.append(str(ex.get("ar") or ""))
                parts.append(str(ex.get("en") or ""))
            else:
                parts.append(str(ex))
    return " ".join(parts)


def _rank_scored(query: set[str], rows: list[dict], utterance: str) -> list[tuple[int, int, dict]]:
    scored: list[tuple[int, int, dict]] = []
    for index, tool in enumerate(rows):
        overlap = len(query & _tokens(_tool_blob(tool)))
        name_hit = 2 if str(tool.get("name") or "").lower() in (utterance or "").lower() else 0
        scored.append((overlap + name_hit, -index, tool))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return scored


def rank_tools(
    utterance: str,
    catalog: list[dict] | None,
    *,
    k: int = 12,
    context: str = "",
) -> list[dict]:
    """Return up to ``k`` tools, highest overlap first. Empty utterance → first k.

    A bare follow-up ("get it", "جيبها") overlaps nothing. Rank that against
    ``context`` (the recent transcript) so the offered read stays in the window.
    """
    rows = [t for t in (catalog or []) if isinstance(t, dict) and t.get("name")]
    if k <= 0:
        return []
    if not (utterance or "").strip():
        return rows[:k]
    scored = _rank_scored(_tokens(utterance), rows, utterance)
    if scored and scored[0][0] > 0:
        positive = [tool for score, _idx, tool in scored if score > 0]
        return positive[:k]
    if (context or "").strip():
        scored = _rank_scored(_tokens(context), rows, context)
        if scored and scored[0][0] > 0:
            positive = [tool for score, _idx, tool in scored if score > 0]
            return positive[:k]
    return rows[:k]


def select_for_surface(
    utterance: str,
    catalog: list[dict] | None,
    *,
    surface: str | None = None,
    k: int = 12,
    core_names: list[str] | None = None,
) -> list[dict]:
    """Top-k plus always-on core names. Chat drops tools with kind=write."""
    from ai.engine.agent.surface import Surface

    # ``chat.plan`` may draft a plan but still must not be handed write tools.
    on_chat = Surface.resolve(surface).is_chat
    ranked = rank_tools(utterance, catalog, k=k)
    by_name = {str(t.get("name")): t for t in (catalog or []) if isinstance(t, dict)}
    chosen: list[dict] = []
    seen: set[str] = set()
    for tool in ranked:
        name = str(tool.get("name"))
        if on_chat and str(tool.get("kind") or "") == "write":
            continue
        if name not in seen:
            chosen.append(tool)
            seen.add(name)
    for name in core_names or []:
        tool = by_name.get(name)
        if tool is None or name in seen:
            continue
        if on_chat and str(tool.get("kind") or "") == "write":
            continue
        chosen.append(tool)
        seen.add(name)
    return chosen
