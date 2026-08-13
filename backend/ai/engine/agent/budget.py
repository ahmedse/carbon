"""
BudgetTracker — per-run token budget management.

Tracks token consumption during a run, sub-allocates budget to workers,
and enforces graceful degradation when budget is exceeded.

Usage::

    tracker = BudgetTracker(run_id, total_budget=50_000, db_session=db)
    tracker.consume(1500)  # after an LLM call
    sub_budget = tracker.allocate_worker_budget(3)  # split among 3 workers
    if tracker.exceeded:
        # produce text fallback
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from ai.engine.core.config import get_settings
from ai.engine.core.models import Run
from ai.store import first

logger = logging.getLogger("pulse.agent.budget")


@dataclass
class BudgetSnapshot:
    """Immutable snapshot of budget state for reporting."""
    budget: int
    consumed: int
    remaining: int
    exceeded: bool
    justification: str | None


class BudgetTracker:
    """Per-run token budget tracker.

    Tracks token consumption against a per-run cap.  All writes are
    persisted to the ``Run`` row so the budget survives restarts.
    """

    def __init__(
        self,
        run_id: str,
        total_budget: int | None = None,
        db_session=None,
    ):
        """Create a budget tracker for a run.

        Args:
            run_id: The Run.id to track against.
            total_budget: Token cap. If None, reads from settings.RUN_TOKEN_BUDGET_DEFAULT.
            db_session: Async SQLAlchemy session.
        """
        settings = get_settings()
        self._run_id = run_id
        self._total_budget = total_budget if total_budget is not None else settings.RUN_TOKEN_BUDGET_DEFAULT
        self._db = db_session
        self._consumed: int = 0
        self._exceeded: bool = False
        self._justification: str | None = None
        self._worker_budgets: dict[str, int] = {}
        self._initialized = False

    # ── Properties ──────────────────────────────────────────────────────────

    @property
    def remaining(self) -> int:
        """Tokens remaining in budget."""
        return max(0, self._total_budget - self._consumed)

    @property
    def exceeded(self) -> bool:
        """True if the run has exceeded its token budget."""
        return self._exceeded or self._consumed >= self._total_budget

    # ── Core tracking ───────────────────────────────────────────────────────

    async def _ensure_initialized(self) -> None:
        """Load state from DB on first use, or persist initial budget."""
        if self._initialized:
            return
        self._initialized = True

        if self._db is None:
            logger.warning("BudgetTracker: no db_session — budget tracking is in-memory only")
            return

        try:
            run = first(await self._db.select(Run, {"id": self._run_id}))
        except Exception as exc:
            logger.warning("BudgetTracker: failed to load from DB — in-memory only: %s", exc)
            return

        if run is None:
            # Run row doesn't exist yet — persist initial budget
            logger.debug(
                "BudgetTracker: Run row %s not found — will persist on first write",
                self._run_id[:8],
            )
            return

        # Restore from DB
        self._consumed = run.tokens_consumed or 0
        if run.token_budget is not None:
            self._total_budget = run.token_budget
        self._exceeded = run.budget_exceeded or False
        self._justification = run.fan_out_justification

        if run.worker_budgets_json:
            try:
                self._worker_budgets = json.loads(run.worker_budgets_json)
            except (json.JSONDecodeError, TypeError):
                self._worker_budgets = {}

        logger.debug(
            "BudgetTracker initialized: run=%s budget=%d consumed=%d remaining=%d exceeded=%s",
            self._run_id[:8], self._total_budget, self._consumed,
            self.remaining, self._exceeded,
        )

    async def consume(self, tokens: int) -> None:
        """Record token consumption. Call after every LLM call.

        Args:
            tokens: Number of tokens consumed (input + output).
        """
        await self._ensure_initialized()

        self._consumed += tokens
        if self._consumed >= self._total_budget:
            if not self._exceeded:
                logger.warning(
                    "Budget exceeded: run=%s consumed=%d budget=%d",
                    self._run_id[:8], self._consumed, self._total_budget,
                )
            self._exceeded = True

        # Persist to DB
        await self._persist()

    async def _persist(self) -> None:
        """Write current state to the Run row (crash-resilient)."""
        if self._db is None:
            return
        try:
            run = first(await self._db.select(Run, {"id": self._run_id}))
            if run is None:
                # Row doesn't exist — nothing to update (chat path has no Run row)
                logger.debug(
                    "BudgetTracker: Run %s not found for persist — writing as new",
                    self._run_id[:8],
                )
                return
            worker_json = json.dumps(self._worker_budgets) if self._worker_budgets else None
            run.token_budget = self._total_budget
            run.tokens_consumed = self._consumed
            run.budget_exceeded = self._exceeded
            run.fan_out_justification = self._justification
            run.worker_budgets_json = worker_json
            await self._db.flush()
        except Exception:
            logger.exception("BudgetTracker: failed to persist to Run row %s", self._run_id[:8])

    # ── Worker sub-allocation ───────────────────────────────────────────────

    def allocate_worker_budget(self, num_workers: int) -> list[int]:
        """Split a portion of the run budget among N workers.

        Formula: ``total_pool = int(budget * WORKER_SHARE)``, then each worker
        gets ``max(total_pool // num_workers, MIN_WORKER)``.

        Args:
            num_workers: Number of parallel workers.

        Returns:
            List of per-worker budget values.
        """
        settings = get_settings()
        share = settings.RUN_TOKEN_BUDGET_WORKER_SHARE
        min_worker = settings.RUN_TOKEN_BUDGET_MIN_WORKER

        total_pool = int(self._total_budget * share)
        if num_workers <= 0:
            return []

        per_worker = max(total_pool // num_workers, min_worker)

        logger.debug(
            "BudgetTracker: allocate_worker_budget num=%d pool=%d per_worker=%d",
            num_workers, total_pool, per_worker,
        )

        return [per_worker] * num_workers

    def return_unused(self, agent_id: str, unused: int) -> None:
        """Return unused budget from a worker back to the pool.

        This effectively reduces consumed count by the unused amount,
        giving the orchestrator more headroom.

        Args:
            agent_id: Worker agent ID.
            unused: Tokens not used by the worker.
        """
        if unused <= 0:
            return
        self._consumed = max(0, self._consumed - unused)
        self._worker_budgets[agent_id] = self._worker_budgets.get(agent_id, 0) - unused
        logger.debug(
            "BudgetTracker: returned unused=%d from agent=%s consumed=%d",
            unused, agent_id[:8], self._consumed,
        )

    # ── Justification ───────────────────────────────────────────────────────

    async def set_justification(self, text: str) -> None:
        """Record why the orchestrator chose to fan out.

        Args:
            text: Human-readable justification (e.g. "3 independent sub-questions").
        """
        self._justification = text
        if self._db is not None:
            try:
                run = first(await self._db.select(Run, {"id": self._run_id}))
                if run is not None:
                    run.fan_out_justification = text
                    await self._db.flush()
            except Exception:
                logger.exception("BudgetTracker: failed to persist justification")

        logger.info("BudgetTracker: justification set run=%s text=%s", self._run_id[:8], text[:80])

    # ── Snapshot ────────────────────────────────────────────────────────────

    def snapshot(self) -> dict:
        """Return a dict snapshot of current budget state.

        Returns:
            {budget, consumed, remaining, exceeded, justification}.
        """
        return {
            "budget": self._total_budget,
            "consumed": self._consumed,
            "remaining": self.remaining,
            "exceeded": self.exceeded,
            "justification": self._justification,
        }
