"""Cell map: one 9×6 grid for an app (ADR-0051 + the standard).

A cell's state is the worst check bound to that dimension and level.
No bound check → ``open``, and an open cell stops that dimension.
N/A (declared in the standard for the subject's kind) does not stop it.
The app level is the minimum across applicable dimensions. Never a mean.

Pulse is one app: pass every Pulse subject. A track filter narrows them.
"""
from __future__ import annotations

from collections import Counter
from typing import Iterable

from .catalogue import DIMENSIONS, LEVEL_NAMES, Catalogue, Subject
from .evaluator import SATISFIED, SubjectReport
from .standard import Standard, load_standard

_WORST = ("failed", "conflict", "stale", "unknown", "unmeasured", "exempt", "passed")
PULSE_APP = "pulse"


def apps_in(cat: Catalogue, tier: str) -> list[dict]:
    """Pulse is one app. Every other subject is its own app."""
    if tier == PULSE_APP:
        return [{"id": PULSE_APP, "title": "Pulse", "tier": PULSE_APP, "kind": "app"}]
    return [
        {"id": s.id, "title": s.title, "tier": s.tier, "track": s.track, "kind": s.kind}
        for s in cat.subjects_in(tier)
    ]


def subjects_for_app(cat: Catalogue, app_id: str, track: str | None = None) -> list[Subject]:
    if app_id == PULSE_APP:
        rows = cat.subjects_in(PULSE_APP, track or None)
        return rows
    subject = cat.subjects.get(app_id)
    return [subject] if subject else []


def _cell_state(states: list[str]) -> str:
    if not states:
        return "open"
    for worst in _WORST:
        if worst in states:
            return worst
    return "open"


def _dimension_level(states_by_level: dict[int, str]) -> int:
    level = 0
    for rank in range(1, len(LEVEL_NAMES)):
        state = states_by_level.get(rank, "open")
        if state in SATISFIED or state == "n/a":
            level = rank
            continue
        break
    return level


def build_grid(
    subjects: Iterable[Subject],
    reports: dict[str, SubjectReport],
    standard: Standard | None = None,
) -> dict:
    standard = standard or load_standard()
    subjects = list(subjects)
    kinds = {s.kind for s in subjects}
    cells = []
    by_dim: dict[str, dict[int, str]] = {d: {} for d in DIMENSIONS}
    for rung in standard.rungs:
        applicable = [s for s in subjects if standard.applies(s.kind, rung.dimension)]
        if subjects and not applicable:
            state = "n/a"
            bound: list[dict] = []
        else:
            bound = []
            for subject in applicable:
                report = reports.get(subject.id)
                if report is None:
                    continue
                for check in report.checks:
                    if check.check.dimension == rung.dimension and check.check.rank == rung.level:
                        bound.append({
                            "check_id": check.check.id,
                            "title": check.check.title,
                            "state": check.state,
                            "subject_id": subject.id,
                            "solution": check.check.solution,
                            "evidence_class": check.evidence_class,
                        })
            state = _cell_state([b["state"] for b in bound])
        by_dim[rung.dimension][rung.level] = state
        cells.append({
            "dimension": rung.dimension,
            "level": rung.level,
            "state": state,
            "rung": rung.title,
            "evidence_floor": rung.evidence_floor,
            "checks": bound,
        })
    dimensions = {dim: _dimension_level(ranks) for dim, ranks in by_dim.items()}
    applicable_dims = [
        dim for dim in DIMENSIONS
        if any(standard.applies(kind, dim) for kind in kinds) or not kinds
    ]
    level = min((dimensions[d] for d in applicable_dims), default=0)
    target = level + 1
    nxt = [
        c for c in cells
        if c["level"] == target and c["state"] not in ("passed", "exempt", "n/a") and target <= 6
    ]
    counted = [c for c in cells if c["state"] not in ("open", "n/a")]
    applicable = [c for c in cells if c["state"] != "n/a"]
    fresh = [c for c in counted if c["state"] == "passed"]
    return {
        "level": level,
        "level_name": LEVEL_NAMES[level],
        "dimensions": dimensions,
        "weakest": next((d for d in applicable_dims if dimensions[d] == level), "") if applicable_dims else "",
        "distance": len(nxt),
        "next": nxt,
        "freshness": (len(fresh) / len(counted)) if counted else 0,
        "coverage": (len(counted) / len(applicable)) if applicable else 0,
        "coverage_declared": len(counted),
        "coverage_applicable": len(applicable),
        "cells": cells,
        "kinds": sorted(kinds),
    }


def histogram(levels: list[int]) -> dict[str, int]:
    counts = Counter(levels)
    return {str(i): counts.get(i, 0) for i in range(len(LEVEL_NAMES))}


def median(levels: list[int]) -> int:
    if not levels:
        return 0
    ordered = sorted(levels)
    return ordered[(len(ordered) - 1) // 2]
