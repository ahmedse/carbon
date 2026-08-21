"""Phase 24-D — DQ feedback signal taxonomy.

User-origin signals reuse the engine quality-scoring taxonomy from
``ai/engine/knowledge_graph/feedback.py`` (``quality_score_for``) so DQ
signals score identically to KG signals:

    explicit_positive → 1.0      (suggestion accepted)
    explicit_negative → 0.1      (suggestion rejected)
    correction       → 0.0      (rule corrected; the correction itself is 1.0)

Pipeline-heuristic signals (no user judgement) carry their own scores:

    retire_candidate → 0.0      (always-pass / false-positive flag)
    drift            → 0.5      (neutral — observed data change)
"""

from ai.engine.knowledge_graph.feedback import quality_score_for

# event_type → (signal_type, source)
EVENT_SIGNAL_MAP = {
    "suggest_accepted": ("explicit_positive", "suggest"),
    "suggest_rejected": ("explicit_negative", "suggest"),
    "rule_corrected": ("correction", "nl_check"),
    "result_always_pass": ("retire_candidate", "result"),
    "result_false_positive": ("retire_candidate", "result"),
    "drift_detected": ("drift", "drift"),
}

# Heuristic signals not present in the engine taxonomy.
_HEURISTIC_SCORES = {
    "retire_candidate": 0.0,
    "drift": 0.5,
}


def score_for(event_type: str) -> float:
    """Quality score for an event type (user signals via engine taxonomy)."""
    signal_type, _ = EVENT_SIGNAL_MAP[event_type]
    if signal_type in _HEURISTIC_SCORES:
        return _HEURISTIC_SCORES[signal_type]
    return quality_score_for(signal_type)
