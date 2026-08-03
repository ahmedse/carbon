# Phase 5 — Advanced Patterns & Tech Debt
# Master Architect → Backend Worker (DeepSeek) + Frontend Worker (Kimi K3) + Master Architect
# Date: 2026-07-31 | Domain: backend + frontend + architecture
# 3 task groups — G1 (backend), G2 (frontend), G3 (Master Architect design)

---

## PHASE OVERVIEW

P5 addresses 3 items from the audit remediation plan:
- **G1**: `seed_all.py` Builder pattern refactor (Backend Worker, DeepSeek)
- **G2**: Inline sx → theme tokens cleanup (Frontend Worker, Kimi K3)
- **G3**: Command/Undo pattern ADR (Master Architect — design only)

---

## G1 — seed_all.py Builder Pattern Refactor

### REALITY CHECK

- `backend/seed_all.py`: 613 lines, 11 flat functions, procedural `main()` orchestrator
- Each function receives dependent state as parameters (`org_units`, `tables`, `factors`)
- Data flows through the script via return values passed between functions
- The design-patterns.md §Builder specifies: `SeedBuilder().with_users().with_factors().with_targets().run()`

### Why Builder?

1. **Chainable**: `.with_org_units().with_users(org_units).with_tables(org_units).with_periods().run()`
2. **Stateful**: Builder holds intermediate results (org_units, tables, factors) — no manual parameter threading
3. **Idempotent**: Each `.with_*()` step uses `get_or_create()` — safe to re-run
4. **Composable**: Can skip steps: `.with_org_units().with_users(org_units).run()` for quick user seeding

### TARGET DESIGN

```python
class SeedBuilder:
    """Chainable seed orchestrator. Each .with_*() step is idempotent."""

    def __init__(self, years=(2024, 2025, 2026), reset=False):
        self.years = years
        self.reset = reset
        self._org_units = {}
        self._users = []
        self._tables = {}
        self._periods = {}
        self._factors = {}

    # -- Foundation --
    def with_org_units(self): ...
    def with_users(self): ...
    def with_modules_and_tables(self): ...

    # -- Reference data --
    def with_periods(self): ...
    def with_emission_factors(self): ...
    def with_gwp(self): ...

    # -- Activity data --
    def with_activity_data(self): ...

    # -- Rules, targets, DQ --
    def with_calculation_rules(self): ...
    def with_sbti_targets(self): ...
    def with_calculations(self): ...
    def with_data_quality(self): ...

    # -- Terminal --
    def run(self):
        """Execute all stacked steps in dependency order."""
        ...

    def print_summary(self):
        """Print the final summary table + credentials."""
        ...

    @classmethod
    def from_args(cls):
        """Parse sys.argv and return a configured builder."""
        ...
```

### Key behavioral contract

- **DO NOT change any seed data** — values, credentials, org structure, factor codes, GWP numbers — all stay identical
- **DO NOT change the output** — same banner(), same print format, same summary table
- **DO NOT change the CLI** — `python seed_all.py`, `--reset`, `--years` must work identically
- **The existing `main()` function** becomes a thin wrapper:
  ```python
  def main():
      builder = SeedBuilder.from_args()
      builder.run()
      builder.print_summary()
  ```
- Every `with_*()` method returns `self` (chainable)
- Internal state (`_org_units`, `_tables`, `_factors`) is private; methods auto-resolve dependencies. For example, `with_calculation_rules()` checks if `self._tables` is populated; if not, it calls `self.with_modules_and_tables()` first.

---

## G2 — Frontend Inline sx → Theme Tokens

### REALITY CHECK

P4 audit found **2061** `sx={{` occurrences across the frontend. That's a large surface area.

**Strategy**: Don't convert all 2061. Focus on the worst offenders — inline sx with **raw px/hex values**. Many `sx={{` uses already reference theme tokens (`color: 'primary.main', mb: 2`) and are fine.

### Scope

1. **AUDIT**: Identify files where `sx={{` contains raw px numbers (e.g., `padding: '13px'`, `marginTop: 17`) or raw hex colors (e.g., `'#3b82f6'`, `'#43a047'`).
2. **REFACTOR**: Replace with theme tokens: `spacing(2)` for 16px, `theme.palette.primary.main` for blue, etc.
3. **DO NOT change visual appearance** — the output must look identical.

### Target files (from P4 audit)

- `src/pages/ScopeInfoPage.jsx` — known hardcoded hex: `#43a047`, `#1e88e5`, `#ff7043`
- `src/components/HeaderEnhanced.jsx` — flagged in project.config.md as known tech debt
- Any other file found in the audit step with raw px/hex in sx

### Priority order

1. Find files with raw hex in sx: `grep -rn 'sx={{[^}]*#[0-9a-fA-F]\{3,6\}' src/ --include="*.jsx"`
2. Find files with raw px in sx: `grep -rn 'sx={{[^}]*[0-9]\+px' src/ --include="*.jsx"`
3. Fix the worst 3-5 files (most violations per file)
4. Report the rest for P6

### Token substitution map

| Raw value | Token equivalent |
|-----------|-----------------|
| `'#3b82f6'`, `'#1976d2'` | `'primary.main'` |
| `'#dc2626'`, `'#d32f2f'` | `'error.main'` |
| `'#16a34a'`, `'#43a047'` | `'success.main'` |
| `'#ea580c'`, `'#ff7043'` | `'warning.main'` |
| `'#6b7280'` | `'text.secondary'` |
| `'13px'`, `'17px'` | nearest `spacing()`: `spacing(1.5)` (12px), `spacing(2)` (16px) |
| `marginTop: 17` | `mt: 2` (spacing unit = 8px → 16px closest) |

**Rule**: If a raw value doesn't clearly map to an existing token, use the nearest `spacing()` unit — do NOT invent new theme values.

---

## G3 — Command/Undo Pattern ADR (Master Architect)

### Context

- `design-patterns.md` §Command: "What's missing: No undo queue. No command history. No operation logging beyond audit trail."
- `project.config.md` known tech debt: "No Command pattern for undo in DQ/data entry operations — targeted P5-G3"
- The system has an audit trail (`admin/AuditLogPage`) but no undo capability

### What G3 produces

**ADR-0002** in `.ai-toolkit/decisions/0002-command-pattern.md`

### ADR structure

1. **Context**: What problem does undo solve? Which user stories need it?
2. **Decision**: The Command pattern interface spec
3. **Operations that need undo** (prioritized):
   - DQ rule create/edit/delete (high — rules can break calculations)
   - Data row edits (high — data quality impact)
   - Schema field changes (medium — structural)
   - Emission factor edits (medium — calculation impact)
   - Org unit changes (low — rarely changed)
4. **Interface spec**:
   ```python
   class Command(ABC):
       def execute(self) -> CommandResult: ...
       def undo(self) -> CommandResult: ...
       def redo(self) -> CommandResult: ...
       def describe(self) -> str: ...  # human-readable for audit
   ```
5. **Storage**: Command history stored in DB (`CommandLog` model) or in-memory queue
6. **Stack depth**: How many operations are undoable? (recommend: 50)
7. **Consequences**: Storage cost, performance impact, security (who can undo?)
8. **Alternatives considered**: Event sourcing (too heavy), Memento snapshots (storage bloat)

### P5-G3 is NOT implementation — it's the architectural decision document only.

---

## VERIFICATION GATES

### G1 Gate (Backend Worker)
```bash
cd backend
python seed_all.py 2>&1 | tail -20               # must complete, same output
python seed_all.py --reset 2>&1 | tail -20        # reset + reseed
python seed_all.py --years 2025 2>&1 | tail -5     # single year
python -m pytest --reuse-db -q 2>&1 | tail -3      # all tests still pass
```

### G2 Gate (Frontend Worker)
```bash
cd carbon-frontend
npm run build 2>&1 | tail -3                       # build clean
npm run lint 2>&1 | tail -5                         # no new errors
grep -rn 'sx={{[^}]*#[0-9a-fA-F]\{3,6\}' src/ --include="*.jsx" | wc -l  # hex count reduced
```

### G3 Gate (Master Architect)
```bash
ls .ai-toolkit/decisions/0002-command-pattern.md   # ADR exists
```

---

## SCOPE BOUNDARIES

| Group | Worker | Domain | DO NOT TOUCH |
|-------|--------|--------|--------------|
| G1 | Backend Worker | `backend/seed_all.py` only | Any other backend file |
| G2 | Frontend Worker | `carbon-frontend/src/` | Backend, API signatures, hooks |
| G3 | Master Architect | `.ai-toolkit/decisions/` only | Any code file |

---

## REPORT BACK

**G1 + G2**: Follow standard `TASK-RESULTS-P5.md` format per `base-rules.md §9`.

**G3**: Master Architect writes ADR-0002 directly. No worker dispatch needed.
