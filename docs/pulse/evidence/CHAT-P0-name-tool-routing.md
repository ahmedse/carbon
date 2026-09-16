# CHAT P0 — Employee name resolve routes to search_knowledge

**Date:** 2026-09-16 · **Seat:** Master+QA (live IDE browser)  
**Brand:** nibras · **Fixture:** `employee_no=1416` / `full_name=Eslam Mohamed Elsayed Mohamed Ramadan`

## Symptom (pre-fix)

Natural-language employee **name** lookups in Chat returned “No matching employee” even when the person exists in People DB.

| Prompt style | Tool used | Result |
|--------------|-----------|--------|
| Arabic script full name (A3) | `search_knowledge · 0 rows` | Miss (calibrated) |
| Exact EN `full_name` (A4) | `search_knowledge · 0 rows` | Miss |
| `employee_no 1416` + “People live data” (A5) | `call_host_api · 1 rows` | **PASS** |
| Ambiguous “Mohammad” + live (A6) | `call_host_api · 100 rows · Truncated` | PARTIAL |

## Root cause

Chat planner allow-list (`_CHAT_STATIC_TOOLS`) never exposed `resolve_entity` / `aggregate_entity`. Prompts told the model to use ECF resolve; Chat dropped those tools → KG-only miss.

## Fix (landed)

| File | Change |
|------|--------|
| `backend/ai/engine/cognition/turn/runner.py` | `_chat_tool_allowlist()` adds `resolve_entity` + `aggregate_entity` when `ECF_ENABLED` |
| `backend/ai/adapter/carbon.py` | Capabilities catalog surfaces ECF spine tools when enabled |
| Tests | `test_plugins` + `test_gap8_capability_guard` assert ECF in Chat draft tools |

## Retest (post-fix · after QA quota bump 1M→5M)

| Channel | Result |
|---------|--------|
| API Chat | **PASS** — content **1416**; `tool_trace`: **`resolve_entity`** |
| UI browser | **PASS** — table Full Name / Employee Number **1416**; narration “Searching every record…” |

## Still open

- A3 Arabic-script name (DB `name_ar_*` = 0) needs transliteration/seed  
- A6 filter quality (truncated 100/530 dump)  
- AR→EN language drift  
- Presence “Pulse offline” while answering
