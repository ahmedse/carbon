"""Derive row state from a rule and an evidence ledger.

A row is passed only when the latest event for that rule is `passed`
on the requested commit. Conflict rules cannot pass. A different commit
is stale. No event leaves the catalogue label.
"""

from __future__ import annotations

import json
from pathlib import Path

from assurance.model import RESULTS, EvidenceEvent, Pack, RowState, Rule


def load_events(path: Path | None) -> list[EvidenceEvent]:
    if path is None or not path.is_file():
        return []
    events: list[EvidenceEvent] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        raw = json.loads(text)
        result = str(raw.get("result") or "")
        if result not in RESULTS:
            raise ValueError(f"{path}:{line_no} result {result!r} is not allowed")
        events.append(
            EvidenceEvent(
                rule_id=str(raw["rule_id"]),
                pack_id=str(raw["pack_id"]),
                commit=str(raw["commit"]),
                result=result,
                source=str(raw.get("source") or ""),
                evidence_class=str(raw.get("evidence_class") or "executed"),
            )
        )
    return events


def evaluate_rule(rule: Rule, events: list[EvidenceEvent], commit: str) -> RowState:
    if rule.catalogue == "conflict" or rule.confidence == "conflict":
        return RowState(rule.id, rule.pack, "conflict", "sources disagree; a pass event is ignored", rule.blocks_release)

    matched = [event for event in events if event.rule_id == rule.id and event.pack_id == rule.pack]
    if not matched:
        return RowState(
            rule.id,
            rule.pack,
            rule.catalogue,
            "no evidence event for this rule",
            rule.blocks_release,
        )
    latest = matched[-1]
    if latest.commit != commit:
        return RowState(
            rule.id,
            rule.pack,
            "stale",
            f"latest event is on {latest.commit}, board commit is {commit}",
            rule.blocks_release,
        )
    if latest.result == "conflict":
        return RowState(rule.id, rule.pack, "conflict", latest.source or latest.evidence_class, rule.blocks_release)
    if latest.result == "passed":
        return RowState(rule.id, rule.pack, "passed", latest.source or "event passed on this commit", rule.blocks_release)
    if latest.result == "failed":
        return RowState(rule.id, rule.pack, "failed", latest.source or "event failed on this commit", rule.blocks_release)
    return RowState(rule.id, rule.pack, "unknown", latest.source or "event could not run", rule.blocks_release)


def evaluate_packs(packs: list[Pack], events: list[EvidenceEvent], commit: str) -> list[RowState]:
    rows: list[RowState] = []
    for pack in packs:
        for rule in pack.rules:
            rows.append(evaluate_rule(rule, events, commit))
    return rows
