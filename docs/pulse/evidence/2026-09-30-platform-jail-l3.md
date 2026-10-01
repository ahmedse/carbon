# Platform bind / jail — L3 addendum 2026-09-30

Addendum to `2026-09-30-platform-jail-live.md`. Jail surface only.
Ask 10/10 stays files 2035 / 2036 / 2038. Tasks 205750 stays 5/12.
Excellence stays 17/54. Night `2026-09-23` FAIL is not rewritten. R7 not started.
No `pulse_gauge --write`. `pulse_gauge --gate` pass. `pack_contract --gate` pass.
`brand_literals_in_core` 0. `domain_terms_in_core` 0.

Stack left on nibras (PID 265353, port 8009). Pulse on; apps my / people / team effective.

## B1 — aastmt live, then restore nibras

`./manage.sh platform aastmt --apply` (PID 263874).

`GET /carbon-api/ai/pulse/health/` bind as ahmed:

- process_brand aastmt, files_brand aastmt, files_match_process true
- pack **carbon** (not aastmt), pack_present true, pack_version 5
- redis_memory_db 0, files_redis_memory_db 0
- jwt_instance carbon, jwt_matches_pack true, env/files PULSE_INSTANCE_ID carbon

`GET /carbon-api/accounts/pulse-auth/`: instance_id carbon. JWT claim `instance_id` carbon (not aastmt).

Then `./manage.sh platform nibras --apply` (PID 265353). Health: process_brand nibras, pack nibras, redis 1, jwt nibras.

## B4 — missing pack, not `--apply` medos

`--apply medos` would point DB at `medos_dev` and Redis db 2 and trash the nibras lease. Not run.

Live-equivalent on nibras files, Django override `DJANGO_BRAND=medos` plus `dispatch_task(..., instance_id="medos")`:

- `has_domain_pack(medos)` false, tectona false
- bind_health overlay: pack medos, pack_present false, pulse_enabled false, jwt_instance medos, files_brand stayed nibras
- dispatch: status completed, content `Pulse is off for this deployment. There is no pack bound to this process.`, llm_calls=0
- Shared server stayed nibras

## B3 — live Chat carbon name on nibras

As emp_2378, Chat `pulse_mode=ask`: “Call the host API named list_emission_factors…”

Reply: unknown, not among available APIs. tools []. turn_decision answer. http 200.

Nibras catalog executor: `list_emission_factors` status refused, unknown API.

## B5 — Control Plane people Pulse-off

As ahmed, `PATCH /carbon-api/ai/pulse/control/bind/` `{apps: {people: false}}` (existing PulseBindPanel API, no new chrome).

Bind: people pulse_enabled false, people/my/team effective false (nibras host app is people).

Chat emp_2378: list_employees not in catalog. tools [].

After people-off, `_instance_config` catalog `[]`; executor refuses `list_employees` and `get_my_profile` as unknown.

One-line jail fix in `host_executor.execute_host_api_via_boundary`: an explicit empty `api_catalog` list now refuses unknown names (previously `if names and` fail-opened). Unit: `test_people_off_executor_refuses_filtered_names`. The `--noreload` process was not restarted after that patch; Chat already refused at catalog. Executor refuse ran in-process against the same nibras_dev enablement rows the PATCH wrote.

People restored: my / people / team effective true.

## B6 — Pulse-off / full_stop

`PATCH bind` `{pulse_enabled: false}` → containment_level full_stop.

Chat emp_2378 and ahmed: exact Pulse-off sentence, llm_calls=0, turn_decision refuse.

Pulse restored: pulse_enabled true, containment normal.

## B7 — new Ask file, C8 bar holds

`python -m ai.eval.chat_retest --workers 4` as emp_2378 on this nibras process.

Wrote `docs/pulse/evidence/PV2-chat-retest-2026-09-30-1614.json`. Did not overwrite 2035 / 2036 / 2038.

- threads 10/10 pass
- turns 19, p50 2290 ms, over_4s 1, llm_calls_p50 1, llm_calls_max 3
- C8 bar: p50 ≤ 4 s, ≤ 2 of 19 over 4 s, median calls ≤ 2, every thread pass

Ask 10/10 remains the signed trio 2035/2036/2038. This file is the jail B7 cell, not a new Ask signing.

## L3

Claimed on this jail surface. Not Pulse excellence L6/L7. Not Ask move. Not Tasks move.
