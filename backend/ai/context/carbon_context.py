"""Assembles Carbon-specific business context for injection into the system prompt.

Phase 6 of the Pulse v2 plan. This service fetches live data from the Carbon
platform models (reporting period, emission factors, DQ rules) and formats it
as a compact context block so the LLM answers with the platform's *actual*
values instead of generic world knowledge.

Called once per turn and injected into the system prompt before S3 (draft).
The context must never fail the turn — any error yields an empty string.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("carbon.ai.carbon_context")


class CarbonContextAssembler:
    """Fetches and formats Carbon domain context for prompt injection.

    All Django ORM access goes through ``sync_to_async`` (the repo convention —
    the vendored engine never uses async ORM). Each helper is independently
    guarded so a single broken query can't take down the whole block.
    """

    async def assemble(
        self,
        *,
        user=None,
        app_identifier: str | None = None,
        module_id: int | None = None,
    ) -> str:
        """Return a compact Carbon context block, or "" on any failure.

        ``user``/``module_id`` are accepted for forward-compatibility with the
        plan signature but are currently unused (the queried models are global
        platform configuration, not per-user/per-module).
        """
        try:
            parts: list[str] = []

            period = await self._get_active_period()
            if period:
                parts.append(f"**Active reporting period:** {period}")

            if app_identifier == "emissions":
                factors = await self._get_active_factors()
                if factors:
                    parts.append("**Configured emission factors:**")
                    for f in factors[:5]:
                        parts.append(f"  - {f['name']}: {f['factor']} {f['unit']}")

            dq_count = await self._get_active_dq_rules_count()
            if dq_count is not None:
                parts.append(f"**Active DQ rules:** {dq_count}")

            if not parts:
                return ""

            return (
                "\n\n## Your Carbon Platform Context\n"
                + "\n".join(parts)
                + "\n\nAlways refer to these actual values instead of general knowledge."
            )
        except Exception:
            logger.warning("CarbonContextAssembler.assemble failed", exc_info=True)
            return ""

    async def _get_active_period(self) -> str | None:
        """Return the reporting period whose date range contains today."""
        try:
            from asgiref.sync import sync_to_async
            from django.utils import timezone

            from emissions.models import ReportingPeriod

            def _q():
                today = timezone.now().date()
                period = (
                    ReportingPeriod.objects.filter(
                        start_date__lte=today,
                        end_date__gte=today,
                    )
                    .order_by("-start_date")
                    .first()
                )
                if period:
                    return f"{period.name} ({period.start_date} to {period.end_date})"
                return None

            return await sync_to_async(_q, thread_sensitive=True)()
        except Exception:
            return None

    async def _get_active_factors(self) -> list[dict]:
        """Return up to 5 active emission factors, formatted for the prompt."""
        try:
            from asgiref.sync import sync_to_async

            from emissions.models import EmissionFactor

            def _q():
                qs = EmissionFactor.objects.filter(is_active=True).order_by(
                    "category", "name"
                )[:5]
                out = []
                for ef in qs:
                    unit = f"{ef.factor_unit}/{ef.activity_unit}"
                    out.append(
                        {
                            "name": ef.name,
                            "factor": str(ef.factor_value),
                            "unit": unit,
                        }
                    )
                return out

            return await sync_to_async(_q, thread_sensitive=True)()
        except Exception:
            return []

    async def _get_active_dq_rules_count(self) -> int | None:
        """Return the count of active (non-archived) DQ rules."""
        try:
            from asgiref.sync import sync_to_async

            from dq.models import DQRule

            return await sync_to_async(
                DQRule.objects.filter(is_active=True, archived=False).count,
                thread_sensitive=True,
            )()
        except Exception:
            return None
