"""Two leave remainings.

``signed`` is the accounting identity. It can go negative. That is the
overdraw. ``display`` is max(0, signed) — what a floored API returns.

A check that only looks at display cannot see an already-overdrawn book.
"""

from __future__ import annotations

from decimal import Decimal


def signed_remaining(entitled, carried, used, pending) -> Decimal:
    return (
        Decimal(str(entitled))
        + Decimal(str(carried))
        - Decimal(str(used))
        - Decimal(str(pending))
    )


def display_remaining(entitled, carried, used, pending) -> Decimal:
    value = signed_remaining(entitled, carried, used, pending)
    return value if value > 0 else Decimal("0")
