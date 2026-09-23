"""Rule, event, and derived row state. No domain imports."""

from __future__ import annotations

from dataclasses import dataclass


CATALOGUE = frozenset({"configured", "not-executed", "conflict", "planned", "historical"})
RESULTS = frozenset({"passed", "failed", "unknown", "conflict"})


@dataclass(frozen=True)
class Rule:
    id: str
    pack: str
    journey: str
    meaning: str
    source: str
    owner: str
    failure: str
    validation: str
    implementation: str
    confidence: str
    catalogue: str
    residual: str
    blocks_release: bool


@dataclass(frozen=True)
class Pack:
    id: str
    title: str
    brand: str
    rules: tuple[Rule, ...]


@dataclass(frozen=True)
class EvidenceEvent:
    rule_id: str
    pack_id: str
    commit: str
    result: str
    source: str
    evidence_class: str = "executed"


@dataclass(frozen=True)
class RowState:
    rule_id: str
    pack: str
    label: str
    reason: str
    blocking: bool

    @property
    def passed(self) -> bool:
        return self.label == "passed"
