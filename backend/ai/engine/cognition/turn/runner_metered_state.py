"""Mutable turn state shared across extracted _run_metered stage modules."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MeteredTurnState:
    """Cross-stage mutable locals for one metered turn."""

    user_message: str
    total_tokens: int = 0
    total_llm_calls: int = 0
    discuss_thread: bool = False
    discuss_ctx: bool = False
    plan_revision_ref: dict | None = None  # {plan_id, title} the Chat refine targets (typed, from state)
    chat_handoff: Any = None
    ess_bound: Any = None
    intent_resolution: Any = None
    is_weather_rewrite_turn: bool = False
    wm: Any = None
    pref_store: Any = None
    salience: Any = None
    s1_start: float = 0.0
    retrieval: Any = None
    s2_latency: float = 0.0
    draft: Any = None
    critic: Any = None
    execution: Any = None
    final_text: str = ""
    synth: dict | None = None
    forced_tool_call: dict | None = None  # I2: injected tool call for open_question_confirm
    deixis_subject: str = ""  # I6: subject resolved from state for "those"/"that one"
    dense_thinking: bool = False  # client opt-in: denser Thought panel (ADR-0054)
