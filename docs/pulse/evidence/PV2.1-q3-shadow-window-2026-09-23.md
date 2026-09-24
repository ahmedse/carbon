# Q3 understand shadow window (ops note)

**Flag:** `PULSE_UNDERSTAND=shadow` (not default; default stays `legacy`).

**Behavior**
- Runs one `emit_decision` understanding call per eligible turn.
- Logs `[understand-shadow] legacy=… v21=… agree=… ops=…`.
- Does **not** act on the Decision — legacy Intent→Draft spine answers the user.
- Flip to `v21` only after ≥5 days of shadow with high agreement and G6 ≥ 0.95 offline (already 1.0).

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

**Not started:** live 5-day window (needs STACK-HOLD + running stack). Code path is ready.
