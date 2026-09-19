"""Reliability helpers — Cohen's κ gate for summative pack publish (RULE_32)."""
from __future__ import annotations

from collections import Counter
from typing import Sequence


def cohen_kappa(a: Sequence[str | int], b: Sequence[str | int]) -> float:
    """Compute Cohen's κ for two equal-length label sequences."""
    if not a or not b or len(a) != len(b):
        return 0.0
    n = len(a)
    agree = sum(1 for x, y in zip(a, b) if x == y)
    po = agree / n
    labels = set(a) | set(b)
    ca = Counter(a)
    cb = Counter(b)
    pe = sum((ca[l] / n) * (cb[l] / n) for l in labels)
    if pe >= 1.0:
        return 1.0 if po == 1.0 else 0.0
    return (po - pe) / (1.0 - pe)


def passes_reliability_gate(
    expert_labels: Sequence[str | int],
    engine_labels: Sequence[str | int],
    *,
    minimum: float = 0.6,
    dimension: str = "semantic_gravity",
) -> dict:
    kappa = cohen_kappa(expert_labels, engine_labels)
    return {
        "metric": "cohen_kappa",
        "dimension": dimension,
        "value": round(kappa, 4),
        "minimum": minimum,
        "passed": kappa >= minimum,
        "n": len(expert_labels),
    }


def adjacent_band_agreement(
    expert: Sequence[str],
    engine: Sequence[str],
    *,
    band_order: Sequence[str] | None = None,
) -> dict:
    """Exact + adjacent-band match rate for rubric gold (Instrument Trust T4)."""
    if not expert or len(expert) != len(engine):
        return {"exact": 0.0, "adjacent": 0.0, "n": 0, "passed": False}
    order = list(band_order or [])
    idx = {b: i for i, b in enumerate(order)}
    exact = sum(1 for a, b in zip(expert, engine) if a == b)
    adj = 0
    for a, b in zip(expert, engine):
        if a == b:
            adj += 1
        elif order and a in idx and b in idx and abs(idx[a] - idx[b]) <= 1:
            adj += 1
    n = len(expert)
    return {
        "exact": round(exact / n, 4),
        "adjacent": round(adj / n, 4),
        "n": n,
        "passed": (exact / n) >= 0.5 if n else False,
    }
