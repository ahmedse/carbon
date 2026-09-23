from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProbeFinding:
    rule_id: str
    pack_id: str
    result: str
    source: str
    detail: str
