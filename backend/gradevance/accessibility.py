"""WCAG 2.2 AA checklist scaffold for GradeVance VPAT evidence.

Not a substitute for a formal VPAT — tracks studio surfaces + criteria status.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

# status: pass | partial | fail | n/a | pending
ACCESSIBILITY_CHECKLIST: list[dict[str, Any]] = [
    {
        "criterion": "2.4.1 Bypass Blocks",
        "surface": "SkipToMain on all GradeVance studios",
        "status": "pass",
    },
    {
        "criterion": "1.3.1 Info and Relationships",
        "surface": "main landmarks, table captions, labelled forms",
        "status": "pass",
    },
    {
        "criterion": "2.4.6 Headings and Labels",
        "surface": "PageHeader + section h2 on Home/Marking/Authoring/Library/Proposals",
        "status": "pass",
    },
    {
        "criterion": "4.1.2 Name, Role, Value",
        "surface": "MUI controls; aria-labels on queue actions",
        "status": "partial",
    },
    {
        "criterion": "1.4.3 Contrast (Minimum)",
        "surface": "Theme-dependent — needs brand contrast audit",
        "status": "pending",
    },
    {
        "criterion": "2.1.1 Keyboard",
        "surface": "Skip link + native focus; WaveChart has text alternative (desc + sr-only list)",
        "status": "pass",
    },
    {
        "criterion": "3.3.1 / 3.3.3 Error Identification / Suggestion",
        "surface": "ErrorAlert + form validation messages",
        "status": "partial",
    },
]

EVIDENCE_ARTIFACTS = [
    {
        "kind": "checklist_json",
        "path": "docs/eduos/vpat-evidence/checklist.json",
    },
    {
        "kind": "playwright_smoke",
        "path": "carbon-frontend/e2e/journeys/journey-gradevance-a11y.spec.ts",
    },
]


def accessibility_summary() -> dict[str, Any]:
    counts: dict[str, int] = {}
    for row in ACCESSIBILITY_CHECKLIST:
        counts[row["status"]] = counts.get(row["status"], 0) + 1

    repo_root = Path(__file__).resolve().parents[2]
    artifacts = []
    for art in EVIDENCE_ARTIFACTS:
        p = repo_root / art["path"]
        artifacts.append({**art, "present": p.is_file()})

    return {
        "standard": "WCAG 2.2 AA (toward VPAT 2.5)",
        "items": ACCESSIBILITY_CHECKLIST,
        "counts": counts,
        "evidence_artifacts": artifacts,
        "note": "Manual + axe evidence still required before claiming conformance.",
    }
