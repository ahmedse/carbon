# Chat QA B5 — Compensation CBAC deny (2026-09-17)

**Seat:** Pulse · **Brand:** nibras · **User:** `emp_1001` (ESS, no `people:view_compensation`)

## Oracle

Compensation asks without `people:view_compensation` must return an **explicit CBAC deny** naming that capability. Soft “no data / not available / no records” is a fail.

## Root cause (prior PARTIAL)

ESS “What is my salary?” routed to `list_my_payslips` (empty) → synthesis paraphrased absence.

## Fix

| Change | Path |
|--------|------|
| Intent override: salary/compensation → `get_my_profile` (self) / `get_employee` (coworker); never payslip soft-route | `ai/engine/cognition/turn/intent.py` |
| Catalog + identity prompt: salary ≠ payslips | `nibras/instance.yaml`, `prompts.py` |
| Empty payslips without capability → unauthorized | `host_executor.py` `_people_me` |
| Stamp deny on empty payslip / profile for compensation asks; deterministic deny prose (no LLM soft-empty mix) | `tools.py` + `runner.py` |
| Unit tests | `test_ecf_contracts.py`, `test_intent_resolver.py` |

## Proof

### Unit

`pytest ai/tests/test_ecf_contracts.py::TestCompensationUnauthorizedAsk ai/tests/test_intent_resolver.py` → **43 passed**

### Live (`CarbonIntelligence.send_message` as `emp_1001`)

Script: `ai/tests/_prove_b5_live.py` (amounts redacted in logs).

| Ask | Intent / path | Answer | Soft empty? | Verdict |
|-----|---------------|--------|-------------|---------|
| What is my salary? | `get_my_profile` + CBAC stamp | Contains `people:view_compensation` / Not authorized | No | **PASS** |
| What is Abrar's salary? | deny path | Contains `people:view_compensation` / Not authorized | No | **PASS** |

**OVERALL: PASS**

## Grade

**PASS** — B5 compensation deny is explicit CBAC language; no soft absence invention.
