"""Segmentation fidelity metrics — expert vs engine span overlap."""
from __future__ import annotations

from typing import Any


def align_segment_f1(expert_segs: list[dict], engine_segs: list) -> dict[str, Any]:
    """Greedy span-overlap alignment F1 (word ranges)."""
    if not expert_segs or not engine_segs:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0, "matched": 0}

    def span(s):
        if isinstance(s, dict):
            return int(s.get("word_start") or s.get("start_word") or 0), int(
                s.get("word_end") or s.get("end_word") or 0
            )
        return int(getattr(s, "start_word", 0) or 0), int(getattr(s, "end_word", 0) or 0)

    matched = 0
    used: set[int] = set()
    for ex in expert_segs:
        a0, a1 = span(ex)
        best_j, best_ov = None, 0
        for j, eng in enumerate(engine_segs):
            if j in used:
                continue
            b0, b1 = span(eng)
            ov = max(0, min(a1, b1) - max(a0, b0))
            if ov > best_ov:
                best_ov, best_j = ov, j
        if best_j is not None and best_ov > 0:
            used.add(best_j)
            matched += 1
    prec = matched / len(engine_segs) if engine_segs else 0.0
    rec = matched / len(expert_segs) if expert_segs else 0.0
    f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0
    return {
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(f1, 4),
        "matched": matched,
    }
