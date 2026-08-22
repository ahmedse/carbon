"""
Carbon AI Intelligence — Domain Apps

Each domain app gets its own module here.
See ai/domain_protocol.py for the DomainAIOperations ABC.
See .ai-toolkit/shared/ai-contract.md §8 for registration steps.

Current domains:
  - emissions (carbon footprint)
  - water (water management)
  - admin (platform administration — access, lineage, governance, MDM)
  - mdm (master data — reference sets, gold-record confidence, dedup)
  - data_product (governed, versioned data products)
  - finance (non-data operations vertical — advisory/drafting only)
  - hr (non-data operations vertical — advisory/drafting only)
  - customer (non-data operations vertical — advisory/drafting only)
  - (future) waste

``register_builtin_domains()`` is invoked once at app startup
(``ai.apps.AIConfig.ready``). It is guarded by ``has_domain`` so it is safe to
call from ``ready()``, management commands, and the test suite alike — without
it the manifest API (``/ai/pulse/apps/``) and per-domain prompt injection
silently no-op in production because nothing else imports these modules.
"""

from __future__ import annotations


def register_builtin_domains() -> None:
    """Import + register every built-in domain app (idempotent by identifier).

    Registration is first-wins by ``app_identifier``; re-importing an already
    registered domain is a no-op because we guard with ``has_domain`` before
    importing (``register_domain`` itself raises on duplicates).
    """
    from ai.domain_protocol import has_domain

    if not has_domain("emissions"):
        from .emissions import EmissionsDomainAI  # noqa: F401
    if not has_domain("water"):
        from .water import WaterDomainAI  # noqa: F401
    if not has_domain("admin"):
        from .admin import AdminDomainAI  # noqa: F401
    if not has_domain("mdm"):
        from .mdm import MdmDomainAI  # noqa: F401
    if not has_domain("data_product"):
        from .data_product import DataProductDomainAI  # noqa: F401
    # Gap #5 — non-data operations verticals (manifest-only adapters).
    if not has_domain("finance"):
        from .finance import FinanceDomainAI  # noqa: F401
    if not has_domain("hr"):
        from .hr import HRDomainAI  # noqa: F401
    if not has_domain("customer"):
        from .customer import CustomerOpsDomainAI  # noqa: F401
