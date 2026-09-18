"""Working memory — per-conversation active entity focus store (GAP-2).

Redis-backed (Pulse 0.2 Phase A1). Holds a short stack of recently focused
entities per conversation so anaphora / "back to X" can restore a prior focus
without re-scanning full message history. Redis is the source of truth; the
in-process dict is a fallback only when Redis is unreachable.
"""
from __future__ import annotations

import json
import logging
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ai.engine.core.config import get_settings
from ai.engine.memory._redis import get_redis_client, memory_key

logger = logging.getLogger("pulse.memory.working")

#: Max prior focuses retained per conversation (current + history).
_FOCUS_STACK_MAX = 5

#: Entity types that are ephemeral intents, not restoreable named entities.
_NON_RESTORABLE_TYPES = frozenset({"pending_weather", "weather_resolution"})


@dataclass
class WorkingFocus:
    entity: str
    entity_type: str
    entity_id: str | None = None
    aliases: list[str] = field(default_factory=list)
    set_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


def _normalize_alias(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def _alias_tokens(value: str) -> list[str]:
    return [t for t in re.split(r"[\s,/]+", value.lower()) if t]


class WorkingMemory:
    """Per-conversation entity focus store backed by Redis with in-process fallback.

    Redis is the source of truth (L1). ``_store`` is used only when Redis is
    unreachable so callers degrade gracefully instead of crashing.

    Each conversation keeps a short **focus stack** (most recent first). 
    ``get_focus`` returns the head; prior entries remain searchable for
    named restore ("Back to Abrar").
    """

    def __init__(self) -> None:
        self._store: dict[str, list[WorkingFocus]] = {}
        self._lock = threading.Lock()

    # ── Redis plumbing ──────────────────────────────────────────────────

    def _key(self, conversation_id: str) -> str:
        return memory_key("wm", conversation_id)

    def _ttl(self) -> int:
        return get_settings().PULSE_MEMORY_REDIS_TTL_SECONDS

    @staticmethod
    def _focus_to_dict(focus: WorkingFocus) -> dict:
        return {
            "entity": focus.entity,
            "entity_type": focus.entity_type,
            "entity_id": focus.entity_id,
            "aliases": list(focus.aliases or []),
            "set_at": focus.set_at,
        }

    @staticmethod
    def _dict_to_focus(data: dict) -> WorkingFocus:
        aliases_raw = data.get("aliases") or []
        aliases = [
            _normalize_alias(a)
            for a in aliases_raw
            if isinstance(a, str) and _normalize_alias(a)
        ]
        return WorkingFocus(
            entity=str(data.get("entity") or ""),
            entity_type=str(data.get("entity_type") or "item"),
            entity_id=(
                str(data["entity_id"]).strip()
                if data.get("entity_id") not in (None, "")
                else None
            ),
            aliases=aliases,
            set_at=data.get("set_at") or datetime.now(timezone.utc).isoformat(),
        )

    @classmethod
    def _serialize_stack(cls, stack: list[WorkingFocus]) -> str:
        return json.dumps({"stack": [cls._focus_to_dict(f) for f in stack]})

    @classmethod
    def _deserialize_stack(cls, payload: str) -> list[WorkingFocus]:
        try:
            data = json.loads(payload)
        except (TypeError, ValueError):
            return []
        if isinstance(data, dict) and isinstance(data.get("stack"), list):
            out: list[WorkingFocus] = []
            for item in data["stack"]:
                if isinstance(item, dict):
                    out.append(cls._dict_to_focus(item))
            return out
        # Backward compat: single-focus payload from pre-stack WorkingMemory.
        if isinstance(data, dict) and data.get("entity"):
            return [cls._dict_to_focus(data)]
        return []

    def _read_stack(self, conversation_id: str) -> list[WorkingFocus]:
        client = get_redis_client()
        if client is not None:
            key = self._key(conversation_id)
            try:
                payload = client.get(key)
                if payload is None:
                    return []
                return self._deserialize_stack(payload)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Redis read failed for %s — falling back to in-process store: %s",
                    key,
                    exc,
                )

        with self._lock:
            return list(self._store.get(conversation_id) or [])

    def _write_stack(self, conversation_id: str, stack: list[WorkingFocus]) -> None:
        client = get_redis_client()
        if client is not None:
            key = self._key(conversation_id)
            try:
                if not stack:
                    client.delete(key)
                else:
                    client.set(
                        key, self._serialize_stack(stack), ex=self._ttl()
                    )
                # Keep in-process mirror consistent when Redis succeeds.
                with self._lock:
                    if stack:
                        self._store[conversation_id] = list(stack)
                    else:
                        self._store.pop(conversation_id, None)
                return
            except Exception as exc:  # noqa: BLE001 — lenient fallback
                logger.warning(
                    "Redis write failed for %s — falling back to in-process store: %s",
                    key,
                    exc,
                )

        with self._lock:
            if stack:
                self._store[conversation_id] = list(stack)
            else:
                self._store.pop(conversation_id, None)

    @staticmethod
    def _same_identity(a: WorkingFocus, b: WorkingFocus) -> bool:
        if a.entity_id and b.entity_id and a.entity_id == b.entity_id:
            return True
        return (
            a.entity.strip().lower() == b.entity.strip().lower()
            and a.entity_type == b.entity_type
            and not a.entity_id
            and not b.entity_id
        )

    @staticmethod
    def _mention_matches_focus(focus: WorkingFocus, mention: str) -> bool:
        """True when ``mention`` refers to this focus by id, name, or alias."""
        m = _normalize_alias(mention).lower()
        if len(m) < 2:
            return False
        if focus.entity_type in _NON_RESTORABLE_TYPES:
            return False

        candidates = [focus.entity, focus.entity_id or "", *(focus.aliases or [])]
        for raw in candidates:
            c = _normalize_alias(raw).lower()
            if not c:
                continue
            if c == m:
                return True
            # Token match: "Abrar" ↔ "Abrar Alam Azeemullah Ansari"
            tokens = _alias_tokens(c)
            if m in tokens:
                return True
            if len(m) >= 3 and any(tok.startswith(m) for tok in tokens):
                return True
            # Multi-word mention contained in candidate (or vice versa)
            if len(m) >= 3 and (m in c or c in m):
                return True
        return False

    # ── Public API ──────────────────────────────────────────────────────

    def set_focus(
        self,
        conversation_id: str,
        entity: str,
        entity_type: str = "item",
        *,
        entity_id: str | None = None,
        aliases: list[str] | None = None,
    ) -> None:
        """Push (or re-activate) an entity as the active focus for a conversation."""
        clean_aliases: list[str] = []
        seen: set[str] = set()
        for a in aliases or []:
            n = _normalize_alias(a)
            key = n.lower()
            if not n or key in seen:
                continue
            seen.add(key)
            clean_aliases.append(n)
        # Always index the surface name and stable id as aliases.
        for extra in (entity, entity_id):
            n = _normalize_alias(extra)
            key = n.lower()
            if n and key not in seen:
                seen.add(key)
                clean_aliases.append(n)

        focus = WorkingFocus(
            entity=_normalize_alias(entity) or (entity_id or ""),
            entity_type=entity_type,
            entity_id=_normalize_alias(entity_id) or None,
            aliases=clean_aliases,
        )
        stack = self._read_stack(conversation_id)
        stack = [f for f in stack if not self._same_identity(f, focus)]
        stack.insert(0, focus)
        stack = stack[:_FOCUS_STACK_MAX]
        self._write_stack(conversation_id, stack)

    def get_focus(self, conversation_id: str) -> WorkingFocus | None:
        """Return the active (most recent) entity focus, or None if not set."""
        stack = self._read_stack(conversation_id)
        return stack[0] if stack else None

    def get_focus_stack(self, conversation_id: str) -> list[WorkingFocus]:
        """Return the focus stack (most recent first). Empty if unset."""
        return self._read_stack(conversation_id)

    def find_prior_focus(
        self, conversation_id: str, mention: str
    ) -> WorkingFocus | None:
        """Find a stacked focus matching ``mention`` (name, alias, or id).

        Prefers the most recently focused match. Skips ephemeral weather intents.
        """
        mention_n = _normalize_alias(mention)
        if len(mention_n) < 2:
            return None
        for focus in self._read_stack(conversation_id):
            if self._mention_matches_focus(focus, mention_n):
                return focus
        return None

    def clear(self, conversation_id: str) -> None:
        """Remove the focus stack for a conversation."""
        self._write_stack(conversation_id, [])

    def to_prompt_fragment(self, conversation_id: str) -> str:
        """One-line context injection for LLM system prompts."""
        focus = self.get_focus(conversation_id)
        if not focus:
            return ""
        id_part = f" (id={focus.entity_id})" if focus.entity_id else ""
        return f"Currently active: {focus.entity}{id_part} (type: {focus.entity_type})"


# ── Process-level singleton ────────────────────────────────────────────────────

_working_memory: WorkingMemory | None = None


def get_working_memory() -> WorkingMemory:
    global _working_memory
    if _working_memory is None:
        _working_memory = WorkingMemory()
    return _working_memory


def update_focus_from_resolve_results(
    working_memory: WorkingMemory,
    conversation_id: str,
    completed_tools: list[dict] | None,
) -> WorkingFocus | None:
    """After tool execution, promote a successful ``resolve_entity`` match to focus.

    Stores a stable ``entity_id`` (employee_no when present) plus name aliases
    so later "Back to Abrar" can restore without re-asking who.
    """
    if not completed_tools:
        return None

    last_focus: WorkingFocus | None = None
    for tr in completed_tools:
        name = (tr.get("tool_name") or "").strip()
        if name != "resolve_entity":
            continue
        raw = tr.get("result")
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
        if not isinstance(raw, dict):
            continue
        # Match or unauthorized-but-identified both carry a record.
        record = raw.get("record")
        if not isinstance(record, dict) or not record:
            continue
        if not (raw.get("found") or raw.get("action") == "match"):
            continue

        emp_no = _normalize_alias(
            str(record.get("employee_no") or record.get("id") or "")
        )
        full_name = _normalize_alias(str(record.get("full_name") or ""))
        given = _normalize_alias(str(record.get("name_en_given") or ""))
        family = _normalize_alias(str(record.get("name_en_family") or ""))
        display = full_name or " ".join(p for p in (given, family) if p) or emp_no
        if not display:
            continue

        aliases: list[str] = []
        for a in (full_name, given, family, emp_no):
            if a:
                aliases.append(a)
        # First token of given/full name ("Abrar" from "Abrar Alam …")
        for source in (given, full_name):
            toks = _alias_tokens(source)
            if toks and len(toks[0]) >= 3:
                aliases.append(toks[0])

        working_memory.set_focus(
            conversation_id,
            display,
            "employee",
            entity_id=emp_no or None,
            aliases=aliases,
        )
        last_focus = working_memory.get_focus(conversation_id)

    return last_focus
