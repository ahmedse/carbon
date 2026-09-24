"""The Excellence standard: 9 dimensions × levels 1–6.

Git is the source (assurance/standard/standard.yaml). A cell with no bound
check is open. N/A is declared per subject kind, never inferred.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import yaml

from .catalogue import ASSURANCE_ROOT, DIMENSIONS, MAX_LEVEL

STANDARD_PATH = ASSURANCE_ROOT / "standard" / "standard.yaml"


@dataclass(frozen=True)
class Rung:
    dimension: str
    level: int
    title: str
    evidence_floor: str


@dataclass(frozen=True)
class Standard:
    version: int
    rungs: tuple[Rung, ...]
    na: dict[str, frozenset[str]]

    def rung(self, dimension: str, level: int) -> Rung | None:
        for rung in self.rungs:
            if rung.dimension == dimension and rung.level == level:
                return rung
        return None

    def applies(self, kind: str, dimension: str) -> bool:
        return dimension not in self.na.get(kind, frozenset())


def _load(path=STANDARD_PATH) -> Standard:
    raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    floors = {int(k): str(v) for k, v in (raw.get("evidence_floor") or {}).items()}
    rungs: list[Rung] = []
    declared = raw.get("rungs") or {}
    for dimension in DIMENSIONS:
        rows = declared.get(dimension) or {}
        for level in range(1, MAX_LEVEL + 1):
            title = rows.get(level) or rows.get(str(level)) or ""
            rungs.append(Rung(dimension, level, str(title), floors.get(level, "configured")))
    na = {
        str(kind): frozenset(str(d) for d in dims)
        for kind, dims in (raw.get("na") or {}).items()
    }
    return Standard(version=int(raw.get("version") or 1), rungs=tuple(rungs), na=na)


@lru_cache(maxsize=1)
def load_standard() -> Standard:
    return _load()
