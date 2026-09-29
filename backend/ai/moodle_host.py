"""Moodle host seam for Pulse Ask.

Pure functions only — no Django, no Moodle imports. The PHP plugin sends a
course snapshot; this module checks the dial and the HMAC, then builds the
Ask messages. College words stay here and in domain_packs/aast-med, not in
engine/.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from pathlib import Path
from typing import Any

ASK_MODE = "ask"
MAX_SKEW_SECONDS = 120
COURSE_LIST_BLOCKS = ("course_list", "course_list_empty")
COURSE_LIST_ANSWERS = {
    "course_list_empty": (
        "This is not on the course list. Pulse has no courses configured. "
        "A site administrator adds course shortnames in the Pulse settings."
    ),
    "course_list": (
        "This is not on the course list. Open a course an administrator "
        "has added to the Pulse course list."
    ),
}


def reject_dial(pulse_mode: str | None) -> str | None:
    """Return an error code when the dial is not Ask."""
    mode = (pulse_mode or ASK_MODE).strip().lower()
    if mode != ASK_MODE:
        return "ask_only"
    return None


def verify_signature(secret: str, timestamp: str, body: bytes, signature: str, *, now: int | None = None) -> bool:
    if not secret or not timestamp or not signature:
        return False
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False
    current = int(time.time() if now is None else now)
    if abs(current - ts) > MAX_SKEW_SECONDS:
        return False
    expected = hmac.new(secret.encode("utf-8"), f"{ts}.".encode("utf-8") + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.strip())


INSTANCE_ID = "aast-med"


def course_block(snapshot: dict[str, Any] | None) -> str:
    block = str((snapshot or {}).get("block") or "")
    if block in COURSE_LIST_BLOCKS:
        return block
    return ""


class AskDecision:
    """Result of the door checks. A chat payload exists only when Ask may run."""

    def __init__(
        self,
        *,
        error: str | None = None,
        status: int = 200,
        answer: str | None = None,
        refusal: str | None = None,
        chat: dict[str, Any] | None = None,
    ) -> None:
        self.error = error
        self.status = status
        self.answer = answer
        self.refusal = refusal
        self.chat = chat


def prepare_embed(payload: dict[str, Any] | None) -> AskDecision:
    """Ticket for the pane, or a rejection. A blocked page never becomes context."""
    if not isinstance(payload, dict):
        return AskDecision(error="bad_json", status=400)
    dial_error = reject_dial(payload.get("pulse_mode"))
    if dial_error:
        return AskDecision(error=dial_error, status=403)
    snapshot = payload.get("snapshot") if isinstance(payload.get("snapshot"), dict) else {}
    host_context = payload.get("host_context") if isinstance(payload.get("host_context"), dict) else {}
    block = course_block(snapshot)
    if block:
        return AskDecision(error=block, refusal=block, status=403)
    return AskDecision(answer=page_context_from_snapshot(host_context, snapshot))


def prepare_ask(payload: dict[str, Any] | None) -> AskDecision:
    """Ask, a typed refusal, or a dial rejection. Refusals do not build a chat."""
    if not isinstance(payload, dict):
        return AskDecision(error="bad_json", status=400)
    dial_error = reject_dial(payload.get("pulse_mode"))
    if dial_error:
        return AskDecision(error=dial_error, status=403)
    snapshot = payload.get("snapshot") if isinstance(payload.get("snapshot"), dict) else {}
    host_context = payload.get("host_context") if isinstance(payload.get("host_context"), dict) else {}
    block = course_block(snapshot)
    if block:
        return AskDecision(answer=COURSE_LIST_ANSWERS[block], refusal=block)
    from ai.moodle_refusals import answer_for, classify
    from ai.moodle_onboarding import answer as onboarding_answer

    message = str(payload.get("message") or "")
    kind = classify(message)
    if kind:
        return AskDecision(answer=answer_for(kind), refusal=kind)
    howto = onboarding_answer(message, snapshot)
    if howto:
        return AskDecision(answer=howto)
    from ai.moodle_page import access_answer, lecture_answer, section_answer

    reason = access_answer(message, snapshot)
    if reason:
        return AskDecision(answer=reason, refusal=str(snapshot.get("access") or ""))
    lecture = lecture_answer(message, snapshot)
    if lecture:
        return AskDecision(answer=lecture)
    cited = section_answer(message, snapshot)
    if cited:
        return AskDecision(answer=cited)
    chat = chat_payload(
        message,
        host_context,
        snapshot,
        payload.get("moodle_user_id"),
    )
    if chat.get("process_mode") != ASK_MODE:
        return AskDecision(error="ask_only", status=403)
    return AskDecision(chat=chat)


def page_context_from_snapshot(host_context: dict[str, Any], snapshot: dict[str, Any]) -> str:
    """Facts the turn prompt already knows how to render as the current page.

    This is host context for the real chat spine, not a second system prompt.
    """
    block = course_block(snapshot)
    if block:
        return (
            f"{COURSE_LIST_ANSWERS[block]}\n"
            "Do not name a course. Do not describe its contents."
        )
    course = snapshot.get("course") or {}
    sections = snapshot.get("sections") or []
    audience = host_context.get("audience") or snapshot.get("audience") or "unknown"
    if course and not course.get("visible_to_user"):
        return (
            f"Moodle audience: {audience}.\n"
            "The user cannot see the requested course. "
            "Reply only that they cannot see it and there is nothing to cite. "
            "Do not guess why. Do not name the course. Do not describe its contents."
        )
    lines: list[str] = [f"Moodle audience: {audience}."]
    if course.get("visible_to_user"):
        lines.append(
            f"Open course {course.get('fullname')} ({course.get('shortname')}) "
            f"id={course.get('id')} category={course.get('category')} format={course.get('format')}."
        )
    else:
        lines.append("No course is open. Do not invent a course page.")
    if snapshot.get("audience") == "student" and course.get("visible_to_user") and not snapshot.get("enrolled"):
        lines.append("This student is not enrolled in the open course.")
    lines.append("Cite only these sections. If a fact is not listed, say it is not on this page.")
    if not sections:
        lines.append("Sections: (none).")
    else:
        lines.append("Sections:")
        for section in sections[:40]:
            flag = "" if section.get("visible", True) else " [hidden]"
            name = section.get("name") or "(untitled)"
            lines.append(f"- {section.get('number')}: {name}{flag}")
    activity = snapshot.get("activity") if isinstance(snapshot.get("activity"), dict) else None
    if activity and activity.get("name"):
        lines.append(
            "Open activity "
            f"{activity.get('name')} cmid={activity.get('cmid')} "
            f"module={activity.get('module')} section={activity.get('section')}."
        )
    if snapshot.get("sections_truncated"):
        lines.append("Further sections exist and were not included.")
    lines.append(
        "No clinical advice. No claim that Moodle was changed. "
        "Teaching outlines are drafts. Not a mentorship caseload."
    )
    return "\n".join(lines)


def chat_payload(
    message: str,
    host_context: dict[str, Any],
    snapshot: dict[str, Any],
    moodle_user_id: str | int | None,
) -> dict[str, Any]:
    """Payload for dispatch_task('chat'). Dial is always ask."""
    uid = str(moodle_user_id or "0")
    courseid = int((host_context or {}).get("courseid") or snapshot.get("courseid") or 0)
    return {
        "message": (message or "").strip() or "What is on this course?",
        "process_mode": ASK_MODE,
        "host_user_id": f"moodle:{uid}",
        "app_identifier": "moodle",
        "page_context": page_context_from_snapshot(host_context, snapshot),
        "conversation_history": {
            "conversation_id": f"moodle-{uid}-{courseid}",
            "messages": [],
        },
    }


def configured_secret(explicit: str = "") -> str:
    """HMAC secret from settings, then the environment, then a local file.

    The file lets a running dev server pick up the secret without a restart.
    """
    if explicit:
        return explicit
    env = os.environ.get("MOODLE_PULSE_HMAC_SECRET", "")
    if env:
        return env
    path = Path(__file__).resolve().parents[1] / ".moodle_pulse_secret"
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    return text


_TICKETS: dict[str, tuple[float, dict[str, Any]]] = {}
_TICKET_TTL = 600


def issue_ticket(page_context: str, moodle_user_id: str | int | None) -> str:
    now = time.time()
    stale = [key for key, (exp, _) in _TICKETS.items() if exp < now]
    for key in stale:
        _TICKETS.pop(key, None)
    ticket = secrets.token_urlsafe(32)
    _TICKETS[ticket] = (now + _TICKET_TTL, {
        "page_context": page_context,
        "moodle_user_id": str(moodle_user_id or "0"),
    })
    return ticket


def take_ticket(ticket: str) -> dict[str, Any] | None:
    row = _TICKETS.pop(str(ticket or ""), None)
    if not row:
        return None
    expires, payload = row
    if expires < time.time():
        return None
    return payload


