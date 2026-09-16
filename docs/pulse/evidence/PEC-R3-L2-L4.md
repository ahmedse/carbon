# PEC-R3 / L2-L4 Evidence — 2026-09-16

**Seat:** Pulse  
**Stack:** user-owned `./manage.sh start` (agent did **not** restart services)

## PEC-R3 — AI suite debt

| Suite | Result |
|-------|--------|
| `test_ports` + `test_durable` + `test_chat_stream` + `test_web_search_tool` + `test_people_grounding` + `test_capability_list_api` | **104 passed** |

people_grounding: fixtures updated for ReferenceValue gender/nationality; host_executor FK label resolve (Pulse AI-side). Nibras COMMS `20260916-6` for people migration `0026` on live DBs.

## L2 — Security API (live)

| Check | Result |
|-------|--------|
| `GET /carbon-api/ai/catalog/capabilities/` anonymous | **401** |
| `GET /carbon-api/ai/catalog/capabilities/` JWT (superuser) | **200** `[]` |
| `GET /carbon-api/ai/catalog/skills/` JWT | **200** `[]` |
| Backend `/carbon-api/` anonymous | **401** |

Empty `[]` = no Capability/Skill rows in live nibras DB (API shape OK). Seed/sync is optional follow-up.

## L4 — UX (light)

| Check | Result |
|-------|--------|
| `GET http://localhost:5179/carbon/` | **200** |
| Playwright Console Capabilities journey | **NOT RUN** (deferred) |

## Verdict

- **PEC-R3:** DONE  
- **L2:** PASS (deny anon / allow JWT on catalog surfaces)  
- **L4:** PARTIAL (FE up; no browser journey this session)
