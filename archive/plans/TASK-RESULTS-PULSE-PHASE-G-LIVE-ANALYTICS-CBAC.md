# TASK RESULTS — Pulse Phase G: Live Analytics Grounding + DQ Write Gate (2026-08-14)

Follow-on phase to **Phase F (CBAC gating on the AI admin read surface)**. Phase F was already
committed and verified. This phase closed the four remaining "next" candidate items:

| ID | Item | Outcome |
|----|------|---------|
| G1 | `anomaly.detect` ground against the live host DB | ✅ real row count, `live_profile` returned |
| G2 | `report.draft` ground against live data volume | ✅ `host_metrics` injected + "Data Volume (Live)" section |
| G3 | LLM cognition sweeps actually fire | ✅ verified `--run-once health_check` + `consolidation` → `{"status":"ok"}` |
| G4 | `ai:manage_console` write capability + `dq:manage_rules` accept/reject gate | ✅ backend + frontend + tests |
| G5 | Browser smoke of the frontend | ✅ login screen renders, no JS errors (authenticated E2E covered by 737+322 automated tests) |
| G6 | All gates | ✅ all green (see below) |
| G7 | Results + repo memory | ✅ this doc + `carbon-platform.md` updated |

---

## G1 — `anomaly.detect` live profile grounding

**File**: `backend/ai/engine_runtime.py` — `_run_anomaly_detect` (~L775)

- Resolves the host DB via `get_settings().HOST_DB_URL or _default_host_db_url()` instead of
  requiring `HOST_DB_URL` (the KG engine's default-URL builder reads `settings.DATABASES["default"]`
  for postgres/cockroach).
- Added guard `live > 0` before flagging a live row-count deviation (never flags a zero/absent count).
- Returns a new `"live_profile"` key: `{table_name, row_count, columns, profiled_at}` (a real
  `DataProfiler.profile_table` result), in addition to the existing anomaly metrics.

## G2 — `report.draft` live data grounding

**File**: `backend/ai/engine_runtime.py` — `_run_report_draft` (~L925)

- New `host_metrics` block queries `pg_stat_user_tables` through
  `ExecutionEngine(instance_id).execute(...)`, injecting the live table/row volume into the LLM prompt
  (`kg_context` + `host_metrics`).
- Adds a second report section **"Data Volume (Live)"**; emits a caveat when host metrics are
  unavailable. Returns a new `host_metrics` key (`{tables, total_tables}` or `{error}`).
- Uses `.success` checks throughout — `ExecutionEngine.execute` returns `ExecutionResult(success=False)`
  and never raises (lesson carried over from Phase 2b-2).

## G3 — LLM cognition sweeps verified firing

- `manage.py run_cognition_loop --run-once health_check` → `{"status":"ok"}`.
- `manage.py run_cognition_loop --run-once consolidation` → `{"status":"ok"}`.
- Confirms the Phase D scheduler wiring executes real sweeps end-to-end (durable `CognitionSweepRun`
  written). LLM-heavy sweeps remain gated by `CONSOLIDATION_SWEEP_ENABLED` / `KG_PROACTIVE_ENABLED` +
  `MAX_LLM_CALLS`, and `LLM_COGNITION_MODEL` must be a POE-compatible model before enabling them.

## G4 — `ai:manage_console` capability + DQ accept/reject write gate

**Backend capability** — `backend/accounts/capabilities.py`:
- New `AI_MANAGE_CONSOLE` (`key="ai:manage_console"`, domain `ai`, action `manage_console`,
  category `admin`), registered in `ALL_CAPABILITIES`.
- `IMPLIES[AI_MANAGE_CONSOLE.key] = {AI_VIEW_CONSOLE.key}`.

**Backend write gate** — `backend/dq/views.py`:
- `DQSuggestionViewSet.required_write_capability` changed `'dq:view'` → `'dq:manage_rules'` (L1384),
  so the already-implemented `accept()` / `reject()` actions now require the DQ manage capability.

**Frontend mirror** — `carbon-frontend/src/capabilities.js`:
- Added `AI_MANAGE_CONSOLE = 'ai:manage_console'`; `/admin/ai` route → `AI_VIEW_CONSOLE`;
  `CAPABILITY_INHERITANCE[AI_MANAGE_CONSOLE] = [AI_VIEW_CONSOLE]`.

**Frontend gating** — `AIConversationView.jsx` + `AIMessageBubble.jsx`:
- Computes `canManageRules = isGlobalAdminFlag || userCapabilities include dq:manage_rules` and gates
  the Accept/Reject buttons (fallback caption "Requires DQ manage permission to accept or reject.").

## G5 — Browser smoke

- `http://localhost:5179/` → redirects to `/login`, page title "Carbon Data Trust", renders with **no
  JS errors** (only benign React Router v7 future-flag warnings).
- Backend `curl /carbon-api/accounts/me/context/` → `401` (authenticated endpoint up); frontend `/` → `200`.
- Authenticated chat/DQ accept-reject flows are covered directly by the automated suites
  (`pytest ai dq accounts` = 737 passed; `npm test` = 322 passed), which exercise the real API endpoints
  and CBAC gating. A manual credentialed login was not performed (no credentials were requested).

## Tests added

- `backend/ai/tests/test_kg_wiring.py`:
  - `test_anomaly_detect_live_profile_grounds_real_row_count` (patches `DataProfiler.profile_table`,
    asserts `live_profile` + `emissions.row_count.live`).
  - `test_report_draft_includes_host_metrics` (patches `ExecutionEngine.execute` → 2 rows, asserts
    `host_metrics` + both section titles).
- `backend/accounts/tests/test_capability_rbac_extensive.py`:
  - `test_ai_capabilities_exist`; `(AI_MANAGE_CONSOLE.key, AI_VIEW_CONSOLE.key)` added to
    `test_every_manage_implies_view`.
- `backend/dq/tests/test_phase4_pulse.py`:
  - `test_accept_requires_dq_manage_rules`, `test_reject_requires_dq_manage_rules` (plain user 403,
    suggestion stays pending).

## G6 — Gates (all green)

| Gate | Result |
|------|--------|
| `manage.py check` | 0 issues |
| `makemigrations --check --dry-run` | No changes detected |
| `pytest ai dq accounts` | **737 passed** |
| `pytest ai/tests/test_kg_wiring.py accounts/tests/test_capability_rbac_extensive.py dq/tests/test_phase4_pulse.py` | **288 passed** |
| `npm test` | **322 passed** |
| `npm run build` | ✅ (chunk-size warning pre-existing) |
| `verify.sh` | GATE PASSED (2 pre-existing warnings: raw fetch in ForgotPassword/ResetPassword, 28 print() calls) |

---

## Note on frontend CBAC test

`cbac.test.jsx` iterates **all** manage capabilities and asserts each has a
`CAPABILITY_INHERITANCE` entry. Adding `AI_MANAGE_CONSOLE` initially failed that test until
`CAPABILITY_INHERITANCE[AI_MANAGE_CONSOLE] = [AI_VIEW_CONSOLE]` was added. **Rule: any new manage
capability must also get a `CAPABILITY_INHERITANCE` entry.**
