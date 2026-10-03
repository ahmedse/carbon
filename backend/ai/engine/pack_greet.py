"""Pack-owned greeting door. The phrases and copy live in the pack.

The generic engine carries no greeting vocabulary: a pack declares
``greet.yaml`` (its greeting phrases, optional greeting-follow-up phrases and
the locale copy) and the engine returns the line. ``greet_reply`` reads the
pack bound for the turn, exactly like :mod:`ai.engine.pack_vocab`.

Matching is shape-only — a whole-message greeting (every token is one the
pack's own phrases declare) or a declared follow-up phrase. There is no
module-level word table and no compiled regexes here (ADR-0050/0051).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ai.engine.pack_vocab import _active_pack, _safe_segment

_SPEC_CACHE: dict[str, dict[str, Any]] = {}


def _pack_roots() -> list[Path]:
    """Repo layout (dev) and Docker mount (/domain_packs) both work."""
    here = Path(__file__).resolve()
    roots: list[Path] = []
    for candidate in (
        here.parents[3] / "domain_packs",  # monorepo: backend/ai/engine → repo
        Path("/domain_packs"),               # production compose bind-mount
        here.parents[2] / "domain_packs",  # fallback if packaged oddly
    ):
        if candidate.is_dir() and candidate not in roots:
            roots.append(candidate)
    return roots


def _spec(pack_id: str) -> dict[str, Any]:
    if not _safe_segment(pack_id):
        return {}
    cached = _SPEC_CACHE.get(pack_id)
    if cached is not None:
        return cached
    doc: dict[str, Any] = {}
    for root in _pack_roots():
        path = root / pack_id / "greet.yaml"
        if not path.is_file():
            continue
        try:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            loaded = {}
        doc = loaded if isinstance(loaded, dict) else {}
        break
    _SPEC_CACHE[pack_id] = doc
    return doc


def _fold(text: Any) -> str:
    from ai.engine.text.normalize import normalize_text

    return normalize_text(str(text or "")).casefold()


def _tokens(text: str) -> list[str]:
    out: list[str] = []
    buf: list[str] = []
    for ch in text:
        if ch.isalnum():
            buf.append(ch)
        elif buf:
            out.append("".join(buf))
            buf = []
    if buf:
        out.append("".join(buf))
    return out


def _phrases(spec: dict[str, Any], key: str) -> list[str]:
    raw = spec.get(key)
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if str(item).strip()]


def _bare_greeting(message: str, greetings: list[str]) -> str:
    """The declared greeting a whole message is, or ``""``.

    Every token of the message must be a token some declared greeting owns, so
    "hi" is a greeting while "hi, what is my balance" is not.
    """
    message_tokens = _tokens(message)
    if not message_tokens:
        return ""
    declared: set[str] = set()
    for phrase in greetings:
        declared.update(_tokens(_fold(phrase)))
    if not declared or not all(token in declared for token in message_tokens):
        return ""
    best = ""
    for phrase in greetings:
        folded = _fold(phrase)
        if folded and all(token in message_tokens for token in _tokens(folded)):
            if len(folded) > len(_fold(best)):
                best = phrase
    return best or greetings[0]


def _followup(message: str, followups: list[str]) -> str:
    for phrase in followups:
        folded = _fold(phrase)
        if folded and folded in message:
            return phrase
    return ""


def _copy(replies: Any, greeting: str, language: str) -> str:
    if not isinstance(replies, dict):
        return ""
    template = str(replies.get(language) or replies.get("en") or "").strip()
    if not template:
        return ""
    try:
        return template.format(greeting=greeting).strip()
    except (KeyError, IndexError, ValueError):
        return template


def greet_reply(text: str | None) -> dict[str, str] | None:
    """A 0-LLM greeting line from the bound pack, or ``None``.

    ``{"text": ..., "gate": "greet"|"greet_followup"}``. ``None`` when the pack
    declares no greet catalog or the message is not a greeting.
    """
    spec = _spec(_active_pack.get())
    if not spec:
        return None
    message = _fold(text)
    if not message:
        return None
    from ai.engine.cognition.turn.language import detect_reply_language

    language = "ar" if detect_reply_language(str(text or "")) == "ar" else "en"
    greeting = _bare_greeting(message, _phrases(spec, "greetings"))
    if greeting:
        line = _copy(spec.get("replies"), greeting, language)
        if line:
            return {"text": line, "gate": "greet"}
    followup = _followup(message, _phrases(spec, "followups"))
    if followup:
        line = _copy(spec.get("followup_replies"), followup, language)
        if line:
            return {"text": line, "gate": "greet_followup"}
    return None
