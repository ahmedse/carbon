"""Conversation-local stated facts — C10 recall without an LLM call.

Confirmed ``learn_fact`` cards stay on the Chat-confirm path (ADR-0046).
This module only folds a bare ``my X is Y`` statement into ConversationState
``last_results`` and answers later recall from that state.

Schema stays v1: facts are ``last_results`` rows with ``tool=user_fact``.
"""
from __future__ import annotations
from ai.engine.cognition.phrase_tables import T


import re
from typing import Any

from ai.engine.cognition.turn.memory_recall_i18n import (
    HOST_IDENTITY_AR,
    STORE_REMEMBER_AR,
    any_needle,
)
from ai.engine.text.word_match import contains_any_phrase, has_any_word, has_word

_STORE_REMEMBER_PHRASES = T("turn/memory_recall.py::_STORE_REMEMBER_PHRASES")
_FACT_EN_RE = re.compile(
    r"\bmy\s+([a-z][a-z0-9][a-z0-9 /-]{0,40}?)\s+is\s+"
    r"([A-Za-z0-9][A-Za-z0-9._/-]{1,48})\b",
    re.IGNORECASE,
)
_FACT_NAME_RE = re.compile(
    r"\bmy\s+((?:full\s+)?name)\s+is\s+([A-Za-z][A-Za-z .'-]{1,60})\b",
    re.IGNORECASE,
)
_RECALL_PHRASES = T("turn/memory_recall.py::_RECALL_PHRASES")
_HOST_IDENTITY_PHRASES = T("turn/memory_recall.py::_HOST_IDENTITY_PHRASES")
_HOST_IDENTITY_WORDS = T("turn/memory_recall.py::_HOST_IDENTITY_WORDS")
_STOP = T("turn/memory_recall.py::_STOP")
_FACT_TOOL = "user_fact"


def is_remember_store(text: str) -> bool:
    """True when the user asked Chat to persist a learn_fact card."""
    raw = text or ""
    return bool(
        contains_any_phrase(raw, _STORE_REMEMBER_PHRASES)
        or any_needle(raw, STORE_REMEMBER_AR)
    )


def extract_stated_facts(text: str) -> list[dict[str, str]]:
    """Lexical ``my <label> is <code>`` — value must look like a code."""
    if is_remember_store(text):
        return []
    out: list[dict[str, str]] = []
    for match in _FACT_NAME_RE.finditer(text or ""):
        label = " ".join(match.group(1).split()).strip().lower()
        value = " ".join(match.group(2).split()).strip(" .")
        if label and value and " " in value:
            out.append({"key": label, "value": value})
    seen_keys = {row["key"] for row in out}
    for match in _FACT_EN_RE.finditer(text or ""):
        label = " ".join(match.group(1).split()).strip().lower()
        value = match.group(2).strip()
        if not label or not value or not _looks_like_code(value):
            continue
        if label in seen_keys:
            continue
        out.append({"key": label, "value": value})
    return out


def facts_from_state(state: Any) -> list[dict[str, str]]:
    rows = getattr(state, "last_results", None) or []
    facts: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or row.get("tool") != _FACT_TOOL:
            continue
        key, value = _split_digest(str(row.get("digest") or ""))
        if not key or not value:
            continue
        mark = f"{key}={value}"
        if mark in seen:
            continue
        seen.add(mark)
        facts.append({"key": key, "value": value})
    return facts


def remember_facts(state: Any, facts: list[dict[str, str]]) -> list[dict[str, str]]:
    """Append new facts onto ``state.last_results``. Returns the stored rows."""
    if state is None or not facts:
        return facts_from_state(state)
    existing = {(f["key"], f["value"]) for f in facts_from_state(state)}
    turn = 0
    try:
        turn = int(state.next_turn())
    except Exception:  # noqa: BLE001
        turn = 0
    rows = list(getattr(state, "last_results", None) or [])
    for fact in facts:
        key = str(fact.get("key") or "").strip()
        value = str(fact.get("value") or "").strip()
        if not key or not value or (key, value) in existing:
            continue
        rows.append({
            "turn": turn,
            "tool": _FACT_TOOL,
            "api": "",
            "digest": f"{key} is {value}",
            "ref": f"fact:{key.replace(' ', '_')}",
        })
        existing.add((key, value))
    state.last_results = rows
    return facts_from_state(state)


def _host_identity_facet(text: str) -> set[str]:
    """Tokens from host-field wording only — not the whole utterance."""
    facet: set[str] = set()
    raw = text or ""
    cf = raw.casefold()
    for phrase in _HOST_IDENTITY_PHRASES:
        if phrase in cf:
            facet |= _tokens(phrase)
    for word in _HOST_IDENTITY_WORDS:
        if has_word(raw, word):
            facet.add(word.casefold())
    if any_needle(raw, HOST_IDENTITY_AR):
        facet |= _tokens(" ".join(n for n in HOST_IDENTITY_AR if n in raw))
    return facet


def is_memory_use(text: str, facts: list[dict[str, str]]) -> bool:
    if not facts or not (text or "").strip():
        return False
    host_facet = _host_identity_facet(text)
    if host_facet:
        return any(
            bool(host_facet & _tokens(f.get("key") or "")) for f in facts
        )
    if contains_any_phrase(text, _RECALL_PHRASES):
        return True
    blob = " ".join(f"{f['key']} {f['value']}" for f in facts)
    return bool(_tokens(text) & _tokens(blob))


def render_fact_ack(text: str, facts: list[dict[str, str]]) -> str:
    fact = facts[-1] if facts else None
    if fact is None:
        return "Noted."
    return f"Got it. Your {fact['key']} is {fact['value']}."


def render_recall(text: str, facts: list[dict[str, str]]) -> str:
    if not facts:
        return "I do not have that on record yet."
    if len(facts) == 1:
        fact = facts[0]
        if re.search(r"\bstill\b", text or "", re.I):
            return f"Yes, {fact['value']} is still your {fact['key']}."
        if re.search(r"\bconfirm\b", text or "", re.I):
            return f"Yes, confirmed. Your {fact['key']} is {fact['value']}."
        if re.search(r"\bremember\b", text or "", re.I):
            return f"Yes, I remember that your {fact['key']} is {fact['value']}."
        return f"Your {fact['key']} is {fact['value']}."
    parts = [f"{f['key']} {f['value']}" for f in facts]
    return "I have: " + "; ".join(parts) + "."


def _looks_like_code(value: str) -> bool:
    return any(ch.isdigit() for ch in value) or value.isupper()


def _split_digest(digest: str) -> tuple[str, str]:
    if " is " not in digest:
        return "", ""
    key, value = digest.split(" is ", 1)
    return key.strip().lower(), value.strip()


def _tokens(text: str) -> set[str]:
    out: set[str] = set()
    current: list[str] = []
    for ch in (text or "").lower():
        if ch.isalnum() or ch in "_-":
            current.append(ch)
            continue
        if len(current) >= 2:
            tok = "".join(current)
            if tok not in _STOP and len(tok) >= 3:
                out.add(tok)
                if tok.endswith("s") and len(tok) > 4:
                    out.add(tok[:-1])
        current = []
    if len(current) >= 2:
        tok = "".join(current)
        if tok not in _STOP and len(tok) >= 3:
            out.add(tok)
            if tok.endswith("s") and len(tok) > 4:
                out.add(tok[:-1])
    return out
