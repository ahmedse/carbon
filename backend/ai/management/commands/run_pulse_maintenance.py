"""Run Pulse maintenance loops on demand with durable heartbeat telemetry.

This command is intended for cron/systemd timer invocation per brand instance.
It reuses the existing loop entrypoints and records one durable heartbeat row
per loop execution attempt.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from decimal import Decimal
from uuid import uuid4

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Sum
from django.utils import timezone

from ai.engine.core.config import get_settings
from ai.instance_registry import resolve_instance_id
from ai.models import LLMCallLog, PulseHeartbeat
from ai.models.core import Instance

_VALID_LOOPS = ("proactive", "consolidation", "distill", "decay")
_DEFAULT_LOOPS = ",".join(_VALID_LOOPS)


@dataclass
class _LoopResult:
    status: str
    items_produced: int = 0
    llm_calls: int = 0
    cost_usd: Decimal = Decimal("0")
    error: str = ""


class Command(BaseCommand):
    help = (
        "Run background Pulse maintenance loops on demand with durable "
        "heartbeat telemetry."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--instance",
            type=str,
            default=None,
            help="Instance id to run (default: resolve from DJANGO_BRAND).",
        )
        parser.add_argument(
            "--loops",
            type=str,
            default=_DEFAULT_LOOPS,
            help=(
                "CSV loops to run. Allowed: proactive, consolidation, distill, "
                "decay."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would run without writes or loop execution.",
        )

    def handle(self, *args, **options):
        instance_id = options.get("instance") or resolve_instance_id()
        loops = self._parse_loops(options.get("loops") or _DEFAULT_LOOPS)
        dry_run = bool(options.get("dry_run"))

        if not dry_run and not Instance.objects.filter(id=instance_id).exists():
            raise CommandError(f"Unknown instance '{instance_id}'.")

        if dry_run:
            for loop_name in loops:
                self._emit_summary(
                    instance_id=instance_id,
                    loop_name=loop_name,
                    status="skipped",
                    items=0,
                    llm_calls=0,
                    cost_usd=Decimal("0"),
                )
            return

        for loop_name in loops:
            result = self._run_single_loop(instance_id, loop_name)
            self._emit_summary(
                instance_id=instance_id,
                loop_name=loop_name,
                status=result.status,
                items=result.items_produced,
                llm_calls=result.llm_calls,
                cost_usd=result.cost_usd,
            )

    def _run_single_loop(self, instance_id: str, loop_name: str) -> _LoopResult:
        now = timezone.now()
        running = PulseHeartbeat.objects.filter(
            instance_id=instance_id,
            loop=loop_name,
            status="running",
            finished_at__isnull=True,
        ).exists()
        if running:
            return _LoopResult(
                status="skipped",
                error="existing running heartbeat detected",
            )

        heartbeat = PulseHeartbeat.objects.create(
            id=uuid4(),
            instance_id=instance_id,
            loop=loop_name,
            started_at=now,
            status="running",
        )

        before_calls, before_cost = self._llm_usage_for_day(instance_id)
        status = "ok"
        items = 0
        err = ""

        try:
            skip_reason = self._skip_reason(instance_id, loop_name)
            if skip_reason:
                status = "skipped"
                err = skip_reason
            else:
                items = self._run_loop(loop_name=loop_name, instance_id=instance_id)
        except Exception as exc:  # noqa: BLE001 - fail-soft per loop
            status = "error"
            err = str(exc)

        after_calls, after_cost = self._llm_usage_for_day(instance_id)
        used_calls = max(0, after_calls - before_calls)
        used_cost = max(Decimal("0"), after_cost - before_cost)

        heartbeat.finished_at = timezone.now()
        heartbeat.status = status
        heartbeat.items_produced = max(0, int(items or 0))
        heartbeat.llm_calls = used_calls
        heartbeat.cost_usd = used_cost
        heartbeat.error = err
        heartbeat.save(
            update_fields=[
                "finished_at",
                "status",
                "items_produced",
                "llm_calls",
                "cost_usd",
                "error",
            ]
        )

        return _LoopResult(
            status=status,
            items_produced=heartbeat.items_produced,
            llm_calls=heartbeat.llm_calls,
            cost_usd=heartbeat.cost_usd,
            error=err,
        )

    def _skip_reason(self, instance_id: str, loop_name: str) -> str:
        settings = get_settings()
        spent = self._llm_usage_for_day(instance_id)[1]
        budget = self._daily_budget_usd()
        if budget > 0 and spent >= budget:
            return "daily budget exhausted"

        if (
            loop_name == "consolidation"
            and int(settings.CONSOLIDATION_SWEEP_MAX_LLM_CALLS) <= 0
        ):
            return "consolidation llm call cap is zero"

        return ""

    def _daily_budget_usd(self) -> Decimal:
        # Overridable seam (mirrors _llm_usage_for_day) so budget policy is testable.
        return Decimal(str(get_settings().LLM_DAILY_BUDGET_USD or 0))

    def _llm_usage_for_day(self, instance_id: str) -> tuple[int, Decimal]:
        day_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        agg = LLMCallLog.objects.filter(
            instance_id=instance_id,
            created_at__gte=day_start,
        ).aggregate(total_calls=Sum("llm_calls"), total_cost=Sum("cost_usd"))
        return int(agg.get("total_calls") or 0), Decimal(str(agg.get("total_cost") or 0))

    def _parse_loops(self, raw: str) -> list[str]:
        loops = [part.strip().lower() for part in raw.split(",") if part.strip()]
        if not loops:
            raise CommandError("At least one loop must be provided.")

        unknown = [name for name in loops if name not in _VALID_LOOPS]
        if unknown:
            raise CommandError(
                f"Unknown loop(s): {', '.join(sorted(set(unknown)))}. "
                f"Allowed: {', '.join(_VALID_LOOPS)}"
            )

        # Keep first occurrence order while removing duplicates.
        deduped: list[str] = []
        for name in loops:
            if name not in deduped:
                deduped.append(name)
        return deduped

    def _run_loop(self, *, loop_name: str, instance_id: str) -> int:
        return asyncio.run(self._run_loop_async(loop_name=loop_name, instance_id=instance_id))

    async def _run_loop_async(self, *, loop_name: str, instance_id: str) -> int:
        from ai.engine.core.database import get_session_factory
        from ai.engine.core.models import Instance as EngineInstance

        factory = get_session_factory()
        async with factory() as db:
            rows = await db.select(EngineInstance, ("id", instance_id))
            if not rows:
                raise RuntimeError(f"Instance '{instance_id}' not found in store")
            instance = rows[0]

            if loop_name == "proactive":
                from ai.engine.proactive.loop import run_daily_briefing, run_proactive_evaluation
                from ai.engine.proactive.user_watches import run_user_watches

                proactive = await run_proactive_evaluation(db, instance)
                watches = await run_user_watches(db, instance)
                briefing = await run_daily_briefing(db, instance)
                return (
                    int(proactive.get("insights_delivered") or 0)
                    + int(watches.get("watches_fired") or 0)
                    + (1 if briefing.get("delivered") else 0)
                )

            if loop_name == "consolidation":
                from ai.engine.cognition.consolidation import run_consolidation_sweep

                summary = await run_consolidation_sweep(db, instance_id)
                return int(summary.get("skills_created") or 0)

            if loop_name == "distill":
                from ai.engine.cognition.distill.episodic_to_semantic import run_distillation
                from ai.engine.cognition.distill.promotion import run_promotion

                stored = await run_distillation(db, instance)
                promoted = await run_promotion(db, instance)
                return int(stored or 0) + int(promoted or 0)

            if loop_name == "decay":
                from ai.engine.cognition.distill.decay import run_decay

                decayed = await run_decay(db, instance)
                return int(decayed or 0)

        raise RuntimeError(f"Unsupported loop '{loop_name}'")

    def _emit_summary(
        self,
        *,
        instance_id: str,
        loop_name: str,
        status: str,
        items: int,
        llm_calls: int,
        cost_usd: Decimal,
    ) -> None:
        self.stdout.write(
            "instance={instance} loop={loop} status={status} items={items} "
            "llm_calls={llm_calls} cost_usd={cost}".format(
                instance=instance_id,
                loop=loop_name,
                status=status,
                items=max(0, int(items or 0)),
                llm_calls=max(0, int(llm_calls or 0)),
                cost=(cost_usd or Decimal("0")).quantize(Decimal("0.000001")),
            )
        )
