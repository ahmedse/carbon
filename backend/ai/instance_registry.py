"""Resolve the active Pulse instance + default app from the Django brand.

Single source of truth for "which instance am I?" — replaces the hardcoded
``"carbon"`` scattered across the AI layer. Driven by ``settings.DJANGO_BRAND``
so a Nibras deployment boots as the Nibras instance (People & Payroll), never
Carbon. This is the enforcement point for cross-tenant isolation: every engine
partition, conversation, memory fact, and context injection resolves here so a
brand's data can never mingle with or leak into another brand's partition.
"""
from __future__ import annotations

from django.conf import settings

# brand -> (instance_id, default_app_identifier)
_BRAND_INSTANCE_MAP = {
    "aastmt": ("carbon", "carbon"),
    "nibras": ("nibras", "people"),
    "medos": ("medos", "medos"),
    "eduos": ("eduos", "gradevance"),
    "tectona": ("tectona", "healthy"),
}

_FALLBACK_BRAND = "aastmt"


def active_brand() -> str:
    """Return the active Django brand, normalized to a known value."""
    brand = (getattr(settings, "DJANGO_BRAND", _FALLBACK_BRAND) or _FALLBACK_BRAND).lower()
    return brand if brand in _BRAND_INSTANCE_MAP else _FALLBACK_BRAND


def resolve_instance_id() -> str:
    """Default engine instance id for the active deployment.

    Nibras boots as ``nibras`` so its conversations, KG nodes, memories, and
    context injections live in their own partition — never Carbon's.
    """
    return _BRAND_INSTANCE_MAP[active_brand()][0]


def resolve_default_app_identifier() -> str:
    """Default app identifier for newly-created scoped rows/conversations."""
    return _BRAND_INSTANCE_MAP[active_brand()][1]


def default_app_for_instance(instance_id: str | None) -> str:
    """Default app identifier for a *specific* engine instance.

    Unlike :func:`resolve_default_app_identifier` (which is brand-global), this
    is instance-scoped so a Carbon-instance turn defaults to the ``carbon`` app
    even when the deployment brand is Nibras (and vice-versa).
    """
    for app in _BRAND_INSTANCE_MAP.values():
        if app[0] == instance_id:
            return app[1]
    return "carbon"
