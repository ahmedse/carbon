# Q4 staged-exit inventory (2026-09-24)

## Spine meter (L7)

`harness_budget.staged_exits` counts `stage_exit(` / `StagedExit(` in `runner.py` only.

| measured | ceiling | status |
|----------|---------|--------|
| **3** | **4** | PASS |

Spine call sites: `chat_handoff` · `ess_bound_self_read` · `off_limits`.

## Soft gates (`stage_soft_exit`, not in spine meter)

Still on legacy. Skipped when `PULSE_UNDERSTAND=v21` via `may_stage`.

nav_fast_path · plan_status · next_step · zero_llm · plan_dial_process · restyle · typed_router · process_brief_early · deixis · process_brief ×2 · nav_ground · chat_clarify

## Next

1. Live `PULSE_UNDERSTAND=shadow` 5 days (STACK-HOLD).
2. Delete soft-gate *bodies* after shadow agreement.
3. Flip `v21` — Decision owns soft paths.
