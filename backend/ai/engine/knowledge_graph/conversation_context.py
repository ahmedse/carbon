"""
Conversation context dataclasses — Stage 7.

These are pure value objects (no I/O, no LLM deps) shared across the
turn_classifier, coreference_resolver, context_merger, session_store,
and multi_turn modules.

All dataclasses implement to_dict() / from_dict() for JSON persistence.
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


# ── Enumerations ───────────────────────────────────────────────────────────────

class TurnType(Enum):
    CONTINUATION = "continuation"   # adds dimension, sort, limit, viz to same question
    REFINEMENT   = "refinement"     # patches filters / time range on same question
    DRILL_DOWN   = "drill_down"     # narrows to a specific value from prior result
    NEW_TOPIC    = "new_topic"      # unrelated to prior turns


# ── Query context building blocks ──────────────────────────────────────────────

@dataclass
class Filter:
    field: str
    op: str          # "=" | "!=" | ">" | "<" | ">=" | "<=" | "in" | "not_in" | "like" | "between" | "is_null"
    value: Any
    label: str = ""  # human-readable, e.g. "last quarter"

    def to_dict(self) -> dict:
        return {"field": self.field, "op": self.op, "value": self.value, "label": self.label}

    @classmethod
    def from_dict(cls, d: dict) -> "Filter":
        return cls(field=d["field"], op=d["op"], value=d["value"], label=d.get("label", ""))


@dataclass
class TimeRange:
    description: str            # what the user said: "Q3 2025", "last 30 days"
    start: Optional[str] = None # ISO date string; None = open
    end: Optional[str] = None   # ISO date string; None = open

    def to_dict(self) -> dict:
        return {"description": self.description, "start": self.start, "end": self.end}

    @classmethod
    def from_dict(cls, d: dict) -> "TimeRange":
        return cls(description=d["description"], start=d.get("start"), end=d.get("end"))


@dataclass
class SortSpec:
    field: str
    direction: str = "desc"   # "asc" | "desc"

    def to_dict(self) -> dict:
        return {"field": self.field, "direction": self.direction}

    @classmethod
    def from_dict(cls, d: dict) -> "SortSpec":
        return cls(field=d["field"], direction=d.get("direction", "desc"))


@dataclass
class QueryContext:
    """
    Structured, serializable representation of "what we are currently looking at."
    Updated after each turn by ContextMerger.
    """
    metrics: list[str] = field(default_factory=list)       # ["revenue", "units_sold"]
    dimensions: list[str] = field(default_factory=list)    # ["product", "region"]
    filters: list[Filter] = field(default_factory=list)
    time_range: Optional[TimeRange] = None
    sort: Optional[SortSpec] = None
    limit: Optional[int] = None
    visualization: Optional[str] = None  # "bar", "line", "pie", "table", "stat", None
    entity_names: list[str] = field(default_factory=list)  # table names queried

    def is_empty(self) -> bool:
        return (
            not self.metrics
            and not self.dimensions
            and not self.filters
            and self.time_range is None
            and not self.entity_names
        )

    def to_summary_text(self) -> str:
        """Compact natural-language summary for LLM prompts."""
        parts: list[str] = []
        if self.metrics:
            parts.append(f"Metrics: {', '.join(self.metrics)}")
        if self.dimensions:
            parts.append(f"Dimensions: {', '.join(self.dimensions)}")
        if self.time_range:
            parts.append(f"Time range: {self.time_range.description}")
        if self.filters:
            filter_strs = [
                f.label or f"{f.field} {f.op} {f.value}"
                for f in self.filters
            ]
            parts.append(f"Filters: {'; '.join(filter_strs)}")
        if self.sort:
            parts.append(f"Sort: {self.sort.field} {self.sort.direction}")
        if self.limit:
            parts.append(f"Limit: {self.limit}")
        if self.visualization:
            parts.append(f"Visualization: {self.visualization}")
        if self.entity_names:
            parts.append(f"Tables: {', '.join(self.entity_names)}")
        return "; ".join(parts) if parts else "(empty context)"

    def to_dict(self) -> dict:
        return {
            "metrics": self.metrics,
            "dimensions": self.dimensions,
            "filters": [f.to_dict() for f in self.filters],
            "time_range": self.time_range.to_dict() if self.time_range else None,
            "sort": self.sort.to_dict() if self.sort else None,
            "limit": self.limit,
            "visualization": self.visualization,
            "entity_names": self.entity_names,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "QueryContext":
        return cls(
            metrics=d.get("metrics", []),
            dimensions=d.get("dimensions", []),
            filters=[Filter.from_dict(f) for f in d.get("filters", [])],
            time_range=TimeRange.from_dict(d["time_range"]) if d.get("time_range") else None,
            sort=SortSpec.from_dict(d["sort"]) if d.get("sort") else None,
            limit=d.get("limit"),
            visualization=d.get("visualization"),
            entity_names=d.get("entity_names", []),
        )


# ── Turn classification result ─────────────────────────────────────────────────

@dataclass
class TurnClassification:
    turn_type: TurnType
    confidence: float           # 0.0 – 1.0
    reasoning: str = ""         # short debug string


# ── Turn (one completed exchange) ─────────────────────────────────────────────

@dataclass
class Turn:
    turn_id: int
    user_utterance: str
    resolved_utterance: str
    generated_sql: str = ""
    result_summary: str = ""
    query_context: Optional[QueryContext] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "turn_id": self.turn_id,
            "user_utterance": self.user_utterance,
            "resolved_utterance": self.resolved_utterance,
            "generated_sql": self.generated_sql,
            "result_summary": self.result_summary,
            "query_context": self.query_context.to_dict() if self.query_context else None,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Turn":
        return cls(
            turn_id=d["turn_id"],
            user_utterance=d["user_utterance"],
            resolved_utterance=d["resolved_utterance"],
            generated_sql=d.get("generated_sql", ""),
            result_summary=d.get("result_summary", ""),
            query_context=QueryContext.from_dict(d["query_context"]) if d.get("query_context") else None,
            timestamp=d.get("timestamp", ""),
        )


# ── ConversationSession ────────────────────────────────────────────────────────

SESSION_EXPIRY_MINUTES = 30  # silence threshold for session reset


@dataclass
class ConversationSession:
    """
    Per-conversation rolling state.
    Persisted in SQLite as a JSON blob (ConversationContextRecord).
    """
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    instance_id: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    last_active_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    turns: list[Turn] = field(default_factory=list)
    active_context: QueryContext = field(default_factory=QueryContext)
    session_summary: str = ""   # regenerated every 10 turns

    def is_expired(self) -> bool:
        """True if the user has been silent for > SESSION_EXPIRY_MINUTES minutes."""
        try:
            last = datetime.fromisoformat(self.last_active_at)
            delta = datetime.now(timezone.utc) - last
            return delta.total_seconds() > SESSION_EXPIRY_MINUTES * 60
        except Exception:
            return False

    def touch(self) -> None:
        self.last_active_at = datetime.now(timezone.utc).isoformat()

    def reset_active_context(self) -> None:
        self.active_context = QueryContext()

    def recent_turns(self, n: int = 5) -> list[Turn]:
        return self.turns[-n:] if len(self.turns) >= n else list(self.turns)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "instance_id": self.instance_id,
            "created_at": self.created_at,
            "last_active_at": self.last_active_at,
            "turns": [t.to_dict() for t in self.turns],
            "active_context": self.active_context.to_dict(),
            "session_summary": self.session_summary,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ConversationSession":
        return cls(
            session_id=d.get("session_id", str(uuid.uuid4())),
            instance_id=d.get("instance_id", ""),
            created_at=d.get("created_at", ""),
            last_active_at=d.get("last_active_at", ""),
            turns=[Turn.from_dict(t) for t in d.get("turns", [])],
            active_context=QueryContext.from_dict(d.get("active_context", {})),
            session_summary=d.get("session_summary", ""),
        )


# ── ProcessedTurn — output of MultiTurnProcessor.process_turn() ───────────────

@dataclass
class ProcessedTurn:
    """Carries the pre-processed state before the agent is called."""
    resolved_utterance: str
    turn_type: TurnType = TurnType.NEW_TOPIC
    confidence: float = 1.0
    updated_context: Optional[QueryContext] = None
    session: Optional[ConversationSession] = None
    needs_clarification: bool = False
    clarification_question: str = ""
    clarification_choices: list[str] = field(default_factory=list)
