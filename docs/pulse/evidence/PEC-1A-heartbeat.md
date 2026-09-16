# PEC-1A Evidence — Heartbeat metabolism proof

**Date:** 2026-09-16  
**Instance / brand:** `nibras` (`DJANGO_BRAND=nibras`)  
**Worker:** devops-worker (+ health surface check only; no cognition rewrite)

## Verdict

P1 heartbeat metabolism is **proven at runtime** for `nibras`:

- `run_pulse_maintenance` executed all four loops (`proactive`, `consolidation`, `distill`, `decay`) and wrote terminal `PulseHeartbeat` rows (`status=ok`).
- `GET /carbon-api/ai/pulse/sweeps/` already exposes last heartbeat per `(instance_id, loop)` — no second API invented.
- Local compose now includes a `pulse-heartbeat` sidecar that invokes `run_pulse_maintenance` with brand isolation from `backend/.env`.
- VPS remains systemd via `deploy/instance/setup-pulse-heartbeat.sh nibras` (out of scope on this WSL host).

## 1. Compose / scheduler wiring

**Finding (before):** root `docker-compose.yml` `scheduler` → `run_cognition_loop`, `learning-scheduler` → `run_learning_loop`. Neither invoked `run_pulse_maintenance`.

**Fix:** added service `pulse-heartbeat` (`container_name: carbon-pulse-heartbeat`):

- `env_file: ./backend/.env` → inherits `DJANGO_BRAND` / instance isolation
- loop: `ensure_pulse_instance` once, then `run_pulse_maintenance` on interval `PULSE_HEARTBEAT_INTERVAL` (default 86400s)
- Leaves cognition / learning sidecars unchanged (different faculties)

**Local oneshot equivalent (used for this evidence):**

```bash
cd /home/ahmed/ws/carbon/backend
../.venv/bin/python manage.py run_pulse_maintenance --dry-run
DJANGO_BRAND=nibras ../.venv/bin/python manage.py run_pulse_maintenance
# or: ./manage.sh maintenance
```

## 2. Health / read API (last heartbeat)

Endpoint (existing): `GET /carbon-api/ai/pulse/sweeps/` → field `heartbeats[]`  
Implementation: `backend/ai/sweeps_api.py` (latest row per `(instance_id, loop)`).  
No backend health-surface change required for PEC-1A.

## 3. Dry-run (no writes)

```text
instance=nibras loop=proactive status=skipped items=0 llm_calls=0 cost_usd=0.000000
instance=nibras loop=consolidation status=skipped items=0 llm_calls=0 cost_usd=0.000000
instance=nibras loop=distill status=skipped items=0 llm_calls=0 cost_usd=0.000000
instance=nibras loop=decay status=skipped items=0 llm_calls=0 cost_usd=0.000000
```

`PulseHeartbeat` count unchanged by dry-run (command path writes only on real run).

## 4. Real maintenance run (`DJANGO_BRAND=nibras`)

Command summary lines:

```text
instance=nibras loop=proactive status=ok items=0 llm_calls=0 cost_usd=0.000000
instance=nibras loop=consolidation status=ok items=0 llm_calls=0 cost_usd=0.000000
instance=nibras loop=distill status=ok items=0 llm_calls=0 cost_usd=0.000000
instance=nibras loop=decay status=ok items=0 llm_calls=0 cost_usd=0.000000
```

Loop log excerpts (items=0 is valid when no candidates — metabolism still ticks):

```text
Consolidation sweep: no candidates for instance=nibras
Distillation sweep for nibras: 0 facts stored
Promotion sweep for nibras: 0 facts promoted
Decay sweep for nibras: 0 facts decayed
```

## 5. ORM dump — new `PulseHeartbeat` rows (this tick)

| loop | id | status | started_at (UTC) | finished_at (UTC) | items |
|------|----|--------|------------------|-------------------|-------|
| proactive | `e8a218db-72cc-4f34-9302-ec658e6ecb30` | ok | 2026-09-16T13:02:39.170507+00:00 | 2026-09-16T13:02:39.243817+00:00 | 0 |
| consolidation | `075cac29-28d0-45d4-b2e0-6e3ffc56175e` | ok | 2026-09-16T13:02:39.245851+00:00 | 2026-09-16T13:02:39.254349+00:00 | 0 |
| distill | `c70579b4-dfde-4208-8464-acefedd3e98a` | ok | 2026-09-16T13:02:39.255812+00:00 | 2026-09-16T13:02:39.267070+00:00 | 0 |
| decay | `3578827b-df40-4148-8ee6-0e5c254807f0` | ok | 2026-09-16T13:02:39.268656+00:00 | 2026-09-16T13:02:39.274916+00:00 | 0 |

Total `PulseHeartbeat` rows for `instance_id=nibras` after run: **9** (includes prior ticks from 2026-09-15).

## 6. Sweeps health JSON — last tick

`GET /carbon-api/ai/pulse/sweeps/` (auth JWT) returned 4 heartbeats for `nibras`:

```json
{
  "scheduler_running": false,
  "tasks": [],
  "heartbeats": [
    {
      "instance_id": "nibras",
      "loop": "consolidation",
      "status": "ok",
      "started_at": "2026-09-16T13:02:39.245851+00:00",
      "finished_at": "2026-09-16T13:02:39.254349+00:00",
      "items_produced": 0,
      "llm_calls": 0,
      "cost_usd": "0.000000",
      "error": "",
      "created_at": "2026-09-16T13:02:39.246566+00:00"
    },
    {
      "instance_id": "nibras",
      "loop": "decay",
      "status": "ok",
      "started_at": "2026-09-16T13:02:39.268656+00:00",
      "finished_at": "2026-09-16T13:02:39.274916+00:00",
      "items_produced": 0,
      "llm_calls": 0,
      "cost_usd": "0.000000",
      "error": "",
      "created_at": "2026-09-16T13:02:39.269295+00:00"
    },
    {
      "instance_id": "nibras",
      "loop": "distill",
      "status": "ok",
      "started_at": "2026-09-16T13:02:39.255812+00:00",
      "finished_at": "2026-09-16T13:02:39.267070+00:00",
      "items_produced": 0,
      "llm_calls": 0,
      "cost_usd": "0.000000",
      "error": "",
      "created_at": "2026-09-16T13:02:39.256375+00:00"
    },
    {
      "instance_id": "nibras",
      "loop": "proactive",
      "status": "ok",
      "started_at": "2026-09-16T13:02:39.170507+00:00",
      "finished_at": "2026-09-16T13:02:39.243817+00:00",
      "items_produced": 0,
      "llm_calls": 0,
      "cost_usd": "0.000000",
      "error": "",
      "created_at": "2026-09-16T13:02:39.178711+00:00"
    }
  ]
}
```

## 7. Tests + verify gate

```text
......                                                                   [100%]
6 passed in 0.61s
```

Command: `cd backend && ../.venv/bin/python -m pytest ai/tests/test_pulse_heartbeat.py -q --maxfail=5 --disable-warnings`

```text
Verification gate: backend
✓ django check
✓ no missing migrations
GATE PASSED
```

## 8. VPS deploy handoff (systemd — not run on this host)

This WSL/dev machine has no instance containers + no root systemd install for Carbon. Production handoff is unchanged:

```bash
# On VPS as root, once per instance:
sudo bash deploy/instance/setup-pulse-heartbeat.sh nibras

# Creates:
#   /etc/systemd/system/nibras-pulse-heartbeat.service
#   /etc/systemd/system/nibras-pulse-heartbeat.timer   # daily 02:00 UTC, Persistent=true
#
# Service runs inside container:
#   docker exec nibras-backend python manage.py ensure_pulse_instance
#   docker exec nibras-backend python manage.py run_pulse_maintenance

systemctl status nibras-pulse-heartbeat.timer
systemctl start nibras-pulse-heartbeat.service   # trigger now
journalctl -u nibras-pulse-heartbeat -n 50
```

**Local compose proof of the same command path:** `pulse-heartbeat` service in root `docker-compose.yml` + the manual `run_pulse_maintenance` evidence above.
