# Tasks production — plan-create pack bind · 2026-09-30

Surface only. Ask 10/10 on 2035 / 2036 / 2038 unchanged. Jail L3 stands.
Excellence 17/54 unchanged. Night 2026-09-23 FAIL stays. Pulse L6/L7 unclaimed.
R7 not run. No `pulse_gauge --write`. `pulse_gauge --gate` pass. `pack_contract --gate` pass.

## Files

| File | Role |
|---|---|
| `PV2-tasks-prod-2026-09-29-205750.json` | History. 5/12. Do not overwrite. |
| `PV2-tasks-prod-2026-09-28-075752.json` | History. Failed Run. Do not overwrite. |
| `PV2-tasks-prod-2026-09-30-164015.json` | Pre-bind live. Still 5/12. Create 400 = no plan. |
| `PV2-tasks-prod-2026-09-30-164356.json` | After bind loaded on nibras `--noreload`. **8/12**. |

## Cause

Chat Plan-dial (`_run_chat`) already used `@bound_to_pack`. `POST /ai/plans/` runs `SkillAwarePlanner.decompose` on a worker thread with no pack bound. `_DECOMPOSE_AGENT_PROMPT` and `TASK_DECOMPOSE` are live pack strings: unbound they format empty. The model saw identity only, answered in prose, `_parse_plan_response` returned None, create returned 400 “no usable plan”.

Isolated: `test_llm_decompose_binds_the_instance_pack_before_the_model_call` failed until the decorator landed (system prompt had no `Return ONLY valid`). Skills were refused under `force_decompose`; they were not the miss. The parser was not changed. No retry-until-JSON.

## Fix

`@bound_to_pack` on `SkillAwarePlanner.decompose` and `_llm_decompose` in `backend/ai/engine/cognition/plan/planner.py`. Same decorator Chat and ReAct already use. `--noreload` process required `./manage.sh platform nibras --apply` to load it.

## 164356 (emp_2378, nibras)

Reached 8. Failed 2 (R8, R12). Partial 1 (R4). Missing 1 (R7).

| KPI | Honest |
|---|---|
| R1 | reached |
| R2 | reached |
| R3 | reached |
| R4 | partial — Taskso browser file still required |
| R5 | reached |
| R6 | reached — full file, not a persona-only recheck. emp_1067 payroll-runs 403 |
| R7 | missing — no STACK-HOLD |
| R8 | fail — night 2026-09-23 FAIL stays |
| R9 | reached |
| R10 | reached — p50 2315 ms |
| R11 | reached |
| R12 | fail — R4, R7, R8 still open on this file |

Next closable cells need Taskso (R4) or COMMS STACK-HOLD + `PULSE_NIGHTLY_LIVE=1` as emp_1067 (R7), then a new night that PASSes (R8). This seat stops.
