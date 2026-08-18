"""AIUsage — usage aggregation + per-user monthly quota (Phase 21-A).

Aggregates persisted ``AIGeneration`` usage (the completion-time record) into
the shapes served by ``GET /ai/usage/summary`` and
``GET /ai/usage/by-conversation``, and enforces the ``AIUserProfile`` monthly
token budget.

Scoping (CBAC): usage is always scoped to the *requesting* user's own
conversations.  Superusers / global admins may pass ``user_id`` to inspect a
different account (handled at the view layer); the service itself never leaks
cross-tenant data unless an admin explicitly asks.

Cost is read from the Phase 20-A ``ModelCatalog`` rates — never recomputed ad
hoc.  The persisted ``AIGeneration.cost`` already carries the catalog-derived
value, so aggregation simply sums it.
"""

from __future__ import annotations

import re
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.db import models
from django.db.models import Count, Sum
from django.utils import timezone

from ai.models import AIConversation, AIGeneration, AIMessage, AIUserProfile, ModelCatalog

logger = __import__("logging").getLogger("carbon.ai.usage")

_PERIOD_RE = re.compile(r"^(\d+)([dw])?$")

DEFAULT_PERIOD_DAYS = 30
SOFT_WARNING_PCT = int(getattr(settings, "AI_QUOTA_SOFT_WARNING_PCT", 80))


class QuotaExceededError(ValueError):
    """Raised at request time when a user's monthly token quota is exhausted."""

    code = "quota"

    def __init__(self, message: str, quota: dict[str, Any] | None = None):
        super().__init__(message)
        self.quota = quota or {}


def parse_period(value: Any) -> int:
    """Parse a period string like ``"7d"``/``"90d"`` into a day count.

    Accepts plain integers (treated as days) and ``<n>d``/``<n>w`` suffixes.
    Anything unparseable falls back to ``DEFAULT_PERIOD_DAYS``.  Negative or
    zero values are rejected in favour of the default.
    """
    if isinstance(value, int) and not isinstance(value, bool):
        days = value
    else:
        text = str(value or "").strip().lower()
        m = _PERIOD_RE.match(text)
        if not m:
            return DEFAULT_PERIOD_DAYS
        days = int(m.group(1))
        if m.group(2) == "w":
            days *= 7
    return days if days > 0 else DEFAULT_PERIOD_DAYS


class AIUsage:
    """Per-user usage aggregation + quota enforcement."""

    def __init__(self, user):
        self.user = user
        self._profile: AIUserProfile | None = None

    # ── profile ──────────────────────────────────────────────────────────
    @property
    def profile(self) -> AIUserProfile:
        if self._profile is None:
            self._profile, _created = AIUserProfile.objects.get_or_create(
                user=self.user,
            )
        return self._profile

    # ── scoping helpers ──────────────────────────────────────────────────
    def _base_generations(self):
        """Completed generations owned by the requesting user."""
        return AIGeneration.objects.filter(
            conversation__user=self.user,
            status="completed",
        )

    def _since(self, period_days: int):
        return timezone.now() - timedelta(days=period_days)

    # ── aggregation ──────────────────────────────────────────────────────
    def summary(self, period_days: int = DEFAULT_PERIOD_DAYS) -> dict[str, Any]:
        """Aggregate usage over the trailing ``period_days`` for this user."""
        since = self._since(period_days)
        qs = self._base_generations().filter(completed_at__gte=since)
        agg = qs.aggregate(
            total_tokens=Sum("total_tokens"),
            total_prompt=Sum("prompt_tokens"),
            total_completion=Sum("completion_tokens"),
            total_cost=Sum("cost"),
            total_generations=Count("id"),
        )
        total_tokens = int(agg["total_tokens"] or 0)

        tier_rows = qs.values("model_id").annotate(
            tokens=Sum("total_tokens"),
            cost=Sum("cost"),
            n=Count("id"),
        )
        by_tier: dict[str, dict[str, Any]] = {}
        by_model: dict[str, dict[str, Any]] = {}
        for row in tier_rows:
            model_id = row["model_id"] or "unknown"
            tier = ModelCatalog.resolve_tier(model_id)
            tokens = int(row["tokens"] or 0)
            cost = row["cost"] or Decimal("0.0")
            bucket = by_tier.setdefault(
                tier, {"tokens": 0, "cost": Decimal("0.0"), "generations": 0}
            )
            bucket["tokens"] += tokens
            bucket["cost"] += cost
            bucket["generations"] += int(row["n"] or 0)
            by_model[model_id] = {"tokens": tokens, "cost": cost, "generations": int(row["n"] or 0)}

        # Normalize Decimal costs to strings (JSON-safe, fixed precision).
        for bucket in by_tier.values():
            bucket["cost"] = self._money(bucket["cost"])
        for entry in by_model.values():
            entry["cost"] = self._money(entry["cost"])

        return {
            "period_days": period_days,
            "total_tokens": total_tokens,
            "prompt_tokens": int(agg["total_prompt"] or 0),
            "completion_tokens": int(agg["total_completion"] or 0),
            "total_cost": self._money(agg["total_cost"]),
            "total_generations": int(agg["total_generations"] or 0),
            "by_tier": by_tier,
            "by_model": by_model,
            "quota": self.quota_snapshot(),
        }

    def by_conversation(self, period_days: int = DEFAULT_PERIOD_DAYS) -> dict[str, Any]:
        """Per-conversation usage over the trailing ``period_days``."""
        since = self._since(period_days)
        qs = self._base_generations().filter(completed_at__gte=since)
        rows = qs.values("conversation_id").annotate(
            total_tokens=Sum("total_tokens"),
            total_cost=Sum("cost"),
            generation_count=Count("id"),
        )
        conv_ids = [r["conversation_id"] for r in rows]
        conv_titles = dict(
            AIConversation.objects.filter(id__in=conv_ids).values_list("id", "title")
        )
        msg_counts = dict(
            AIMessage.objects.filter(conversation_id__in=conv_ids, is_deleted=False)
            .values("conversation_id")
            .annotate(n=Count("id"))
            .values_list("conversation_id", "n")
        )
        conversations = [
            {
                "conversation_id": str(r["conversation_id"]),
                "title": conv_titles.get(r["conversation_id"], "") or "",
                "total_tokens": int(r["total_tokens"] or 0),
                "total_cost": self._money(r["total_cost"]),
                "generation_count": int(r["generation_count"] or 0),
                "message_count": int(msg_counts.get(r["conversation_id"], 0)),
            }
            for r in rows
        ]
        conversations.sort(key=lambda c: c["total_tokens"], reverse=True)
        return {"period_days": period_days, "conversations": conversations}

    # ── quota ────────────────────────────────────────────────────────────
    def quota_snapshot(self) -> dict[str, Any]:
        """Current quota state for this user (used this window vs limit)."""
        profile = self.profile
        window_start = profile.quota_window_start()
        reset_at = profile.quota_reset_at()
        used = int(
            self._base_generations()
            .filter(completed_at__gte=window_start)
            .aggregate(n=Sum("total_tokens"))["n"]
            or 0
        )
        limit = int(profile.monthly_token_limit or 0)
        remaining = max(0, limit - used)
        pct = round((used / limit) * 100.0, 1) if limit > 0 else 0.0
        hard_exceeded = limit > 0 and used >= limit
        # Phase 22-A — the soft-warning percent is a per-user preference
        # (usage_alert_threshold, default 80); the settings constant is only
        # the fallback for legacy profiles without the field.
        soft_warning_pct = int(profile.usage_alert_threshold or SOFT_WARNING_PCT)
        soft_warning = not hard_exceeded and limit > 0 and pct >= soft_warning_pct
        return {
            "limit": limit,
            "used": used,
            "remaining": remaining,
            "reset_at": reset_at.isoformat(),
            "window_start": window_start.isoformat(),
            "pct": pct,
            "soft_warning": soft_warning,
            "soft_warning_pct": soft_warning_pct,
            "hard_exceeded": hard_exceeded,
        }

    def check_quota(self) -> dict[str, Any]:
        """Request-time gate.  Returns the quota dict; raises on hard exceed."""
        snapshot = self.quota_snapshot()
        if snapshot["hard_exceeded"]:
            raise QuotaExceededError(
                "Monthly token quota exceeded.",
                quota=snapshot,
            )
        return snapshot

    # ── utils ────────────────────────────────────────────────────────────
    @staticmethod
    def _money(value: Any) -> str:
        """Serialize a Decimal cost to a fixed 6-dp string."""
        if value is None:
            return "0.000000"
        return str(Decimal(str(value)).quantize(Decimal("0.000001")))
