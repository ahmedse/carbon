# Chat QA — GOFSCO clarification-loop audit (2026-09-17)

**Seat:** Pulse · **Brand:** nibras · **Mode:** Chat (advisory)

## Symptom

User: “tell me more about gofsco” → “the company” → “data in the system”  
Chat replied three times with “What specifically…?” and never called tools.

## Oracle (data exists)

| Fact | Value |
|------|-------|
| OrgUnit root | `GOFSCO — Gas & Oil Field Services Company` (slug `gofsco`, code `GOFSCO`) |
| Active employees | **530** |
| Org units | **33** |

## Root cause

1. **IntentResolver short-circuit:** classifier returned `action=clarify` (conf≈0.70, no endpoint) for the tenant org name. Runner returned the clarifying question **before** draft/tools.
2. **Missing tenant-org grounding:** Chat prompt had ORG-NAME GUARD only on *synthesis* (after tools). Persona mentioned GOFSCO but Intent had no “whole organisation ≠ ambiguous entity” rule.
3. **topic_guard overreach (secondary):** Nibras `topic_guard` blocked `(list\|show\|get)…org.?units` as if Carbon MDM — org tree is in-scope for GOFSCO.

Not deterministic `clarify.py` (different copy). Not missing DB data.

## Fix

| Change | Path |
|--------|------|
| `tenant_org:` + company persona guidance | `instances/nibras/instance.yaml` (+ carbon AASTMT) |
| Prompt directive `_build_tenant_org_directive` | `ai/engine/llm/prompts.py` |
| Live root alias enrichment | `ai/engine_runtime.py` `_enrich_tenant_org` |
| Intent: tenant rule + `_apply_tenant_org_override` (clarify→answer → `analyze_employees`) | `ai/engine/cognition/turn/intent.py` |
| Pass `tenant_org` into IntentResolver | `runner.py` |
| Unblock org-unit list from topic_guard | `nibras/instance.yaml` |
| Tests | `test_tenant_org_directive.py`, `test_intent_resolver.py` |

## Proof

In-process `CarbonIntelligence.send_message` as `ahmed` (Chat):

- Intent: `action=answer top=analyze_employees conf=0.90` (was `clarify`)
- Tools: 2 completed; synthesis from tool results
- Answer includes **530** active employees + org-unit breakdown
- **No** “What specifically…?” loop

`pytest ai/tests/test_tenant_org_directive.py ai/tests/test_intent_resolver.py` → **34 passed**

## Grade

**PASS** — GOFSCO company / data-in-system Chat path grounded.

---

## Follow-on (same session): B5 compensation deny — **PASS**

See [`CHAT-B5-COMPENSATION-DENY-2026-09-17.md`](CHAT-B5-COMPENSATION-DENY-2026-09-17.md).

- Intent routes salary/compensation to `get_my_profile` / `get_employee` (not empty payslips)
- Empty payslips + missing capability → unauthorized; profile salary asks stamped deny
- Deterministic deny prose (no LLM “no salary data” mix)
- Live `emp_1001`: self + Abrar salary → `view_compensation` deny; **PASS**

