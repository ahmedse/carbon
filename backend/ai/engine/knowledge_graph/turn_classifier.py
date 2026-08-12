"""
Turn classifier — Stage 7.

Classifies each user utterance into a TurnType using a two-pass approach:

  Pass 1 (heuristics) — cheap regex/keyword patterns.  Returns early when
  confidence is high (> 0.8).  Empty active_context always yields NEW_TOPIC.

  Pass 2 (LLM) — called when heuristic confidence is 0.4 – 0.8 or when the
  patterns disagree.  A structured prompt asks the model for a JSON answer.

Callers should treat confidence < 0.7 as "ambiguous" and optionally surface
a clarification prompt to the user.
"""
import json
import logging
import re
from typing import Optional

from ai.engine.knowledge_graph.conversation_context import (
    ConversationSession,
    TurnClassification,
    TurnType,
)

logger = logging.getLogger("pulse.knowledge_graph.turn_classifier")

# ── Heuristic pattern tables ───────────────────────────────────────────────────

_CONTINUATION_PATTERNS = [
    r"\bbreak\s+(that|this|it)\s+down\b",
    r"\bgroup\s+by\b",
    r"\bsort\s+by\b",
    r"\border\s+by\b",
    r"\bshow\s+(top|bottom)\s+\d+\b",
    r"\bshow\s+only\s+top\b",
    r"\blimit\s+to\s+\d+\b",
    r"\btop\s+\d+\b",
    r"\bbottom\s+\d+\b",
    r"\bas\s+a\s+(bar|line|pie|table|chart|graph|stat)\b",
    r"\b(bar|line|pie|scatter)\s+chart\b",
    r"\bvisualize\b",
    r"\bchart\s+it\b",
    r"\bplot\s+(that|this|it)\b",
    r"\bshow\s+(that|this|it)\s+as\b",
    r"\bbreak\s+it\s+down\b",
    r"\bby\s+(month|week|day|year|quarter|region|country|category|product|type)\b",
    r"\bper\s+(month|week|day|year|quarter|region|country|category|product|type)\b",
    r"\badd\s+(a\s+)?(column|dimension|breakdown)\b",
]

_REFINEMENT_PATTERNS = [
    r"\bonly\s+for\b",
    r"\bonly\s+(active|inactive|enabled|disabled)\b",
    r"\bexclude\b",
    r"\bexcept\b",
    r"\bfilter\s+by\b",
    r"\bwhere\b",
    r"\binstead\b",
    r"\bchange\s+(the\s+)?(filter|date|time|period)\b",
    r"\bswitch\s+(to|the)\s+(date|time|period|filter)\b",
    r"\bfor\s+(last|this|next)\s+(week|month|quarter|year)\b",
    r"\bsince\s+\d{4}\b",
    r"\b(in|from|during)\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|january|february|march|april|june|july|august|september|october|november|december)\b",
    r"\b(in|from|during)\s+q[1-4]\b",
    r"\bbut\s+only\b",
    r"\bwith\s+status\b",
    r"\bwith\s+type\b",
    r"\bnarrow\s+(that|it|this)\s+to\b",
    r"\brestrict\s+to\b",
]

_DRILL_DOWN_PATTERNS = [
    r"\bwhy\s+(did|is|are|was|were)\b",
    r"\bwhat\s+caused\b",
    r"\bwhat\s+drove\b",
    r"\bwhat\s+(is|are)\s+driving\b",
    r"\bzoom\s+in\b",
    r"\bdig\s+into\b",
    r"\bfocus\s+on\b",
    r"\bbreak\s+down\s+(specifically|just)\b",
    r"\btell\s+me\s+more\s+about\b",
    r"\bshow\s+me\s+(just|only)\s+the\s+\w+\s+ones\b",
    r"\bdetail(s)?\s+for\b",
    r"\bwhat\s+about\s+(just|only)\b",
]

# Signals that strongly suggest a genuinely new topic
_NEW_TOPIC_SIGNALS = [
    r"\bswitch\s+to\b",
    r"\bnew\s+question\b",
    r"\bdifferent\s+(question|topic|table|dataset)\b",
    r"\binstead\s+tell\s+me\b",
    r"\bnow\s+show\s+me\b",
    r"\bforget\s+(that|the|about)\b",
    r"\bstart\s+(over|fresh|again)\b",
]


def _score_patterns(text: str, patterns: list[str]) -> int:
    count = 0
    for p in patterns:
        if re.search(p, text, re.IGNORECASE):
            count += 1
    return count


# ── Main classifier class ──────────────────────────────────────────────────────

class TurnClassifier:
    """
    Classifies an utterance relative to the current ConversationSession.
    """

    def __init__(self, llm_client, model: str):
        self._llm = llm_client
        self._model = model

    # ── public API ────────────────────────────────────────────────────────────

    async def classify(
        self, utterance: str, session: ConversationSession
    ) -> TurnClassification:
        """Return a TurnClassification for *utterance* given *session* state."""

        # First turn (or expired session with no context) → always NEW_TOPIC.
        if session.active_context.is_empty() or not session.turns:
            return TurnClassification(
                turn_type=TurnType.NEW_TOPIC, confidence=1.0,
                reasoning="no prior context — first turn"
            )

        # Heuristic pass
        classification = self._heuristic(utterance)

        if classification.confidence >= 0.8:
            logger.debug(
                "turn_classifier heuristic winner=%s conf=%.2f",
                classification.turn_type.value,
                classification.confidence,
            )
            return classification

        # LLM pass for ambiguous or low-confidence cases
        try:
            return await self._llm_classify(utterance, session, classification)
        except Exception as exc:
            logger.warning("turn_classifier LLM fallback failed: %s — using heuristic", exc)
            return classification

    # ── heuristic pass ────────────────────────────────────────────────────────

    def _heuristic(self, utterance: str) -> TurnClassification:
        cont_score = _score_patterns(utterance, _CONTINUATION_PATTERNS)
        refi_score = _score_patterns(utterance, _REFINEMENT_PATTERNS)
        drill_score = _score_patterns(utterance, _DRILL_DOWN_PATTERNS)
        new_score = _score_patterns(utterance, _NEW_TOPIC_SIGNALS)

        scores = {
            TurnType.CONTINUATION: cont_score,
            TurnType.REFINEMENT: refi_score,
            TurnType.DRILL_DOWN: drill_score,
            TurnType.NEW_TOPIC: new_score,
        }

        best_type = max(scores, key=lambda t: scores[t])
        best_score = scores[best_type]

        if best_score == 0:
            # No heuristic signals — very likely NEW_TOPIC but with low confidence
            return TurnClassification(
                turn_type=TurnType.NEW_TOPIC, confidence=0.45,
                reasoning="no heuristic patterns matched"
            )

        total_signals = sum(scores.values()) or 1
        confidence = min(0.9, best_score / total_signals + 0.4)

        return TurnClassification(
            turn_type=best_type,
            confidence=round(confidence, 2),
            reasoning=f"heuristic: signals={scores}",
        )

    # ── LLM pass ──────────────────────────────────────────────────────────────

    async def _llm_classify(
        self,
        utterance: str,
        session: ConversationSession,
        initial: TurnClassification,
    ) -> TurnClassification:
        context_summary = session.active_context.to_summary_text()
        recent = session.recent_turns(3)
        turn_history = "\n".join(
            f"  [{i+1}] User: {t.user_utterance}\n       Result: {t.result_summary or '(no summary)'}"
            for i, t in enumerate(recent)
        )

        system = (
            "You are a conversation classifier. Classify the user's NEW message relative to "
            "their conversation history. Return ONLY a JSON object with these fields:\n"
            '  {"turn_type": "continuation"|"refinement"|"drill_down"|"new_topic", '
            '"confidence": 0.0-1.0, "reasoning": "one sentence"}\n\n'
            "Definitions:\n"
            "  continuation — adds a dimension, sort order, limit, or viz to the same question\n"
            "  refinement   — changes a filter, time range, or value for the same question\n"
            "  drill_down   — asks why/what caused, or focuses on a specific value from last result\n"
            "  new_topic    — a genuinely new question unrelated to prior turns\n"
        )

        user_msg = (
            f"Active context:\n{context_summary}\n\n"
            f"Recent turns:\n{turn_history}\n\n"
            f"NEW MESSAGE: \"{utterance}\"\n\n"
            f"Initial heuristic guess: {initial.turn_type.value} (confidence {initial.confidence})\n\n"
            "Classify the new message."
        )

        response = await self._llm.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.1,
            max_tokens=150,
        )

        raw = response.choices[0].message.content.strip()
        return self._parse_llm_response(raw, initial)

    def _parse_llm_response(
        self, raw: str, fallback: TurnClassification
    ) -> TurnClassification:
        try:
            # Strip markdown fences if present
            clean = re.sub(r"```[a-zA-Z]*\n?", "", raw).strip().rstrip("`")
            # Use raw_decode so extra trailing text (multiple JSON objects,
            # commentary, etc.) doesn't cause "Extra data" errors.
            decoder = json.JSONDecoder()
            data, _ = decoder.raw_decode(clean)
            turn_type = TurnType(data["turn_type"])
            confidence = float(data.get("confidence", 0.7))
            reasoning = data.get("reasoning", "")
            return TurnClassification(
                turn_type=turn_type, confidence=confidence, reasoning=f"llm: {reasoning}"
            )
        except Exception as exc:
            logger.debug("turn_classifier LLM parse error: %s — using heuristic", exc)
            return fallback
