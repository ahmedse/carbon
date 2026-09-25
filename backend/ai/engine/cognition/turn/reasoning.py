"""Typed reasoning channel (ADR-0054, pillar B).

Four layers, no extra model round for the rationale:

* the Decision reason, scrubbed
* a step line from the step record (intent + unfinished dependencies)
* a provider summary only when conversation state already asks for it
* a revision when text already produced for the turn is replaced

``dense=True`` (client opt-in) widens the provider thinking budget and the
scrubbed length. It still drops fences, backticks, and ``call_`` tokens.
"""
from __future__ import annotations

from typing import Any

CONFIDENCE_FLOOR = 0.6
_SCRUB_SENTENCES = 2
_SCRUB_CHARS = 400
_DENSE_SENTENCES = 12
_DENSE_CHARS = 2400


def scrub(text: str, *, dense: bool = False) -> str:
    """Drop fenced blocks, backtick spans, and call tokens. Cap by density."""
    raw = str(text or "")
    kept: list[str] = []
    fence = False
    for line in raw.splitlines():
        if "```" in line:
            fence = not fence
            continue
        if fence:
            continue
        piece = []
        tick = False
        for ch in line:
            if ch == "`":
                tick = not tick
                continue
            if not tick:
                piece.append(ch)
        line = "".join(piece)
        words = [w for w in line.split() if not w.startswith("call_")]
        if words:
            kept.append(" ".join(words))
    if dense:
        # Keep paragraph breaks so the Thought panel can read as prose.
        out = "\n".join(kept).strip()
        parts = [p.strip() for p in out.replace("\n", ". ").split(". ") if p.strip()]
        out = ". ".join(parts[:_DENSE_SENTENCES])
        if out and not out.endswith("."):
            out = out + "."
        return out[:_DENSE_CHARS]
    out = " ".join(kept).strip()
    parts = [p.strip() for p in out.split(". ") if p.strip()]
    out = ". ".join(parts[:_SCRUB_SENTENCES])
    if out and not out.endswith("."):
        out = out + "."
    return out[:_SCRUB_CHARS]


def budget_on(state: Any, *, dense: bool = False) -> bool:
    """True when this turn should request a provider reasoning summary.

    Default: low intent confidence, a previous degradation, or an open
    correction. ``dense`` is the client's opt-in (status-bar switch) — it
    does not read the user's words.
    """
    if dense:
        return True
    if state is None:
        return False
    intent = getattr(state, "intent", None) or {}
    try:
        if float(intent.get("confidence") or 1) < CONFIDENCE_FLOOR:
            return True
    except (TypeError, ValueError):
        pass
    decisions = getattr(state, "decisions", None) or []
    if decisions and "degraded" in str(decisions[-1].get("why") or ""):
        return True
    question = getattr(state, "open_question", None) or {}
    return str(question.get("kind") or "") == "correct_previous"


def revision(shown: str, replacement: str, reason: str, *, dense: bool = False) -> dict | None:
    """A revision when the turn replaces text it already produced."""
    prior = (shown or "").strip()
    nxt = (replacement or "").strip()
    if not prior or prior == nxt:
        return None
    return {"shown": scrub(prior, dense=dense), "reason": scrub(reason, dense=dense)}


def step_narration(intent: str, waiting: list[str]) -> str:
    """Why this step, and which dependencies have not finished."""
    line = scrub(intent) or "This step."
    pending = [str(w) for w in waiting if str(w).strip()]
    if not pending:
        return line
    return f"{line} Waiting on step {', '.join(pending)}."
