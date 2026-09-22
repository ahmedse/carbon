# Evidence — Chat staged leave · Agent banner (E-031) · 2026-09-22

## Observation

| Field | Value |
|-------|--------|
| Actor | `emp_1067` |
| Mode | Pulse **Chat** |
| Utterance | `اريد اجازة, ليوم واحد غدا, عادي.` |
| Grounding | Pass — `annual`, `2026-09-23`, 1 day |
| Tool | `call_host_api` staged (Sources: `call_host_api · 0 rows`) |
| UI | Banner: *Agent mode is OFF — switch to Agent to confirm this action* |
| Confirm/Decline | Absent in Chat |

## Verdict

| Layer | Pass/Fail | Note |
|-------|-----------|------|
| Synonym عادي→annual | Pass | MDM / write_slots |
| Date غدا→2026-09-23 | Pass | Clock grounding |
| No deflection prose | Pass | Did not refuse “elsewhere” |
| **G2 Chat contract** | **Fail** | Chat must have **zero** `pending_exec` |
| Agent confirm gate UI | Pass (correct) | Non-memory host confirms are Agent-only |
| Bandaid “show Confirm in Chat” | **Rejected** | ADR-0046 / RULE_35 |

**Root cause:** G2 drift — Chat called a mutation tool. The banner is the frontend
honoring ADR-0014 after the backend already violated Chat’s “no side effects” promise.

## Proper paths (do these next in QA)

1. **My app** — `/my/leave` submit → Correspondence → `emp_1712` `/team` Approve  
2. **Agent** — switch to Agent → plan/run `leave.request.lifecycle` → Run consent → host  

## Toolkit updates shipped (no product code change)

- ADR-0046  
- RULE_35 · security RULE 12  
- PB-62  
- `.cursor/rules/pulse-chat-agent-mode-contract.mdc`  
- ADR-0014 cross-link  

## Follow-up Pulse seat phase (not done here)

Stop Chat from staging host mutations; honest handoff copy; G2 regression fixture.
**Not** a Chat Confirm flip.
