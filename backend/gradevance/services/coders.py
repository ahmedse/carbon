"""Coder strategy registry — heuristic default; LLM can register later.

Packs select stages; runtime selects coder by name from pipeline snapshot.
Never hardcode a single LLM call as the grade (anti-pattern #1).
"""
from __future__ import annotations

from typing import Callable, Protocol

from gradevance.services.pipeline import _SegDraft, code_segment


class CoderStrategy(Protocol):
    def __call__(
        self, seg: _SegDraft, anchors: list[dict], lct_enabled: bool
    ) -> list[dict]:
        ...


_REGISTRY: dict[str, CoderStrategy] = {}


def register_coder(name: str, fn: CoderStrategy) -> None:
    _REGISTRY[name] = fn


def get_coder(name: str | None = None) -> CoderStrategy:
    key = name or "heuristic_anchor"
    if key not in _REGISTRY:
        raise KeyError(f"Unknown coder strategy: {key}")
    return _REGISTRY[key]


def list_coders() -> list[str]:
    return sorted(_REGISTRY)


# Default registration
register_coder("heuristic_anchor", code_segment)

# Side-effect imports register optional strategies.
try:
    from gradevance.services import gold_oracle as _gold_oracle  # noqa: F401
except Exception:  # pragma: no cover
    pass
try:
    from gradevance.services import llm_coder as _llm_coder  # noqa: F401
except Exception:  # pragma: no cover
    pass
