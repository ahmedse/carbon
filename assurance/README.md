# Assurance framework

Three layers. The first without the second is a scoreboard.

1. **Catalogue** — `domain_packs/<id>/assurance/rules/` plus `assurance/platform/`. What must be true, who owns it, what fails if it is false.
2. **Probes** — honesty, independent formula, signed conservation, static host binding. They read this repo. They do not import `people`, `emissions`, or Pulse.
3. **Host tests / CI / live stream** — Django and Playwright write the same JSONL event. Not wired yet.

A row is `passed` only when a probe or a host test wrote `passed` for that rule on the named commit. `conflict` cannot be passed. `stale` means the event is for another commit.

```bash
python -m assurance probe --pack nibras --commit <sha> --ledger /tmp/nibras.jsonl
python -m assurance report --pack nibras --commit <sha> --ledger /tmp/nibras.jsonl
```

See `docs/assurance/ASSURANCE-WORKBOARD-PLAN.md`.

## Excellence ladder (ADR-0051)

The same directories also hold the **ladder manifests** read by `backend/excellence`:

- `assurance/<tier>/ladder.yaml` — tier, subjects, tier-wide checks (`platform` is inherited by every tier).
- `assurance/<tier>/tracks/<track>.yaml` — one track (Pulse: `chat`, `agent`, `memory`, `packs`, `ops`).
- `domain_packs/<id>/assurance/ladder.yaml` — a domain app's tier.

Rules (`pack.yaml` + `rules/`) say *what must be true*; the ladder says *which level each subject has earned*
(L0 Unmanaged → L6 Excellent, one check at a time, minimum across dimensions). Events live in the
`carbon_excellence` database, never in the brand DB.

```bash
cd backend
python -m excellence.gauge --no-db --collect --only repo,pulse_gauge,observe   # dry run
python -m excellence.gauge --collect --write --gate                             # persist + ratchet
python -m excellence.gauge --gate --changed origin/main                         # CI: only touched subjects
python -m excellence.gauge --run pytest:accounts                                # one app
python -m excellence.gauge --run vitest:src/pages/admin/excellence/__tests__/ExcellencePages.test.jsx
bash .ai-toolkit/scripts/verify.sh excellence                                   # verify gate target
```

Admin UI: **Trust → Excellence** (`/admin/excellence`). Ladder | Rules. Measure runs collectors into the ledger.
