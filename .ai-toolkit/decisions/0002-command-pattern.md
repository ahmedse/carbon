# ADR-0002 — Command Pattern for Reversible Operations

- **Status:** Accepted
- **Date:** 2026-07-31
- **Deciders:** Master Architect
- **Area:** cross-cutting (backend + frontend)

## Context

The Carbon platform has an audit trail (`AuditLogPage`, Django's `LogEntry`) that records *what happened*
but provides **no undo capability**. Users cannot reverse mistakes in DQ rules, data entry, schema changes,
or emission factor edits. This is a known gap in `project.config.md` tech debt and `design-patterns.md` §Command.

Three concrete user stories drive this:

1. **DQ Admin**: Edits a DQ rule threshold from 5% to 50% by mistake → all calculations fail. Must
   manually reconstruct the previous threshold value.
2. **Data Owner**: Bulk-edits 200 electricity rows → realizes wrong meter_id filter was applied.
   Must re-upload CSV or manually revert each row.
3. **Schema Admin**: Deletes a required field from a live table → orphan DataRow values. No way
   to restore the field structure without re-creating it and re-mapping data.

These are production risks for a platform managing real emissions data.

## Decision

We adopt the **Command pattern** (GoF Behavioral) for all mutating operations on the following
domain objects:

| Priority | Domain | Operations | Risk |
|----------|--------|-----------|------|
| **P0** | DQ Rules (`dq.models`) | create, update, delete | Rules gate all data quality — a bad rule breaks the DQ dashboard |
| **P0** | Data Rows (`dataschema.models.DataRow`) | create, bulk_create, update, delete | Bulk edits are common; revert-by-hand is impossible |
| **P1** | Emission Factors (`emissions.models.EmissionFactor`) | create, update, delete | Factor changes propagate to all downstream calculations |
| **P1** | Calculation Rules (`emissions.models.CalculationRule`) | create, update, delete | Rules link tables to factors; a broken link silences calculations |
| **P2** | Schema Fields (`dataschema.models.DataField`) | create, update, delete | Structural — field deletion orphans rows |
| **P2** | SBTi Targets (`emissions.models.SBTiTarget`) | create, update, delete | Targets are infrequently changed |

### Interface

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

@dataclass
class CommandResult:
    """Result of executing or undoing a command."""
    success: bool
    message: str
    affected_count: int = 0
    data_snapshot: Optional[dict] = None  # for complex undo (e.g., deleted field schema)

class Command(ABC):
    """Encapsulates a reversible domain operation."""

    @abstractmethod
    def execute(self, user) -> CommandResult:
        """Perform the operation. Return result with snapshot for undo."""
        ...

    @abstractmethod
    def undo(self) -> CommandResult:
        """Reverse the operation using stored snapshot."""
        ...

    def redo(self, user) -> CommandResult:
        """Re-execute after undo. Default: call execute() again."""
        return self.execute(user)

    @abstractmethod
    def describe(self) -> str:
        """Human-readable description for audit log. E.g. 'Update DQ Rule #42 threshold 5% → 50%'"""
        ...

class CommandInvoker:
    """Manages execution, undo stack, and history."""

    def __init__(self, max_undo_depth: int = 50):
        self._undo_stack: list[Command] = []
        self._redo_stack: list[Command] = []
        self._max_depth = max_undo_depth

    def execute(self, command: Command, user) -> CommandResult:
        result = command.execute(user)
        if result.success:
            self._undo_stack.append(command)
            if len(self._undo_stack) > self._max_depth:
                self._undo_stack.pop(0)  # discard oldest
            self._redo_stack.clear()  # new action invalidates redo chain
        return result

    def undo(self) -> CommandResult:
        if not self._undo_stack:
            return CommandResult(False, "Nothing to undo")
        command = self._undo_stack.pop()
        result = command.undo()
        if result.success:
            self._redo_stack.append(command)
        return result

    def redo(self, user) -> CommandResult:
        if not self._redo_stack:
            return CommandResult(False, "Nothing to redo")
        command = self._redo_stack.pop()
        return command.redo(user)
```

### Concrete Example — DQ Rule Update

```python
class UpdateDQRuleCommand(Command):
    def __init__(self, rule: DQRule, new_fields: dict):
        self._rule = rule
        self._new_fields = new_fields
        self._old_snapshot = {f: getattr(rule, f) for f in new_fields}

    def execute(self, user) -> CommandResult:
        for field, value in self._new_fields.items():
            setattr(self._rule, field, value)
        self._rule.save()
        return CommandResult(True, f"Updated DQ Rule #{self._rule.id}", 1)

    def undo(self) -> CommandResult:
        for field, value in self._old_snapshot.items():
            setattr(self._rule, field, value)
        self._rule.save()
        return CommandResult(True, f"Reverted DQ Rule #{self._rule.id}", 1)

    def describe(self) -> str:
        changes = ", ".join(f"{k}: {self._old_snapshot[k]} → {self._new_fields[k]}"
                           for k in self._new_fields)
        return f"Update DQ Rule #{self._rule.id} ({changes})"
```

### Storage

- **In-memory stack** per request (stateless — cleared after response). Sufficient for single-session undo.
- **NOT persisted** to DB — this is NOT event sourcing. The audit trail (`LogEntry`) already records
  what happened. The undo stack is transient and rebuilt on page load.
- **Future extension**: If cross-session undo is needed, serialize the stack to `django.core.cache`
  keyed by user session. Not in scope for v1.

### Security

- **Undo is scoped to the same user**: A user can only undo their own commands.
- **Undo respects RBAC**: If a user loses the permission needed to perform the original operation
  (e.g., admin revokes their DQ edit role), undo is still allowed (the snapshot already exists).
- **Sensitive data in snapshots**: `data_snapshot` may contain field values. The invoker clears
  snapshots when the stack is popped. No snapshots are persisted to DB.

## Alternatives Considered

- **Event Sourcing (full append-only log)** — Rejected. Too heavy for this project's scale.
  Requires rewriting all mutating operations as events, replay mechanism, snapshotting.
  Good for financial ledgers; overkill for DQ rules and data entry.
- **Memento pattern (full object snapshots)** — Rejected. Storing entire model instances in
  the undo stack would balloon memory for bulk data row edits (200 rows × N fields).
  The Command pattern stores only the diff.
- **Database-level point-in-time recovery** — Rejected. PostgreSQL PITR is a DBA operation,
  not a user-facing undo button. Slow (restore entire DB), not granular.
- **Django's built-in `django-reversion`** — Rejected. Adds a dependency, stores version
  history in DB (bloat), and doesn't provide a clean undo stack UX.
- **Do nothing** — Rejected. The audit trail proves users make mistakes. Undo is a user-facing
  feature, not a nice-to-have. P0 priority for DQ rules and data rows.

## Consequences

- **Positive:**
  - Users can undo mistakes without admin intervention — reduces support burden
  - DQ rule edits are safe — threshold typos are one click away from reversal
  - Bulk data entry is recoverable — undo the entire batch
  - Audit trail (existing `LogEntry`) + undo stack = full accountability
  - Pattern is testable: `assert command.undo().success`

- **Negative / trade-off:**
  - Every mutating operation needs a Command subclass — ~12-15 classes for P0+P1 targets
  - Snapshot storage in memory adds ~1-5KB per undoable operation (acceptable for max 50 depth)
  - Commands must be instantiated with all data BEFORE execution (eager snapshot capture)
  - Does not handle cascading effects (e.g., undoing a factor edit does not re-undo calculations
    that used the old value — those are separate commands)

- **Do NOT re-try:**
  - Full event sourcing architecture — rejected, too heavy
  - DB trigger-based undo — rejected, bypasses business logic
  - REST-level undo endpoint without Command abstraction — rejected, duplicates undo logic across views

## References

- `.ai-toolkit/shared/design-patterns.md` §Command — current state: PARTIAL, missing undo queue
- `.ai-toolkit/project.config.md` — known tech debt line: "No Command pattern for undo in DQ/data entry"
- `TASKS-AUDIT-REMEDIATION.md` §P5-G3 — original scope
- P6 implementation phase (future) will implement Commands for P0 targets first
