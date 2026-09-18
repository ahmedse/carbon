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
) -> dict:
    kappa = cohen_kappa(expert_labels, engine_labels)
    return {
        "metric": "cohen_kappa",
        "value": round(kappa, 4),
        "minimum": minimum,
        "passed": kappa >= minimum,
    }
