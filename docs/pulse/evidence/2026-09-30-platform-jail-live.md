# Platform bind / jail — live health 2026-09-30

Surface: Platform bind / jail only. Not Ask. Not Tasks. Not excellence 17/54.
Ask 10/10 on 2035/2036/2038 is unchanged. Tasks 205750 stays 5/12. Night 2026-09-23 FAIL is not rewritten. R7 is not started. No `pulse_gauge --write`.

Process was restarted once: `./manage.sh platform nibras --apply` (last resort to load identity code). Files had been `aastmt` with `PULSE_INSTANCE_ID=aastmt` (brand slug). Apply wrote pack id `nibras` and `PULSE_MEMORY_REDIS_URL` db 1. Stack left on nibras.

`pulse_gauge --gate` pass. `pack_contract --gate` pass. `brand_literals_in_core` 0.

## B2 — file switch without apply (process still aastmt, old PID 237493)

`./manage.sh platform eduos` (no `--apply`).

Files: `DJANGO_BRAND=eduos`, `PULSE_INSTANCE_ID=eduos`, `PULSE_MEMORY_REDIS_URL` db 4.

Live `GET /carbon-api/ai/pulse/health/` bind:

```json
{
  "process_brand": "aastmt",
  "files_brand": "eduos",
  "files_match_process": false,
  "switched": false,
  "pack": "carbon",
  "pack_present": true,
  "jwt_instance": "aastmt",
  "files_pulse_instance_id": "eduos",
  "redis_memory_db": 0,
  "files_redis_memory_db": 4
}
```

`switched` is false. Pulse Admin mismatch copy: files ≠ process, Pulse has not switched.

## B1 — nibras after `--apply` (PID 251751, this code)

nibras_dev needed `accounts.0017_user_must_change_password` and `ai.0047_pulseappenablement` before HTTP login. That is host schema, not a Pulse identity leak. `ensure_nibras_admins`: ahmed password already matched.

`GET /carbon-api/ai/pulse/health/` bind as ahmed:

```json
{
  "process_brand": "nibras",
  "files_brand": "nibras",
  "files_match_process": true,
  "switched": true,
  "pack": "nibras",
  "pack_version": "17",
  "pack_present": true,
  "pulse_enabled": true,
  "containment_level": "normal",
  "jwt_instance": "nibras",
  "files_pulse_instance_id": "nibras",
  "env_pulse_instance_id": "nibras",
  "jwt_matches_pack": true,
  "redis_memory_db": 1,
  "files_redis_memory_db": 1,
  "extra_packs": []
}
```

`GET /carbon-api/ai/pulse/control/bind/`: Pulse on; apps `my`, `people`, `team`.
`GET /carbon-api/accounts/pulse-auth/`: `instance_id` nibras; Pulse JWT claim `instance_id` nibras.

B1 aastmt (pack carbon, Redis db 0, JWT carbon) is unit-locked (`test_jwt_and_health_use_pack_id_not_brand_slug`). This seat did not `--apply` aastmt after the nibras reload.

## B8 — browser

`http://localhost:5179/admin/ai/platform?tab=pulse` as ahmed. Pulse Control sidebar still six destinations (Command Center, Domain, Assets, Evidence, Learning, Platform). Pulse is a Platform tab next to Spend / Engine / Roles. No brand picker. Health chips: process brand nibras, pack nibras, version 17, pack present, Redis db 1, JWT nibras. Copy: this tab does not switch platforms.

## B3

Unit: nibras executor refuses `list_emission_factors`; carbon executor refuses `list_employees`. Live carbon-name Chat probe not run.

## B7

Not started. No new Ask file. No Tasks prod file. No R7.
