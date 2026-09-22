# Profile-change apply — journey prove (2026-09-22)

**Seat:** Nibras · **Gap closed:** HTTP journey parity with leave e2e (submit → HR inbox → approve → Employee allowlist apply).

## Gate

```bash
cd backend && ../.venv/bin/python -m pytest \
  people/tests/test_profile_change_apply.py \
  people/tests/test_profile_change_journey_e2e.py \
  -q --maxfail=5 --disable-warnings -p no:cacheprovider
```

**Result:** 9 passed (6 unit/signal + 3 HTTP journey).

## Coverage

| Path | Prove |
|---|---|
| Allowlist extract / ignore unsafe keys | `test_profile_change_apply.py` |
| `fsm.approve` applies; reject/cancel no-op | `test_profile_change_apply.py` |
| `POST /people/me/profile-change/` → HR inbox → `POST …/approve/` → fields + chronicle/governance | `test_profile_change_journey_e2e.py` |
| HR reject via API does not mutate | `test_profile_change_journey_e2e.py` |
| Requester does not see own item in inbox | `test_profile_change_journey_e2e.py` |

## Non-goals

- Playwright UI for HR approve (Team inbox is manager-scoped; HR uses correspondence act). API journey is the leave-parity acceptance for apply.
- Expanding allowlist beyond NSR-5A personal/display fields.
