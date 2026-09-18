# Chat QA — C7 focus stack restore (2026-09-17)

**Seat:** Pulse · **Brand:** nibras · **User:** `ahmed`  
**Fixture:** Abrar `1021` → switch `1416` → “Back to Abrar”

## Goal

Prior focused people must remain restoreable after a topic switch without
re-asking who Abrar is.

## Fix

| Layer | Change |
|-------|--------|
| WorkingMemory | Focus **stack** (last 5) with `entity_id` + aliases |
| Anaphora | “Back to X” / “again” restores prior focus; rewrites with `employee_no` |
| Runner | `update_focus_from_resolve_results` after tool turns |

## Unit tests

`ai/tests/test_c7_focus_restore.py` → **PASS** (plus gap2/gap3)

## Live prove

| Step | Focus | Verdict |
|------|-------|---------|
| Tell me about Abrar | `entity_id=1021` | **PASS** |
| Look up 1416 | `entity_id=1416` | **PASS** |
| Back to Abrar | Restored `1021`; reply cites employee number **1021** | **PASS** |

## Result

**C7 PASS**
