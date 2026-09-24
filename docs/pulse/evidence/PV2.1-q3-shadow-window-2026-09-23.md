# Q3 understand shadow window (ops note)

**Flag:** `PULSE_UNDERSTAND=shadow` (not default; default stays `legacy`).

**Behavior**
- Runs one `emit_decision` understanding call per eligible turn.
- Logs `[understand-shadow] legacy=… v21=… agree=… ops=…`.
- Does **not** act on the Decision — legacy Intent→Draft spine answers the user.
- Flip in an environment after an hours-scale agreement log (human, 2026-09-24: no 5-day wait) and G6 ≥ 0.95. Bank agreement 2026-09-24: baseline tier 121/122, the one split is g6-038 Arabic. v21-tier disagreement with the ladder is expected.

**Start (Master / STACK-HOLD only)**
```bash
# on the Pulse API process env — do not restart stack from agents without STACK-HOLD
export PULSE_UNDERSTAND=shadow
# leave PULSE_TOOL_CHOICE=off unless Q1 probe says otherwise
```

**Collect**
```bash
rg '\[understand-shadow\]' <pulse-api-log> | tee docs/pulse/evidence/PV2.1-shadow-raw.txt
# agreement rate = agree=True / total shadow lines
```

**Stop / flip**
- Abort: unset or `PULSE_UNDERSTAND=legacy`.
- Flip: `PULSE_UNDERSTAND=v21` only after Master review of the 5-day log.

**2026-09-24:** the 5-day calendar is waived. Hours measurement is `PV2.1-shadow-hours-2026-09-24.json`. Committed default stays `legacy`. This workstation's running API already has `PULSE_UNDERSTAND=v21` (process env). It was not restarted.
