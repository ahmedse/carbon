# PV2-4B — Arbiter owns the recorded decision

**Date:** 2026-09-23  
**Human:** date gate waived (“don’t regard plan dates”). Five soak nights were not invented.

## What flipped

`PULSE_ARBITER` default is `on`. `_finalize_meter` records `Arbiter.decide(signals)` as `turn_decision`.

| Mode | Recorded decision |
|---|---|
| `on` (default) | Arbiter |
| `shadow` | caller label; comparison still logged |
| `legacy` | caller label; no comparison (kill switch) |

Precedence now includes the gates the runner actually fires: `chat_clarify` → clarify, `tools_executed` → tool_answer. A one-gate exit therefore agrees with the body that exit already built.

## What did not flip

The 17 early-return sites in `runner.py` still build and return that one gate’s response. They were not collapsed into a single executor. On the offline bank they agree with the Arbiter, so the recorded decision and the text match.

## Proof

Offline `--gate` after the default change: **96/96**, router 1.0, slot 1.0, llm p50/max 2/2, over_budget 0.  
`test_pv2_arbiter.py` 10 passed (conflict → refuse when on; legacy and shadow keep the caller label).

Raw: `docs/pulse/evidence/PV2-4B-offline.json`
