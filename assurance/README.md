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
