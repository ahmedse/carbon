"""P3-07b — Deterministic workflow driver (pure, replay-safe).

The driver maps a run's *plan* (an ordered list of activity specs) onto its
append-only ``RunJournalEntry`` journal and deterministically returns the next
activity to execute — or ``None`` when the run is complete.

Design contract
---------------
* **Pure & deterministic.**  The same ``(specs, entries)`` always yields the
  same answer.  There is no wall-clock, no randomness, and no DB access.  Time
  is deliberately absent so replaying the fold can never diverge.
* **Append-only fold.**  ``next_activity`` folds the journal by ``sequence``
  (latest entry per activity wins).  An activity whose latest entry is
  ``succeeded`` / ``skipped`` is *committed* and skipped forever.  An
  ``outcome_unknown`` activity is NOT re-dispatched (it belongs to the
  reconciliation worker, P3-08).  Everything else is *incomplete*.
* **Dependency order.**  An incomplete activity is eligible only once all of
  its ``depends_on`` activities are committed.  Among eligible activities the
  lowest ``step_index`` wins (ties broken by ``step_id`` for stability).
* **Restart-mid-run.**  ``reconcile_inflight`` re-queues in-flight
  (``dispatched``/``failed``/stale) entries back to ``planned`` — up to the
  retry cap — so a restart resumes at the earliest incomplete activity instead
  of re-running everything from scratch.

Host-side seam only: this module imports Django models and the step-journal
canonical-id helper; the engine never imports it (RULE_20 / ADR-0007).
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

from ai.models.journal import (
    RunJournalEntry,
    ACTIVITY_KIND_LLM,
    ACTIVITY_KIND_HOST,
    STATUS_PLANNED,
    STATUS_DISPATCHED,
    STATUS_SUCCEEDED,
    STATUS_FAILED,
    STATUS_OUTCOME_UNKNOWN,
    STATUS_SKIPPED,
)

# Latest-entry statuses that mean "this activity is permanently done".
COMMITTED_STATUSES: frozenset[str] = frozenset({STATUS_SUCCEEDED, STATUS_SKIPPED})

# Latest-entry statuses that mean "we tried but never got a terminal result"
# and can therefore be safely re-queued to ``planned`` on restart.
REQUEUE_STATUSES: frozenset[str] = frozenset({STATUS_DISPATCHED, STATUS_FAILED})


@dataclass(frozen=True)
class ActivitySpec:
    """A single activity's durable identity — extracted from a ``RunStep``.

    ``frozen=True`` keeps the driver's inputs hashable/immutable, which is what
    makes the fold trivially deterministic.
    """

    step_id: str
    step_index: int
    activity_kind: str = ACTIVITY_KIND_HOST
    depends_on: tuple[str, ...] = ()
    tool_name: str = ""

    @staticmethod
    def from_step(step) -> "ActivitySpec":
        """Build a spec from a ``RunStep`` (duck-typed for test doubles)."""
        depends = getattr(step, "depends_on_json", None) or ()
        if isinstance(depends, str):
            depends = (depends,)
        tool = getattr(step, "tool_name", "") or ""
        step_kind = getattr(step, "step_kind", "") or ""
        kind = (
            ACTIVITY_KIND_LLM
            if (step_kind == ACTIVITY_KIND_LLM or _is_llm_tool(tool))
            else ACTIVITY_KIND_HOST
        )
        return ActivitySpec(
            step_id=str(getattr(step, "step_id", "") or ""),
            step_index=int(getattr(step, "step_index", 0) or 0),
            activity_kind=kind,
            depends_on=tuple(str(d) for d in depends),
            tool_name=tool,
        )


def _is_llm_tool(tool: str) -> bool:
    """Heuristic: an LLM-bearing tool implies the ``llm`` activity kind."""
    t = (tool or "").lower()
    return "llm" in t or "chat" in t or "agent" in t


def infer_activity_kind(spec) -> str:
    """Closed vocabulary: ``llm`` iff there is an LLM tool; else ``host``.

    Accepts an ``ActivitySpec`` or a duck-typed object exposing
    ``activity_kind``/``tool_name``.
    """
    kind = getattr(spec, "activity_kind", "") or ""
    if kind == ACTIVITY_KIND_LLM:
        return ACTIVITY_KIND_LLM
    tool = (getattr(spec, "tool_name", "") or "").lower()
    if _is_llm_tool(tool):
        return ACTIVITY_KIND_LLM
    return ACTIVITY_KIND_HOST


def latest_statuses(entries) -> dict[str, str]:
    """Fold entries by ``sequence`` → one current status per activity.

    ``entries`` may be ``RunJournalEntry`` rows or lightweight objects exposing
    ``.step_id``, ``.status`` and ``.sequence`` (the pure driver accepts both).
    """
    status_by_step: dict[str, tuple[int, str]] = {}
    for e in entries:
        sid = str(getattr(e, "step_id", "") or "")
        if not sid:
            continue
        seq = int(getattr(e, "sequence", 0) or 0)
        status = getattr(e, "status", STATUS_PLANNED) or STATUS_PLANNED
        if sid not in status_by_step or seq > status_by_step[sid][0]:
            status_by_step[sid] = (seq, status)
    return {sid: status for sid, (_, status) in status_by_step.items()}


def next_activity(specs, entries):
    """Return the next activity spec to execute, or ``None`` when complete.

    Deterministic: committed activities are skipped, ``outcome_unknown`` is
    blocked (reconciliation owns it), and the lowest-``step_index`` eligible
    incomplete activity wins.
    """
    statuses = latest_statuses(entries)
    committed = {sid for sid, st in statuses.items() if st in COMMITTED_STATUSES}
    blocked = {sid for sid, st in statuses.items() if st == STATUS_OUTCOME_UNKNOWN}

    eligible: list[ActivitySpec] = []
    for spec in sorted(specs, key=lambda s: (s.step_index, s.step_id)):
        sid = spec.step_id
        if sid in committed:
            continue
        if sid in blocked:
            continue
        if not committed.issuperset(spec.depends_on):
            continue
        eligible.append(spec)

    return eligible[0] if eligible else None


@dataclass(frozen=True)
class RequeueDecision:
    """A restart decision to re-queue an in-flight activity to ``planned``."""

    spec: ActivitySpec
    attempt: int

    def as_dict(self) -> dict:
        return {"step_id": self.spec.step_id, "attempt": self.attempt}


def reconcile_inflight(specs, entries, *, retry_max: int = 3):
    """Decide which in-flight activities to re-queue on a restart-mid-run.

    * ``dispatched`` / ``failed`` → re-queue to ``planned``, bounded by the
      retry cap (a step that already exhausted the cap stays terminal and is
      NOT re-queued).
    * ``succeeded`` / ``skipped`` → leave committed (never re-run).
    * ``outcome_unknown`` → leave for the reconciliation worker (P3-08).
    * a spec with no journal entry at all → considered ``planned`` already, so
      it needs no explicit re-queue (the driver will simply select it).

    Returns a list of ``RequeueDecision`` (the caller appends ``planned``
    entries and resumes the driver).
    """
    statuses = latest_statuses(entries)

    # Count completed (non-planned) dispatch attempts per activity so we never
    # exceed the retry cap on restart.
    dispatch_attempts: dict[str, int] = {}
    for e in entries:
        sid = str(getattr(e, "step_id", "") or "")
        st = getattr(e, "status", STATUS_PLANNED) or STATUS_PLANNED
        if st in {STATUS_DISPATCHED, STATUS_FAILED, STATUS_SUCCEEDED}:
            dispatch_attempts[sid] = max(
                dispatch_attempts.get(sid, -1),
                int(getattr(e, "attempt", 0) or 0),
            )

    decisions: list[RequeueDecision] = []
    for spec in sorted(specs, key=lambda s: (s.step_index, s.step_id)):
        sid = spec.step_id
        latest = statuses.get(sid, STATUS_PLANNED)
        if latest not in REQUEUE_STATUSES:
            continue
        used = dispatch_attempts.get(sid, -1) + 1
        if used >= retry_max:
            # Cap exhausted — this activity is terminal; leave it alone.
            continue
        decisions.append(RequeueDecision(spec=spec, attempt=used))
    return decisions


class RunJournal:
    """Host-side facade over ``RunJournalEntry`` for one run.

    Appends entries with the next monotonic ``sequence`` (``next_sequence`` is
    computed atomically-ish per run via ``max+1``; callers serialize on the
    run).  All writes are appends — entries are never edited in place.
    """

    def __init__(self, run_id: str):
        self.run_id = str(run_id)

    def next_sequence(self) -> int:
        last = (
            RunJournalEntry.objects.filter(run_id=self.run_id)
            .order_by("-sequence")
            .values_list("sequence", flat=True)
            .first()
        )
        return (int(last) + 1) if last is not None else 1

    def append(self, spec, *, status, operation_id="", canonical_inputs=None,
               result=None, error="", attempt=0) -> RunJournalEntry:
        """Append one entry; never mutates an existing entry."""
        entry = RunJournalEntry.objects.create(
            run_id=self.run_id,
            step_id=str(getattr(spec, "step_id", "") or ""),
            step_index=int(getattr(spec, "step_index", 0) or 0),
            activity_kind=infer_activity_kind(spec),
            sequence=self.next_sequence(),
            operation_id=operation_id or "",
            canonical_inputs_json=canonical_inputs,
            status=status,
            result_json=result,
            error=error or "",
            attempt=int(attempt or 0),
        )
        return entry

    def entries(self):
        return list(
            RunJournalEntry.objects.filter(run_id=self.run_id).order_by("sequence")
        )

    def count(self) -> int:
        return RunJournalEntry.objects.filter(run_id=self.run_id).count()

    def for_step(self, step_id: str):
        return list(
            RunJournalEntry.objects.filter(run_id=self.run_id, step_id=step_id)
            .order_by("sequence")
        )


def as_dict(spec: ActivitySpec) -> dict:
    """Serialize a spec (used by resume result payloads)."""
    return asdict(spec)
