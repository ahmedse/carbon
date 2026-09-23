"""Durable per-conversation ConversationState (PV2-1A · ADR-0047 · contract §4.2).

One versioned, bounded, RBAC-redacted state object per conversation, loaded at
the start of every Chat turn and saved at every exit. Primary store is
``ConversationContextRecord.session_json`` (PK ``conversation_id``, tenancy
``(instance_id, conversation_id)`` + owner ``host_user_id``); Redis is a
best-effort mirror that is only read when the durable store is unavailable.

The rendered ``StateBlock`` is one block of the future ContextPack (§4.3); in
P1 only the draft prompt consumes it.

Schema v1 (top-level keys exactly)::

    version, focus[], intent{}, slots{}, open_question{}, last_results[],
    active_plans[], decisions[], language, surface_last

Engine-only: imports nothing from the Django host (import boundary).
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field, fields
from typing import Any, Iterable

from ai.engine.cognition.tool_digest import (
    _RECORD_LIST_KEYS,
    _RESTRICTED_KEY_RE,
    _allowed_org_units,
    _parse,
    _record_in_scope,
    build_tool_digest,
)
from ai.engine.cognition.turn.language import detect_reply_language
from ai.engine.core.models import ConversationContextRecord

logger = logging.getLogger("pulse.cognition.state_store")

_EMPTY_PAYSLIP_REPLY_RE = re.compile(
    r"no (?:committed )?payslips"
    r"|found no payslips"
    r"|no payslips (?:are |were )?(?:on file|found)"
    r"|لم أجد قسائم",
    re.IGNORECASE,
)

STATE_VERSION = 1
FOCUS_MAX = 5
LAST_RESULTS_MAX = 8
DECISIONS_MAX = 12
ACTIVE_PLANS_MAX = 5
STATE_BLOCK_MAX_CHARS = 600

# ``ConversationContextRecord.conversation_id`` is a varchar(36) primary key;
# longer ids cannot be stored (and must not poison the turn's transaction).
_CONVERSATION_ID_MAX = 36

_NON_FOCUS_TYPES = frozenset({"pending_weather", "weather_resolution"})
_SLOT_VALUE_MAX = 60
_LABEL_MAX = 80
_OPEN_QUESTION_TEXT_MAX = 200
_WHY_MAX = 80

_DICT_KEYS = ("intent", "slots", "open_question")
_LIST_KEYS = ("focus", "last_results", "active_plans", "decisions")


# ── State object ────────────────────────────────────────────────────────


@dataclass
class ConversationState:
    version: int = STATE_VERSION
    focus: list[dict] = field(default_factory=list)          # most recent first
    intent: dict = field(default_factory=dict)
    slots: dict = field(default_factory=dict)
    open_question: dict = field(default_factory=dict)
    last_results: list[dict] = field(default_factory=list)   # chronological
    active_plans: list[dict] = field(default_factory=list)
    decisions: list[dict] = field(default_factory=list)      # chronological
    language: str = ""
    surface_last: str = ""

    def bound(self) -> "ConversationState":
        self.focus = self.focus[:FOCUS_MAX]
        self.last_results = self.last_results[-LAST_RESULTS_MAX:]
        self.decisions = self.decisions[-DECISIONS_MAX:]
        self.active_plans = self.active_plans[:ACTIVE_PLANS_MAX]
        return self

    def to_dict(self) -> dict:
        self.bound()
        return json.loads(json.dumps(
            {f.name: getattr(self, f.name) for f in fields(self)},
            ensure_ascii=False, default=str,
        ))

    @classmethod
    def from_dict(cls, data: Any) -> "ConversationState":
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except (TypeError, ValueError):
                data = None
        if not isinstance(data, dict):
            return cls()
        state = cls()
        for key in _DICT_KEYS:
            value = data.get(key)
            if isinstance(value, dict):
                setattr(state, key, dict(value))
        for key in _LIST_KEYS:
            value = data.get(key)
            if isinstance(value, list):
                setattr(state, key, [dict(v) for v in value if isinstance(v, dict)])
        for key in ("language", "surface_last"):
            value = data.get(key)
            if isinstance(value, str):
                setattr(state, key, value)
        return state.bound()

    def is_empty(self) -> bool:
        return not any(
            getattr(self, key) for key in (*_DICT_KEYS, *_LIST_KEYS, "language")
        )

    def next_turn(self) -> int:
        turns = [
            d.get("turn") for d in self.decisions if isinstance(d.get("turn"), int)
        ]
        return (max(turns) + 1) if turns else 1

    def size(self) -> int:
        return len(json.dumps(self.to_dict(), ensure_ascii=False))


def upsert_active_plan(
    state: ConversationState | None,
    *,
    plan_id: str = "",
    status: str,
    title: str = "",
    slots: dict | None = None,
    step_summary: str = "",
) -> ConversationState | None:
    """Write-back one plan lifecycle event onto ``state.active_plans`` (most recent first)."""
    if state is None:
        return None
    status_n = (status or "").strip() or "pending_approval"
    pid = (plan_id or "").strip()
    title_n = (title or "").strip()
    body = {
        k: v for k, v in (slots or {}).items()
        if v not in (None, "", [], {})
    }
    entry = {
        "plan_id": pid,
        "status": status_n,
        "title": title_n,
        "slots": body,
        "step_summary": (step_summary or "").strip()[:200],
    }
    rest = []
    for item in state.active_plans or []:
        if not isinstance(item, dict):
            continue
        same_id = pid and (item.get("plan_id") or "") == pid
        same_handoff = (
            not pid
            and not item.get("plan_id")
            and (item.get("title") or "") == title_n
        )
        if same_id or same_handoff:
            continue
        rest.append(item)
    state.active_plans = [entry, *rest][:ACTIVE_PLANS_MAX]
    return state


@dataclass
class TurnStateContext:
    """Turn-scoped carrier: the loaded state plus signals known mid-turn."""

    state: ConversationState
    intent: Any = None


# ── RBAC redaction ──────────────────────────────────────────────────────


def _entry_in_scope(entry: dict, allowed: set[str]) -> bool:
    if not _record_in_scope(entry, allowed):
        return False
    return all(
        _record_in_scope({"org_unit_id": org}, allowed)
        for org in entry.get("org_unit_ids") or []
    )


def redact_state(state: ConversationState, scope: dict | None) -> ConversationState:
    """Drop focus / last_results entries tagged with an org unit outside ``scope``.

    Same rule as the tool digest: with no scope only untagged entries survive.
    """
    allowed = _allowed_org_units(scope)
    state.focus = [f for f in state.focus if _entry_in_scope(f, allowed)]
    state.last_results = [r for r in state.last_results if _entry_in_scope(r, allowed)]
    return state


# ── Turn update ─────────────────────────────────────────────────────────


def _parse_args(raw: Any) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _clean_slots(body: dict) -> dict:
    out: dict = {}
    for key, value in (body or {}).items():
        if _RESTRICTED_KEY_RE.search(str(key)):
            continue
        if isinstance(value, bool) or isinstance(value, (int, float)):
            out[str(key)] = value
        elif isinstance(value, str) and value.strip():
            text = " ".join(value.split())
            out[str(key)] = text[:_SLOT_VALUE_MAX]
    return out


def _write_intent(
    completed_tools: Iterable[dict] | None, draft_tool_calls: Iterable[dict] | None,
) -> tuple[str, dict] | None:
    """(api_name, body) of this turn's write intent — a Chat handoff draft
    (ADR-0046: the mutation was cancelled, the extracted values survive) or,
    failing that, a drafted ``call_host_api`` with a body."""
    for item in completed_tools or []:
        if not isinstance(item, dict):
            continue
        data = _parse(item.get("result"))
        if isinstance(data, dict) and data.get("action") == "chat_handoff":
            draft = data.get("draft") if isinstance(data.get("draft"), dict) else {}
            return str(data.get("api_name") or ""), draft
    for call in draft_tool_calls or []:
        if not isinstance(call, dict):
            continue
        fn = call.get("function") or {}
        if fn.get("name") != "call_host_api":
            continue
        args = _parse_args(fn.get("arguments"))
        body = args.get("body")
        if isinstance(body, dict) and body:
            return str(args.get("api_name") or ""), body
    return None


def _intent_action(intent: Any) -> str:
    action = str(getattr(intent, "action", "") or "")
    candidates = getattr(intent, "candidates", None) or []
    if action == "answer" and candidates:
        return str(getattr(candidates[0], "name", "") or action)
    return action


def _result_org_units(data: Any, allowed: set[str]) -> list[str]:
    if isinstance(data, dict) and "data" in data and "status_code" in data:
        data = data["data"]
    records: list[dict] = []
    if isinstance(data, list):
        records = [r for r in data if isinstance(r, dict)]
    elif isinstance(data, dict):
        records = [data]
        for key in _RECORD_LIST_KEYS:
            if isinstance(data.get(key), list):
                records.extend(r for r in data[key] if isinstance(r, dict))
    orgs: set[str] = set()
    for record in records:
        org = record.get("org_unit_id", record.get("org_unit"))
        if isinstance(org, dict):
            org = org.get("id")
        if org is not None and str(org) in allowed:
            orgs.add(str(org))
    return sorted(orgs)


def _tag_org_units(entry: dict, orgs: list[str]) -> dict:
    if len(orgs) == 1:
        entry["org_unit_id"] = orgs[0]
    elif orgs:
        entry["org_unit_ids"] = orgs
    return entry


def _last_result_entries(
    completed_tools: Iterable[dict] | None, scope: dict | None, turn: int,
) -> list[dict]:
    allowed = _allowed_org_units(scope)
    entries: list[dict] = []
    for item in completed_tools or []:
        if not isinstance(item, dict) or item.get("error"):
            continue
        data = _parse(item.get("result"))
        # S-TRACE-01 synthetic retrieval step ({"count": n}) is not a tool fact.
        if isinstance(data, dict) and set(data) == {"count"}:
            continue
        digest = build_tool_digest([item], scope)
        if not digest:
            continue
        args = item.get("tool_args") if isinstance(item.get("tool_args"), dict) else {}
        call_id = item.get("tool_call_id") or ""
        entry = {
            "turn": turn,
            "tool": str(item.get("tool_name") or ""),
            "api": str(args.get("api_name") or ""),
            "digest": digest,
            "ref": f"tool_call:{call_id}" if call_id else "",
        }
        entries.append(_tag_org_units(entry, _result_org_units(data, allowed)))
    return entries


def _resolved_org_units(completed_tools: Iterable[dict] | None) -> dict[str, str]:
    """``entity id → org_unit_id`` from this turn's ``resolve_entity`` records."""
    out: dict[str, str] = {}
    for item in completed_tools or []:
        if not isinstance(item, dict) or item.get("tool_name") != "resolve_entity":
            continue
        data = _parse(item.get("result"))
        record = data.get("record") if isinstance(data, dict) else None
        if not isinstance(record, dict):
            continue
        entity_id = str(record.get("employee_no") or record.get("id") or "").strip()
        org = record.get("org_unit_id", record.get("org_unit"))
        if isinstance(org, dict):
            org = org.get("id")
        if entity_id and org is not None:
            out[entity_id] = str(org)
    return out


def _focus_key(entry: dict) -> tuple[str, str]:
    return (
        str(entry.get("type") or ""),
        str(entry.get("id") or "") or str(entry.get("label") or "").strip().lower(),
    )


def _focus_entries(
    focus_stack: Iterable[Any],
    prior_focus: list[dict],
    org_by_id: dict[str, str],
    turn: int,
) -> list[dict]:
    prior_by_key = {_focus_key(f): f for f in prior_focus}
    prior_head = _focus_key(prior_focus[0]) if prior_focus else None
    out: list[dict] = []
    for wf in focus_stack:
        entity_type = str(getattr(wf, "entity_type", "") or "item")
        if entity_type in _NON_FOCUS_TYPES:
            continue
        label = " ".join(str(getattr(wf, "entity", "") or "").split())[:_LABEL_MAX]
        entity_id = str(getattr(wf, "entity_id", "") or "")
        if not label and not entity_id:
            continue
        entry = {"type": entity_type, "id": entity_id, "label": label}
        key = _focus_key(entry)
        prior = prior_by_key.get(key)
        is_new_head = not out and key != prior_head
        entry["turn"] = turn if (prior is None or is_new_head) else prior.get("turn", turn)
        org = org_by_id.get(entity_id) or (prior or {}).get("org_unit_id")
        if org is not None:
            entry["org_unit_id"] = str(org)
        out.append(entry)
        if len(out) >= FOCUS_MAX:
            break
    return out


def update_state_from_turn(
    state: ConversationState,
    *,
    decision: str,
    user_message: str = "",
    response_text: str = "",
    fired_gates: Iterable[str] | None = None,
    intent: Any = None,
    completed_tools: list[dict] | None = None,
    draft_tool_calls: list[dict] | None = None,
    focus_stack: Iterable[Any] | None = None,
    scope: dict | None = None,
    surface: str = "chat",
    arbiter_shadow: dict | None = None,
) -> ConversationState:
    """Fold one finished turn's signals into ``state`` (in place) and bound it."""
    turn = state.next_turn()

    if (user_message or "").strip():
        state.language = detect_reply_language(user_message)
    state.surface_last = surface

    if intent is not None:
        zone = str(getattr(intent, "zone", "") or "")
        action = _intent_action(intent)
        prior = state.intent or {}
        same = prior.get("zone") == zone and prior.get("action") == action
        new_intent = {
            "zone": zone,
            "action": action,
            "confidence": round(float(getattr(intent, "confidence", 0.0) or 0.0), 2),
            "since_turn": prior.get("since_turn", turn) if same else turn,
        }
        if prior.get("api"):
            new_intent["api"] = prior["api"]
        state.intent = new_intent

    write = _write_intent(completed_tools, draft_tool_calls)
    if write is not None:
        api, body = write
        prior_api = (state.intent or {}).get("api")
        if api and prior_api and api != prior_api:
            state.slots = {}
        merged = dict(state.slots)
        merged.update(_clean_slots(body))
        state.slots = merged
        if api:
            prior = state.intent or {}
            state.intent = {
                "zone": prior.get("zone") or "platform",
                "action": api,
                "confidence": prior.get("confidence", 0.0),
                "since_turn": prior.get("since_turn", turn) if prior_api == api else turn,
                "api": api,
            }

    state.last_results = state.last_results + _last_result_entries(
        completed_tools, scope, turn,
    )
    if _EMPTY_PAYSLIP_REPLY_RE.search(response_text or ""):
        already = any(
            "list_my_payslips" in str(row.get("api") or row.get("digest") or "")
            and (
                "count=0" in str(row.get("digest") or "")
                or "results=[]" in str(row.get("digest") or "")
            )
            for row in state.last_results
            if isinstance(row, dict)
        )
        if not already:
            state.last_results.append({
                "turn": turn,
                "tool": "call_host_api",
                "api": "list_my_payslips",
                "digest": "call_host_api list_my_payslips: count=0",
            })

    if focus_stack is not None:
        stack = list(focus_stack)
        if stack:
            state.focus = _focus_entries(
                stack, state.focus, _resolved_org_units(completed_tools), turn,
            )

    if decision == "clarify":
        state.open_question = {
            "slot": "",
            "asked_turn": turn,
            "text": " ".join((response_text or "").split())[:_OPEN_QUESTION_TEXT_MAX],
        }
    else:
        state.open_question = {}

    fired = [g for g in (fired_gates or []) if g]
    row = {
        "turn": turn,
        "decision": decision or "answer",
        "why": (",".join(fired) or "draft")[:_WHY_MAX],
    }
    if isinstance(arbiter_shadow, dict):
        if arbiter_shadow.get("arbiter"):
            row["arbiter"] = str(arbiter_shadow.get("arbiter"))
        if "agree" in arbiter_shadow:
            row["agree"] = bool(arbiter_shadow.get("agree"))
    state.decisions = state.decisions + [row]
    return state.bound()


def seed_working_memory(working_memory: Any, conversation_id: str, state: ConversationState) -> bool:
    """Re-seed an empty working-memory focus stack from durable state."""
    if not state.focus or working_memory.get_focus_stack(conversation_id):
        return False
    for entry in reversed(state.focus):
        working_memory.set_focus(
            conversation_id,
            entry.get("label") or entry.get("id") or "",
            entry.get("type") or "item",
            entity_id=entry.get("id") or None,
        )
    return True


# ── StateBlock ──────────────────────────────────────────────────────────


def _fmt_slot(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def render_state_block(state: ConversationState, max_chars: int = STATE_BLOCK_MAX_CHARS) -> str:
    """Render the prompt ``StateBlock`` (≤ ``max_chars``); ``""`` when empty.

    Lines are ordered by importance so truncation drops the least useful.
    """
    lines: list[str] = []
    if state.slots:
        lines.append(
            "Details the user already gave (do not ask again): "
            + ", ".join(f"{k}={_fmt_slot(v)}" for k, v in state.slots.items())
        )
    if state.open_question.get("text"):
        lines.append(
            f"You asked (turn {state.open_question.get('asked_turn', '?')}): "
            f"{state.open_question['text']}"
        )
    intent = state.intent or {}
    if intent.get("action") or intent.get("zone"):
        since = intent.get("since_turn")
        lines.append(
            f"Current intent: {intent.get('action') or '-'} ({intent.get('zone') or '-'}"
            + (f", since turn {since})" if since else ")")
        )
    if state.focus:
        lines.append("In focus: " + "; ".join(
            f"{f.get('label') or f.get('id')} ({f.get('type')}"
            + (f" {f['id']}" if f.get("id") and f.get("id") != f.get("label") else "")
            + ")"
            for f in state.focus[:3]
        ))
    if state.last_results:
        lines.append("Earlier tool results: " + " | ".join(
            f"t{r.get('turn')} {r.get('digest')}" for r in reversed(state.last_results[-3:])
        ))
    if state.active_plans:
        lines.append("Active plans: " + "; ".join(
            f"{p.get('title') or p.get('plan_id')} ({p.get('status')})"
            for p in state.active_plans[:3]
        ))
    if state.language:
        lines.append(f"User's last language: {state.language}")
    if not lines:
        return ""

    out = "CONVERSATION STATE (from earlier turns of this conversation):"
    for line in lines:
        candidate = f"{out}\n- {line}"
        if len(candidate) <= max_chars:
            out = candidate
            continue
        room = max_chars - len(out) - 4
        if room > 20:
            out = f"{out}\n- {line[: room - 1].rstrip()}…"
        break
    return out[:max_chars]


# ── Redis mirror (best-effort) ──────────────────────────────────────────


def _mirror_key(instance_id: str, conversation_id: str) -> str:
    return f"pulse:cs:{instance_id}:{conversation_id}"


def _mirror_client():
    try:
        from ai.engine.memory._redis import get_redis_client

        return get_redis_client()
    except Exception:  # noqa: BLE001 — mirror is optional
        return None


def _mirror_set(instance_id: str, conversation_id: str, owner: str | None, data: dict) -> None:
    client = _mirror_client()
    if client is None:
        return
    try:
        from ai.engine.core.config import get_settings

        client.set(
            _mirror_key(instance_id, conversation_id),
            json.dumps({"instance_id": instance_id, "host_user_id": owner, "state": data},
                       ensure_ascii=False),
            ex=get_settings().PULSE_MEMORY_REDIS_TTL_SECONDS,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("ConversationState mirror write failed conv=%s: %s", conversation_id[:8], exc)


def _mirror_get(instance_id: str, conversation_id: str) -> dict | None:
    client = _mirror_client()
    if client is None:
        return None
    try:
        raw = client.get(_mirror_key(instance_id, conversation_id))
        data = json.loads(raw) if raw else None
        return data if isinstance(data, dict) else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("ConversationState mirror read failed conv=%s: %s", conversation_id[:8], exc)
        return None


def _mirror_delete(instance_id: str, conversation_id: str) -> None:
    client = _mirror_client()
    if client is None:
        return
    try:
        client.delete(_mirror_key(instance_id, conversation_id))
    except Exception as exc:  # noqa: BLE001
        logger.warning("ConversationState mirror delete failed conv=%s: %s", conversation_id[:8], exc)


# ── Store ───────────────────────────────────────────────────────────────


def _owner(host_user_id: Any) -> str | None:
    return None if host_user_id in (None, "") else str(host_user_id)


def _storable(conversation_id: str | None) -> bool:
    return bool(conversation_id) and len(conversation_id) <= _CONVERSATION_ID_MAX


class ConversationStateStore:
    """Load / save / clear ConversationState for ``(instance_id, conversation_id)``.

    The row owner (``host_user_id``) must match the caller, otherwise state is
    neither loaded nor overwritten.
    """

    def __init__(self, db=None):
        self.db = db

    async def _row(self, conversation_id: str):
        rows = await self.db.select(
            ConversationContextRecord, {"conversation_id": conversation_id},
        )
        for row in rows or []:
            if getattr(row, "conversation_id", None) == conversation_id:
                return row
        return None

    async def load(
        self,
        instance_id: str,
        conversation_id: str,
        host_user_id: Any,
        *,
        scope: dict | None = None,
    ) -> ConversationState:
        payload = owner = row_instance = None
        from_db = False
        if self.db is not None and _storable(conversation_id):
            try:
                row = await self._row(conversation_id)
                from_db = True
                if row is not None:
                    payload = row.session_json
                    owner = getattr(row, "host_user_id", None)
                    row_instance = row.instance_id
            except Exception:  # noqa: BLE001 — fall back to the mirror
                logger.warning(
                    "ConversationState DB load failed conv=%s", conversation_id[:8],
                    exc_info=True,
                )
        if not from_db and conversation_id:
            mirror = _mirror_get(instance_id, conversation_id)
            if mirror:
                payload = mirror.get("state")
                owner = mirror.get("host_user_id")
                row_instance = mirror.get("instance_id")
        if payload is None:
            return ConversationState()
        if row_instance != instance_id:
            logger.warning(
                "ConversationState not loaded conv=%s: instance mismatch",
                conversation_id[:8],
            )
            return ConversationState()
        if _owner(owner) != _owner(host_user_id):
            logger.warning(
                "ConversationState not loaded conv=%s: owner mismatch",
                conversation_id[:8],
            )
            return ConversationState()
        return redact_state(ConversationState.from_dict(payload), scope)

    async def save(
        self,
        instance_id: str,
        conversation_id: str,
        host_user_id: Any,
        state: ConversationState,
    ) -> bool:
        """Persist ``state``; ``True`` only when the durable row was written."""
        data = state.to_dict()
        owner = _owner(host_user_id)
        saved = False
        if self.db is not None and _storable(conversation_id):
            try:
                row = await self._row(conversation_id)
                if row is None:
                    self.db.add(ConversationContextRecord(
                        conversation_id=conversation_id,
                        instance_id=instance_id,
                        session_json=data,
                        host_user_id=owner,
                    ))
                elif row.instance_id != instance_id or _owner(
                    getattr(row, "host_user_id", None)
                ) != owner:
                    logger.warning(
                        "ConversationState not saved conv=%s: row belongs to "
                        "another instance/owner", conversation_id[:8],
                    )
                    return False
                else:
                    row.session_json = data
                await self.db.commit()
                saved = True
            except Exception:  # noqa: BLE001 — state must never fail a turn
                logger.warning(
                    "ConversationState save failed conv=%s", conversation_id[:8],
                    exc_info=True,
                )
        if conversation_id:
            _mirror_set(instance_id, conversation_id, owner, data)
        return saved

    async def clear(self, conversation_id: str, *, instance_id: str | None = None) -> dict | None:
        """Delete the state (row + mirror + working-memory focus).

        Returns ``{"instance_id", "host_user_id", "state"}`` of the removed row
        so a clear can be undone via :meth:`restore`; ``None`` when absent.
        """
        prior = None
        if self.db is not None and _storable(conversation_id):
            row = await self._row(conversation_id)
            if row is not None:
                prior = {
                    "instance_id": row.instance_id,
                    "host_user_id": getattr(row, "host_user_id", None),
                    "state": ConversationState.from_dict(row.session_json).to_dict(),
                }
                instance_id = instance_id or row.instance_id
                await self.db.delete(row)
        if instance_id and conversation_id:
            _mirror_delete(instance_id, conversation_id)
        try:
            from ai.engine.memory.working import get_working_memory

            get_working_memory().clear(conversation_id)
        except Exception:  # noqa: BLE001
            logger.debug("working-memory clear skipped", exc_info=True)
        return prior

    async def restore(self, conversation_id: str, snapshot: dict | None) -> bool:
        """Re-save a snapshot returned by :meth:`clear` (undo of /clear)."""
        if not isinstance(snapshot, dict) or not snapshot.get("instance_id"):
            return False
        return await self.save(
            snapshot["instance_id"],
            conversation_id,
            snapshot.get("host_user_id"),
            ConversationState.from_dict(snapshot.get("state")),
        )
