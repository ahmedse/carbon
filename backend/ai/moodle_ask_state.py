"""Typed Moodle Ask conversation state (host-side, not engine/).

Mirrors ConversationState.slots for the Moodle door path. Topic teaching
writes ``resolved_topic``; reference asks read it. Never scan chat history.
Keyed like chat_payload conversation_id: moodle-{uid}-{courseid}.
"""
from __future__ import annotations

from typing import Any

# Field names (document on the manifesto canvas).
RESOLVED_TOPIC = "resolved_topic"
COURSE_SHORTNAME = "course_shortname"
PASSAGE_IDS = "passage_ids"

_STATE: dict[str, dict[str, Any]] = {}


def ask_state_key(
    moodle_user_id: str | int | None,
    courseid: str | int | None = None,
    *,
    shortname: str | None = None,
) -> str:
    uid = str(moodle_user_id or "0")
    cid = int(courseid or 0)
    if cid:
        return f"moodle-{uid}-{cid}"
    sn = str(shortname or "").strip().casefold()
    if sn:
        return f"moodle-{uid}-{sn}"
    return f"moodle-{uid}-0"


def get_ask_state(key: str) -> dict[str, Any]:
    row = _STATE.get(str(key or ""))
    if not isinstance(row, dict):
        return {}
    return dict(row)


def put_ask_state(key: str, state: dict[str, Any] | None) -> None:
    if not key:
        return
    if not isinstance(state, dict) or not state:
        _STATE.pop(str(key), None)
        return
    _STATE[str(key)] = {
        RESOLVED_TOPIC: str(state.get(RESOLVED_TOPIC) or "").strip(),
        COURSE_SHORTNAME: str(state.get(COURSE_SHORTNAME) or "").strip(),
        PASSAGE_IDS: [
            str(pid)
            for pid in (state.get(PASSAGE_IDS) or [])
            if str(pid).strip()
        ][:8],
    }


def clear_ask_state(key: str | None = None) -> None:
    if key is None:
        _STATE.clear()
        return
    _STATE.pop(str(key), None)


def set_resolved_topic(
    state: dict[str, Any],
    *,
    topic: str,
    shortname: str,
    passage_ids: list[str],
) -> None:
    """Write the topic door’s resolution into a mutable state bag."""
    state[RESOLVED_TOPIC] = str(topic or "").strip()
    state[COURSE_SHORTNAME] = str(shortname or "").strip()
    state[PASSAGE_IDS] = [str(pid) for pid in passage_ids if str(pid).strip()][:8]
