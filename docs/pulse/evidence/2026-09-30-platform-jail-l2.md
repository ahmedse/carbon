# Platform bind / jail — 2026-09-30

Surface: Platform bind / jail only. Not Ask. Not Tasks. Not excellence 17/54.
Canvas: L2 Implemented (unit/API). L3 Proven not claimed. Pulse L6/L7 unclaimed.

## Status

L2 on unit and API after `pulse_gauge --gate` and `pack_contract --gate` pass. L3 is not claimed: B1 and B2 need a live `./manage.sh platform … --apply` (this seat does not start or kill manage.sh). Night 2026-09-23 FAIL is not rewritten. Ask 10/10 on 2035/2036/2038 is unchanged. Tasks 205750 stays 5/12. Excellence stays 17/54. R7 is not started.

## What landed

- Per-call `resolve_instance_id()` on plan, chat provider, flight director, catalog, flywheel. `PLAN_INSTANCE_ID` remains an import snapshot for tests/seeds only.
- `manage.sh platform` writes pack id (`aastmt` → `carbon`) and `PULSE_MEMORY_REDIS_URL` on the same Redis db as `REDIS_URL`.
- Carbon catalog fallback deleted. Missing pack → empty catalog + Pulse-off sentence.
- Catalog rows declare `app`. Host-layer filter: brand preset ∩ deactivated `AppActivation` ∩ `PulseAppEnablement` (default on).
- `full_stop` / Pulse-off refuse the turn before the model. `tool_freeze` blocks host calls.
- Platform hub has a Pulse tab. No new sidebar. No brand picker. Writes need `ai:manage_console`.
- `pack_contract` skips `_` directories (`domain_packs/_platform` is a guide, not a pack).

## Health / Admin reload

File writes without `--apply` do not switch the live process. JWT class-body and `get_settings()` cache stay yesterday until that process restarts. Health `files_brand != process_brand` is the honest signal. This work must not hide that.

## B1–B8

| Id | Honest now |
|---|---|
| B1 | Open live. Code + health shape. No process restart here. |
| B2 | Open live. Health mismatch + Admin banner exist. File-without-apply not executed. |
| B3 | Unit. nibras catalog has no carbon names. Live probe not in the bank. |
| B4 | Unit. medos / tectona / unknown empty + Pulse-off sentence. Live Ask as medos not run. |
| B5 | Unit. people / my enablement filter. Live Admin toggle not run. |
| B6 | Unit. full_stop and tool_freeze. Live Admin click not run. |
| B7 | Not started. Ask 10/10 and Tasks 5/12 unchanged. No R7. |
| B8 | Code + API + IA unit. Browser walk of the tab not run. |
