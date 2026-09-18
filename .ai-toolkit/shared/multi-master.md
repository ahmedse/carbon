# Multi-Master Coordination Protocol (BINDING)

**Read by:** Master Architect (every session, before Active focus)  
**Ops log:** `docs/ops/MASTERS-COMMS.md` (append-only)  
**Seats:** `.ai-toolkit/masters/seats.md`  
**Established:** 2026-09-16 — after a Pulse Master wrongly dispatched NSR.

---

## Why this exists

Multiple Master Architect sessions may run in parallel (e.g. **Pulse** vs **Nibras** vs **EduOS**).
`TASKS.md` alone is not enough: a row marked “MASTER PRIORITY” without an **Owner**
causes track theft. This protocol makes ownership hard law.

---

## Seats (Master identities)

| Seat ID | Owns (summary) | Must not touch |
|---------|----------------|----------------|
| `Pulse` | AI/Pulse, ECF, PEC residuals, `backend/ai/**`, Pulse docs/ops | NSR people/my/team thickening, GOFSCO staff product UI |
| `Nibras` | NSR, people/my/team/correspondence staff circuits | Pulse engine/host AI phases, ECF cutover; EduOS/GradeVance |
| `EduOS` | GradeVance, LCT/Rubric packs, EduOS brand (`docs/eduos/**`) | Nibras ERP tracks; Tectona Healthy product |
| `Catalog` | Data Trust platform — catalog/DQ/MDM/dataschema metadata plane | Pulse engine internals; Nibras staff UI; EduOS |

Full path map: `.ai-toolkit/masters/seats.md`.

---

## Activation (Master Architect — Step 0)

Before planning or dispatch:

1. Declare aloud: **`I am Master: <Seat ID>`** (Pulse, Nibras, or EduOS).
2. Read `.ai-toolkit/masters/seats.md`.
3. Read `TASKS.md` → **Active focus** → only rows where **Owner = your Seat**.
4. Read open items in `docs/ops/MASTERS-COMMS.md` addressed **TO: your Seat**.
5. Confirm: `Ready as Master Architect (<Seat>) for <PROJECT>.`

If the human did not name a seat, **ask once** before dispatching anything.

---

## Hard rules

1. **Never dispatch, implement, mark DONE, or rewrite specs** for a track you do not own.
2. **Never edit paths** listed under another seat’s exclusive trees (see seats.md), except:
   - Explicit **HANDOFF** ACK in MASTERS-COMMS, or
   - Human override in the current user message naming both seats.
3. Cross-seat need → append a **REQUEST** to MASTERS-COMMS; wait for **ACK** (or human).
4. Workers inherit the Master’s seat for the phase. A Pulse-dispatched worker must not
   receive NSR phases. Spec **DO NOT TOUCH** must name the other seat’s trees.
5. `TASKS.md` Active focus **must** include an **Owner** column. Missing Owner = do not dispatch.
6. **Shared local stack lease** (see below) — code ownership ≠ process ownership of `:8009`/`:5179`.

---

## Shared local stack lease (BINDING)

Dev stack ports (`BACKEND`/`FRONTEND` via `./manage.sh`, typically **:8009** / **:5179**) and Postgres used by that stack are **shared infrastructure**. Either seat may *use* them; neither may **kill/restart** without a lease.

### Rules

1. Before exclusive browser/API QA or long Pulse chat that needs a stable process, the seat posts COMMS:

```text
TYPE:INFO  Ask: STACK-HOLD <Seat> until <HH:MM offset or ISO> — reason
Paths: manage.sh, :8009, :5179
```

2. While a `STACK-HOLD` is open (until time / explicit `STACK-RELEASE` INFO):
   - Other seat **must not** run `./manage.sh start|restart|stop|killall|clean-ports`, `pkill` on `runserver`/Vite, or kill the lease-holder’s PID.
   - Need restart → `REQUEST` + wait `ACK` (or human override).
3. `./manage.sh start` **always kills** the existing backend first (playbook PB-50). Treat it as a lease violation if another seat holds `STACK-HOLD`.
4. Agent sandbox may false-negative `pg_isready` / TCP to localhost while host Postgres is fine (PB-50). Diagnose and restart only with host/`all` permissions; do not conclude “stack dead” from sandbox-only probes.
5. Request-level errors in the other seat’s code (e.g. Pulse chat 500s) are **not** a license to restart the process during a hold — file COMMS `INFO`/`REQUEST` instead.

### Release

```text
TYPE:INFO  Ask: STACK-RELEASE <Seat> — hold ended
```

Or hold expires at the stated time (whichever comes first). Human message overrides.

---

## MASTERS-COMMS format (append-only)

File: `docs/ops/MASTERS-COMMS.md`

```text
## [<ISO-8601 with offset>] FROM:<Seat> TO:<Seat|ALL> TYPE:<TYPE> ID:<YYYYMMDD-N>
Track: <phase or track id>
Ask: <one sentence>
Paths: <optional glob list>
Blockers: <none | text>
```

| TYPE | Meaning |
|------|---------|
| `REQUEST` | Need action/decision/audit from the other Master |
| `ACK` | Accept REQUEST; will act or decline with reason |
| `BLOCKED` | Cannot proceed; need human or other seat |
| `HANDOFF` | Transfer ownership of a path/phase (rare) |
| `DECISION` | Cross-seat decision recorded (pointer to ADR if needed) |
| `INFO` | FYI only; no action required |

**Not allowed:** status novels, worker chatter, full TASK-RESULTS dumps.
Status proof stays in `TASK-RESULTS.md`.

---

## Conflict resolution

1. Path ownership in `seats.md` wins over “priority” wording.
2. Open REQUEST without ACK → requesting Master must not implement.
3. Human message always overrides; record a `DECISION` entry afterward.

---

## Anti-patterns

- Dispatching “whatever is ACTIVE” without checking Owner.
- Editing `people/**` from a Pulse session “just to help.”
- Using chat memory instead of MASTERS-COMMS for cross-seat asks.
- Closing another seat’s TASK-RESULTS sections.
- `./manage.sh start` / killing `:8009` while another seat’s `STACK-HOLD` is open.
- Trusting agent-sandbox `pg_isready` as proof Postgres died (PB-50).
