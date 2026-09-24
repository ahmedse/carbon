"""Map git diffs to excellence subjects (ADR-0051 P4 — gate only what moved)."""
from __future__ import annotations

import subprocess
from pathlib import Path

from .catalogue import REPO_ROOT, Catalogue, Subject


def changed_paths(base: str = "origin/main") -> set[str]:
    """Paths changed between ``base`` and HEAD (name-only). Empty on git failure."""
    try:
        proc = subprocess.run(
            ["git", "diff", "--name-only", f"{base}...HEAD"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=False,
        )
    except OSError:
        return set()
    if proc.returncode != 0:
        # first commit / no remote — fall back to unstaged+staged vs HEAD
        proc = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=False,
        )
        if proc.returncode != 0:
            return set()
    return {line.strip().replace("\\", "/") for line in proc.stdout.splitlines() if line.strip()}


def _touches(subject: Subject, paths: set[str]) -> bool:
    declared = [
        *subject.paths, *subject.tests, *subject.spec, *subject.adr,
        *subject.runbook, *subject.ci, *((subject.process,) if subject.process else ()),
    ]
    for d in declared:
        d = d.replace("\\", "/").rstrip("/")
        if not d:
            continue
        for p in paths:
            if p == d or p.startswith(d + "/") or d.startswith(p.rstrip("/") + "/"):
                return True
    return False


def subjects_touched(cat: Catalogue, paths: set[str], *, tier: str | None = None, track: str | None = None) -> list[Subject]:
    if not paths:
        return []
    return [s for s in cat.subjects_in(tier, track) if _touches(s, paths)]
