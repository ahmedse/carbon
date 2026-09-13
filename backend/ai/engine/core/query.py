"""Pure query helpers shared by the engine (stdlib-only, no Django/host imports)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def first(rows: list[Any]) -> Any:
    """Return the first row of a ``select`` result, or ``None``."""
    return rows[0] if rows else None


@dataclass(frozen=True)
class TenancyScope:
    """Engine-owned tenancy filter (no Django Q). The host store expands it."""
    instance_id: str
    host_user_id: str | None


def scope(instance_id: str, host_user_id: str | None) -> TenancyScope:
    """Build an engine-side tenancy filter (expanded by the host store)."""
    return TenancyScope(instance_id=instance_id, host_user_id=host_user_id)
