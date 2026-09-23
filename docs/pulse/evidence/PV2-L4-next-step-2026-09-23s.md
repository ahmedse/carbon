# PV2 L4 — next ESS step from state (2026-09-23s)

Not a soak night. Night **2026-09-23 stays FAIL**. Streak **0/5**.

## What L4 is

The chip already reported a started plan. Pulse did not name the next action unless the user asked "status of my request?" (C9). L4 is the verb.

| State | Next verb (Chat, 0 LLM) | Chip |
|---|---|---|
| handoff_ready / slots only | switch to Agent to submit | Submit · title |
| pending_approval | open Agent and Approve, then Run | Approve · title |
| approved | open Agent and Run | Run · title |
| paused | open Agent and confirm the waiting step | Confirm · title |
| completed / failed | no offer | — |

Chat still does not submit or Confirm a host write (ADR-0046). "Confirm" on the chip is the Agent step, not a Chat Confirm button.

## Triggers

- `what next` / `then what` / `ماذا بعد` / lone `ok`
- C9 status copy appends the same sentence
- Not a new ESS write, not a payroll recall

## Not claimed

- Official 6B night 2
- ADR-0047 Accepted
- Offers outside the three ESS journeys
