# PEC-2A — Learning-reuse proof

**Date:** 2026-09-16  
**Verdict:** **PROVED** (fixture-based HRMS arc) — not CUT  
**Roadmap:** P2 Prove Learning-Reuse

## Arc exercised

1. **Draft** — `payroll_run_variance_check` (procedure, Nibras payroll variance)
2. **Admit/promote** — `run_skill_admission` (marginal-gain critic disabled; other critics pass) → `instance_promoted`
3. **Later plan match** — `SkillAwarePlanner.decompose` on an HRMS utterance → `source=skill`, `invoke_skill`
4. **Reuse counter + ledger** — terminal skill-sourced `Run` → `feed_run_feedback` → `usage_count` 0→1 + `AuditLog(action=ai.skill_reused)`

## Counter before / after

| Field | Before reuse | After reuse |
|-------|--------------|-------------|
| `status` | `instance_promoted` | `instance_promoted` (unchanged — RULE_21) |
| `usage_count` | **0** | **1** |
| `success_rate` | 0.0 | 1.0 |

Captured IDs from the evidence dump (2026-09-16T13:07:37Z):

- `skill_id` = `c33ff3f5-3c05-41e3-88b5-3907b814487b`
- `run_id` = `9928a775-4413-4e02-84c9-287007f60a0e`
- `SkillAdmissionLog.id` = `e6b44114-bb7c-4e7c-8efd-27d5dc118b3b` (`verdict=admitted`)
- `AuditLog.id` = `47f88d9c-fa9a-43a7-a5f7-418cc3b057fc` (`action=ai.skill_reused`)

Ledger detail citing the skill:

```json
{
  "run_id": "9928a775-4413-4e02-84c9-287007f60a0e",
  "skill_id": "c33ff3f5-3c05-41e3-88b5-3907b814487b",
  "skill_name": "payroll_run_variance_check",
  "success": true,
  "vetoed": 0,
  "usage_count": 1,
  "latency_ms": 420.0
}
```

Planner match log:

```
SkillAwarePlanner: matched skill=payroll_run_variance_check score=0.95 kind=procedure
SkillAwarePlanner: routing non-plan skill 'payroll_run_variance_check' to invoke_skill
```

## Code changes

- `backend/ai/feedback/skill_flywheel.py` — after `update_stats`, re-fetch skill for accurate `usage_count`; write `AuditLog` `ai.skill_reused` (best-effort).
- `backend/ai/tests/test_pec2a_learning_reuse.py` — end-to-end fixture arc (draft→admit→plan→counter+ledger).
- `backend/ai/tests/test_skill_flywheel.py` — assert ledger row + `usage_count` on successful feed.

## Verification

```bash
cd /home/ahmed/ws/carbon/backend && \
  ../.venv/bin/python -m pytest \
    ai/tests/test_learning_trigger.py \
    ai/tests/test_flight_learning.py \
    ai/tests/test_pec2a_learning_reuse.py \
    ai/tests/test_skill_reuse.py \
    -q --maxfail=5 --disable-warnings
# 28 passed
./.ai-toolkit/scripts/verify.sh backend
# GATE PASSED
```

## Notes / limits

- Fixture-based (no live LLM). Keyword match on skill name in the HRMS utterance clears the planner threshold — sufficient to prove the hot path.
- Marginal-gain critic remains disabled in the fixture (same pattern as `test_skill_admission`) because `evals.stream` is absent; gate-only promotion still runs structural/harmlessness/consistency.
- Live unattended heartbeat→consolidation→draft remains PEC-1A’s concern; this phase proves **reuse after gate promotion**.
