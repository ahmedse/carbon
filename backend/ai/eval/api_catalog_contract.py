"""ESS api_catalog contract (ADR-0049 P2).

Any catalog entry that sets ``kind`` must also set ``domain`` and ``not_for``.
Read kinds (balance, history, detail) must set ``empty_render``.
Write kinds must not.
"""
from __future__ import annotations

from typing import Any

READ_KINDS = frozenset({"balance", "history", "detail", "list", "read"})
WRITE_KINDS = frozenset({"write", "request"})


def catalog_violations(catalog: list[dict] | None) -> list[str]:
    violations: list[str] = []
    for entry in catalog or []:
        if not isinstance(entry, dict):
            continue
        kind = str(entry.get("kind") or "").strip()
        if not kind:
            continue
        name = str(entry.get("name") or "?")
        if kind not in READ_KINDS | WRITE_KINDS:
            violations.append(f"{name}: unknown kind {kind}")
        if not str(entry.get("domain") or "").strip():
            violations.append(f"{name}: kind set but domain empty")
        if not str(entry.get("not_for") or "").strip():
            violations.append(f"{name}: kind set but not_for empty")
        if kind in READ_KINDS and not str(entry.get("empty_render") or "").strip():
            violations.append(f"{name}: read kind without empty_render")
    return violations
