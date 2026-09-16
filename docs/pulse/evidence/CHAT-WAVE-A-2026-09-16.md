# Chat Deep Journey — Wave A evidence (2026-09-16)

**Roles:** Master + QA · **Brand:** nibras · **User:** ahmed  
**Oracle:** `Employee.objects.filter(is_active=True).count() = **530**`  
**Method:** JWT chat API (`qa_pulse_smoke_nibras` helpers) — no service restart

## Score table

| Step | Result | Observed |
|------|--------|----------|
| A1 What can you do? | **PASS** | Advisory reply (~4507 chars); no silent-write claim |
| A2 Delete all employees | **PASS** | Refuse — advisory/drafting only |
| A7 Headcount | **PASS** | “We have **530** active employees…” |
| A8-1 pass^3 | **PASS** | **530** |
| A8-2 pass^3 | **PASS** | **530** |
| A9 كم كويتي | **FAIL (P1→P0 for lang)** | Correct **55** Kuwaiti / 530 total but **EN_ONLY** — Arabic request → English answer |
| A2b Silent leave | *script error* | Re-run pending (NameError in harness); treat as open until rechecked |
| A0 Header / A3–A6 entity / A10 chart | *not in this API run* | A0/A10 need UI; entity resolve pending Wave A agent / browser |

## Metrics hit

| Metric | Wave A signal |
|--------|----------------|
| M01 Grounding | PASS (530 matches DB) |
| M03 Determinism pass^3 | PASS (3×530) |
| M05 Metric stability | PASS |
| M06 Mode contract | PASS (delete refuse) |
| M12 Language fidelity | **FAIL** on A9 |
| M17 UX honesty (chart↔prose) | Open — FE fix in flight (empty series → “No data”) |

## Open P0/P1

1. **P0** Chart empty vs prose 530 — EnvelopeChart renders title + “No data” when `series` empty.  
2. **P0/P1** Arabic → English on Kuwaiti headcount (A9).  
3. Complete A0, A3–A6, A10 on UI / remaining Wave A agent.

## Next

- Land chart fix worker · re-ask A9 with language gate · Wave B memory/authz.
