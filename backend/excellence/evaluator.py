"""Derive levels from events (ADR-0051 §4–§6). Pure; no database access.

Row state per (subject, check), the only state a UI may show:

* no event on HEAD                → ``unmeasured`` (catalogue class, never green)
* latest event commit ≠ HEAD      → ``stale``
* result unknown                  → ``unknown``
* evidence_class conflict         → ``conflict`` (not passable)
* active exemption                → ``exempt`` (satisfies rank; counted apart)
* otherwise                       → ``passed`` | ``failed``
* passed, but evidence below the rung floor → ``unknown``

A rank with no check in that dimension is open and stops the climb. An empty
dimension is level 0. Overall level is the minimum across applicable
dimensions. Never the mean. Rank 5 counts only with enforcement-verified
evidence or better. Rank 6 counts only when a fault was demonstrated.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable, Mapping

from .catalogue import DIMENSIONS, Catalogue, Check, MAX_LEVEL, Subject
from .standard import Standard, load_standard

SATISFIED = frozenset({"passed", "exempt"})
_EVIDENCE_RANK = {
    "configured": 1,
    "executed": 2,
    "enforcement-verified": 3,
    "fault-demonstrated": 4,
}


def meets_floor(evidence_class: str, floor: str) -> bool:
    """True when the event's evidence is at least the rung's floor."""
    return _EVIDENCE_RANK.get(evidence_class, 0) >= _EVIDENCE_RANK.get(floor, 1)


@dataclass(frozen=True)
class EventView:
    """The subset of an Event row the evaluator needs (ORM or dict agnostic)."""

    check_id: str
    subject_id: str
    commit: str
    result: str
    evidence_class: str
    at: Any = None
    source: str = ""

    @classmethod
    def from_obj(cls, obj: Any) -> "EventView":
        get = obj.get if isinstance(obj, Mapping) else lambda k, d=None: getattr(obj, k, d)
        return cls(
            check_id=str(get("check_id") or ""),
            subject_id=str(get("subject_id") or ""),
            commit=str(get("commit") or ""),
            result=str(get("result") or "unknown"),
            evidence_class=str(get("evidence_class") or "unknown"),
            at=get("at"),
            source=str(get("source") or ""),
        )


@dataclass(frozen=True)
class ExemptionView:
    check_id: str
    subject_id: str
    until: date

    @classmethod
    def from_obj(cls, obj: Any) -> "ExemptionView":
        get = obj.get if isinstance(obj, Mapping) else lambda k, d=None: getattr(obj, k, d)
        return cls(str(get("check_id")), str(get("subject_id")), get("until"))


@dataclass
class CheckState:
    check: Check
    state: str
    evidence_class: str = "configured"
    commit: str = ""
    source: str = ""


@dataclass
class SubjectReport:
    subject: Subject
    level: int
    dimensions: dict[str, int] = field(default_factory=dict)
    checks: list[CheckState] = field(default_factory=list)

    @property
    def next_steps(self) -> list[CheckState]:
        """Failing / unmeasured checks at the next level, lowest rank first."""
        target = self.level + 1
        return [c for c in self.checks if c.check.rank == target and c.state not in SATISFIED]

    @property
    def open_cells(self) -> list[str]:
        """Applicable cells at the next rank that have no check. Silence is not a pass."""
        target = self.level + 1
        if target > MAX_LEVEL:
            return []
        out = []
        for dim, dim_level in self.dimensions.items():
            if dim_level != self.level:
                continue
            if any(c.check.dimension == dim and c.check.rank == target for c in self.checks):
                continue
            out.append(f"{dim}:{target}")
        return out

    def as_dict(self) -> dict[str, Any]:
        return {
            "subject_id": self.subject.id,
            "tier": self.subject.tier,
            "track": self.subject.track,
            "kind": self.subject.kind,
            "level": self.level,
            "dimensions": dict(self.dimensions),
            "checks": [
                {
                    "check_id": c.check.id,
                    "title": c.check.title,
                    "rank": c.check.rank,
                    "dimension": c.check.dimension,
                    "state": c.state,
                    "evidence_class": c.evidence_class,
                    "commit": c.commit,
                    "source": c.source,
                    "solution": c.check.solution,
                }
                for c in self.checks
            ],
            "next": [c.check.id for c in self.next_steps],
            "open": self.open_cells,
        }


def _latest_by_pair(events: Iterable[EventView]) -> dict[tuple[str, str], EventView]:
    latest: dict[tuple[str, str], EventView] = {}
    for ev in events:
        key = (ev.subject_id, ev.check_id)
        cur = latest.get(key)
        if cur is None or _sort_key(ev) >= _sort_key(cur):
            latest[key] = ev
    return latest


def _sort_key(ev: EventView) -> tuple:
    return (ev.at is not None, ev.at or 0)


def evaluate_subject(
    subject: Subject,
    checks: list[Check],
    latest: Mapping[tuple[str, str], EventView],
    exemptions: set[tuple[str, str]],
    head: str,
    standard: Standard | None = None,
) -> SubjectReport:
    standard = standard or load_standard()
    states: list[CheckState] = []
    for check in checks:
        ev = latest.get((subject.id, check.id))
        if (subject.id, check.id) in exemptions:
            states.append(CheckState(check, "exempt", "configured", ev.commit if ev else "", ev.source if ev else ""))
            continue
        if ev is None:
            states.append(CheckState(check, "unmeasured", "configured"))
            continue
        if ev.evidence_class == "conflict":
            states.append(CheckState(check, "conflict", ev.evidence_class, ev.commit, ev.source))
            continue
        if head and ev.commit and ev.commit != head:
            states.append(CheckState(check, "stale", ev.evidence_class, ev.commit, ev.source))
            continue
        if ev.result not in ("passed", "failed"):
            states.append(CheckState(check, "unknown", ev.evidence_class, ev.commit, ev.source))
            continue
        rung = standard.rung(check.dimension, check.rank)
        floor = rung.evidence_floor if rung else "configured"
        if ev.result == "passed" and not meets_floor(ev.evidence_class, floor):
            states.append(CheckState(check, "unknown", ev.evidence_class, ev.commit, ev.source))
            continue
        states.append(CheckState(check, ev.result, ev.evidence_class, ev.commit, ev.source))

    dims: dict[str, int] = {}
    for dim in DIMENSIONS:
        if not standard.applies(subject.kind, dim):
            continue
        dims[dim] = _dimension_level([c for c in states if c.check.dimension == dim])
    level = min(dims.values()) if dims else 0
    return SubjectReport(subject=subject, level=level, dimensions=dims, checks=states)


def _dimension_level(states: list[CheckState]) -> int:
    """Level N needs every check of this dimension at ranks 1..N satisfied.
    A rank with no check is an open cell and stops the dimension. An empty
    dimension is level 0. Other dimensions do not carry the rank."""
    by_rank: dict[int, list[CheckState]] = {}
    for state in states:
        by_rank.setdefault(state.check.rank, []).append(state)
    level = 0
    for rank in range(1, MAX_LEVEL + 1):
        rows = by_rank.get(rank)
        if not rows or not all(s.state in SATISFIED for s in rows):
            break
        level = rank
    return level


def evaluate(
    cat: Catalogue,
    events: Iterable[Any],
    exemptions: Iterable[Any] = (),
    *,
    head: str,
    today: date | None = None,
    tier: str | None = None,
    track: str | None = None,
) -> dict[str, SubjectReport]:
    today = today or date.today()
    latest = _latest_by_pair(EventView.from_obj(e) for e in events)
    active = {
        (x.subject_id, x.check_id)
        for x in (ExemptionView.from_obj(e) for e in exemptions)
        if x.until is not None and x.until >= today
    }
    out: dict[str, SubjectReport] = {}
    for subject in cat.subjects_in(tier, track):
        out[subject.id] = evaluate_subject(subject, cat.checks_for(subject), latest, active, head)
    return out


def regressions(current: Mapping[str, SubjectReport], previous: Mapping[str, int]) -> list[str]:
    """Subjects whose level fell below the previous snapshot (the ratchet)."""
    out = []
    for sid, rep in current.items():
        prev = previous.get(sid)
        if prev is not None and rep.level < prev:
            out.append(f"{sid}: L{prev} → L{rep.level}")
    return sorted(out)
