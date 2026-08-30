"""S1 — Salience (regex intent classification, no LLM).

Routes user messages into one of four domains and chooses a processing
route (fast / full / deep). Also detects urgency keywords to bump weight.
"""
import logging

from ai.engine.agent.reasoning import _CONVERSATIONAL_RE, _IDENTITY_RE
from ai.engine.cognition.turn.witnesses import SalienceResult

logger = logging.getLogger("pulse.cognition.turn.salience")

# ── Data / operational question patterns ──────────────────────────────────────

_TREND_PATTERNS = [
    "how many", "count of", "total", "average", "max", "min",
    "list", "show me", "what are the", "find", "search",
    "compare", "trend", "over time", "breakdown", "dataset",
    "data", "query", "sql", "table", "column", "schema",
    "training", "prediction", "model version", "engine",
    "accuracy", "precision", "recall", "metric",
]

_URGENCY_KEYWORDS = {"urgent", "asap", "critical", "broken", "down", "error", "failing", "emergency"}

# Reasoning-heavy signals → route to the "deep" lane. A "why"/"explain"/
# "root cause" question needs genuine reasoning, not a plain data lookup.
_DEEP_PATTERNS = [
    "why", "explain", "analyze", "analyse", "evaluate", "assess",
    "trade-off", "tradeoff", "implication", "justify", "root cause",
    "what if", "synthesize", "synthesise", "hypothesize", "reasoning",
]


class SalienceWitness:
    """Regex-based intent classifier. Zero LLM cost."""

    async def assess(self, user_message: str) -> SalienceResult:
        msg_lower = user_message.lower().strip()

        # ── Conversational ──
        if _CONVERSATIONAL_RE.match(user_message):
            return SalienceResult(
                weight=0.1,
                domain="conversational",
                route="fast",
                salience_features={"matched": "conversational_regex"},
            )

        # ── Identity ──
        if _IDENTITY_RE.search(user_message):
            return SalienceResult(
                weight=0.3,
                domain="identity",
                route="fast",
                salience_features={"matched": "identity_regex"},
            )

        # ── Data / operational ──
        if any(p in msg_lower for p in _TREND_PATTERNS):
            weight = 0.8
            route = "full"
            features = {"matched": "data_patterns"}
            # Urgency bump
            if any(kw in msg_lower for kw in _URGENCY_KEYWORDS):
                weight = min(1.0, weight + 0.3)
                features["urgency"] = True
            # Deep reasoning bump — a data question that also asks "why" /
            # "explain" / "root cause" needs the reasoning lane, not a lookup.
            if any(p in msg_lower for p in _DEEP_PATTERNS):
                route = "deep"
                features["matched"] = "deep_patterns"
                weight = min(1.0, weight + 0.1)
            return SalienceResult(
                weight=weight,
                domain="data",
                route=route,
                salience_features=features,
            )

        # ── Deep reasoning (non-data query: "why do we use X?", etc.) ──
        if any(p in msg_lower for p in _DEEP_PATTERNS):
            return SalienceResult(
                weight=0.8,
                domain="general",
                route="deep",
                salience_features={"matched": "deep_patterns"},
            )

        # ── Fallback ──
        weight = 0.5
        if any(kw in msg_lower for kw in _URGENCY_KEYWORDS):
            weight = min(1.0, weight + 0.3)
        return SalienceResult(
            weight=weight,
            domain="general",
            route="full",
            salience_features={"matched": "fallback"},
        )
