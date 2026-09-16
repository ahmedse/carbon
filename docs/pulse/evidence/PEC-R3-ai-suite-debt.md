# PEC-R3 — AI suite debt

**Date:** 2026-09-16  
**Worker:** backend-worker / debugger-fixer (Pulse seat)  
**Scope:** Partitioned inventory + fixes for  
`test_durable` · `test_chat_stream` · `test_ports` · `test_people_grounding` · `test_web_search_tool`  
**Postgres:** **UP** (re-verified after earlier DOWN / connection-refused block).  
**Status:** **PARTIAL** — greenable partitions fixed; `test_people_grounding` now **GREEN (20/20)**; remaining django_db partitions still pending full re-run.

## Inventory summary

| File | Tests (approx) | Verified green | Still red / blocked |
|------|---------------:|---------------:|---------------------|
| `test_ports.py` | 22 | **22** | 0 |
| `test_chat_stream.py` | ~12 | **5** non-DB | ~7 django_db pending re-run |
| `test_web_search_tool.py` | 21 | **19** non-DB | 1 django_db pending re-run |
| `test_durable.py` | ~22 | 0 (all django_db) | pending re-run; 2 stale/flaky tests fixed statically |
| `test_people_grounding.py` | 20 | **20** | 0 |

Historical audit (~7 failed + 9 errors) mapped primarily to: ports signature drift, chat_stream `progress_callback` mock drift, durable resume/`failed` + order flakiness, web_search FakeClient missing `post`, plus people FK fixture drift after NSR-7B.

## Evidence table

| Test | Status | Root cause | Fix |
|------|--------|------------|-----|
| `test_ports.py::test_pdp_decide_signature_has_seven_params` | **FIXED → GREEN** | Product PDP Protocol gained attribution kwargs (`actor_chain`, `request_id`, `instance_id`, `host_user_id` — PEC-ID-1); test still expected 7 core params only | **Test** updated to assert full signature (`test_pdp_decide_signature_has_core_and_attribution_params`) |
| `test_chat_stream.py::test_dispatch_task_stream_*` (×3) | **FIXED → GREEN** | `dispatch_task_stream` → `_run_chat(..., progress_callback=pcb)`; fakes lacked kwarg → `TypeError` | **Test** fakes accept `progress_callback=None`; assert pcb is async |
| `test_chat_stream.py::test_chat_stream_builds_payload_and_delegates` | **GREEN** | — | — |
| `test_chat_stream.py` django_db stream/persist/SSE | pending | Was blocked on Postgres down | Re-run when convenient |
| `test_web_search_tool.py::test_search_result_is_external_labelled` | **FIXED → GREEN** | `_FakeClient` had `get` only; product `_ddg_html_search` uses `client.post` | **Test** mock adds `post` → empty `_Resp(text="")` |
| `test_web_search_tool.py` other non-DB (18) | **GREEN** | — | — |
| `test_web_search_tool.py::test_has_capability_resolves_for_admin` | pending | django_db | Re-run when convenient |
| `test_durable.py::test_resume_rejects_non_resumable_statuses` | **FIXED (static)** | Test listed `failed` as reject; product `_RESUMABLE_STATUSES` includes `failed` (intentional; covered by `test_resume_requeues_failed_*`) | **Test** drop `failed` from reject list |
| `test_durable.py::test_replay_preserves_step_order_and_depends_on` | **FIXED (static)** | Dict key order from unordered queryset → flaky `[1,0]` vs `[0,1]` | **Test** `.order_by("step_index")` |
| `test_durable.py` (remainder) | pending | Was blocked on Postgres down | Re-run full file when convenient |
| `test_people_grounding.py` (all 20) | **FIXED → GREEN** | Fixtures assigned `gender=''`/`'male'` strings; `Employee.gender` is now FK→`ReferenceValue`. Position ORM hit stale `grade` CharField vs model `grade_id` under `--reuse-db --nomigrations`. Analytics still treated gender as free-text. | **Test** fixtures `_ref`/`_as_ref`; omit Position.grade; **AI helper** resolve ReferenceValue FKs + synonym-merge after label resolve; recreate test DB once via `--create-db` |

## Commands run

```bash
./manage.sh status                         # PostgreSQL: RUNNING (later re-check)
./manage.sh test ai/tests/test_ports.py -q --maxfail=5
# → 22 passed

./manage.sh test \
  ai/tests/test_chat_stream.py::test_dispatch_task_stream_chat_yields_chunks_then_done \
  ai/tests/test_chat_stream.py::test_dispatch_task_stream_non_chat_yields_single_error \
  ai/tests/test_chat_stream.py::test_dispatch_task_stream_engine_error_yields_error \
  ai/tests/test_chat_stream.py::test_dispatch_task_stream_passes_async_callback \
  ai/tests/test_chat_stream.py::test_chat_stream_builds_payload_and_delegates \
  -q --maxfail=5
# → 5 passed

./manage.sh test ai/tests/test_web_search_tool.py -q --maxfail=5 \
  -k 'not test_has_capability_resolves_for_admin'
# → 19 passed, 1 deselected

# people_grounding — after fixture + analytics FK helper + one --create-db:
./manage.sh test ai/tests/test_people_grounding.py -q --tb=line --maxfail=20 --create-db
# → 20 passed
./manage.sh test ai/tests/test_people_grounding.py -q --tb=line --maxfail=20
# → 20 passed (reuse-db OK after recreate)
```

## Files changed

| Action | File | What |
|--------|------|------|
| MODIFY | `backend/ai/tests/test_ports.py` | PDP decide signature assertion |
| MODIFY | `backend/ai/tests/test_chat_stream.py` | `progress_callback` on stream fakes |
| MODIFY | `backend/ai/tests/test_durable.py` | resume reject list; replay `order_by` |
| MODIFY | `backend/ai/tests/test_web_search_tool.py` | FakeClient `post` |
| MODIFY | `backend/ai/tests/test_people_grounding.py` | ReferenceValue gender/nationality fixtures; omit Position.grade |
| MODIFY | `backend/ai/host_executor.py` | Analytics: ReferenceValue FK label resolve + synonym merge; `*_code` aliases |
| CREATE/UPDATE | `docs/pulse/evidence/PEC-R3-ai-suite-debt.md` | this evidence |

No people-app schema edits (Pulse seat). Test DB recreate only (`--create-db`) to align `--nomigrations` reuse-db with current models.

## COMMS → Nibras (residual)

1. **Dev DB vs models:** live brand DBs may still have CharField `people_employee.gender` / `people_position.grade` while models expect `gender_id` / `grade_id` (migration `0026_bucket1_governed_referencevalue_fks`). Apply 0026 on each brand DB when ready.
2. **People suite fixtures:** many `people/tests/*` still assign `gender='female'` strings — same FK ValueError once their DB is migrated; Nibras owns those test updates.
3. **`--reuse-db --nomigrations`:** after people model FK landings, CI/dev must run `--create-db` once (or drop `test_*`) or ORM will keep seeing stale CharField columns.

## Still pending (same partition)

1. Full `ai/tests/test_durable.py`
2. `test_chat_stream.py` django_db cases
3. `test_web_search_tool.py::test_has_capability_resolves_for_admin`

## Out of scope (per dispatch)

- L2 live JWT / L4 browser  
- NSR / people product thickening / people migrations applied by Pulse  
- Reopening PEC/ECF tracks  
