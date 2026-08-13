# TASK-RESULTS — Pulse Vendor Frontend Phase B

**Status:** ✅ COMPLETE — all 6 gates green
**Date:** 2026
**Scope:** Replace the 14 `PulseModulePlaceholder` panels in the ai-admin studio with real, read-only, grounded panels backed by the 49 ai models. No new models, no migrations, no writes.

---

## 1. Files Created

### Backend (read-only layer, mounted under `/carbon-api/ai/pulse/`)
| File | Purpose |
|------|---------|
| `backend/ai/observability_api.py` | `PANEL_REGISTRY` (13 keys → model lists), `PANEL_LABELS`, `_make_serializer` factory (secret-field exclusion), `_redact_secrets` (recursive JSON redaction), `PulseInventoryView`, `PulseDataView`, `PulseArchetypesView` |
| `backend/ai/tests/test_observability_api.py` | 7 tests: auth-required, inventory completeness (13 panels), unknown-panel 404, logs merge+`_type` tag, `host_api_token` + nested JSON token redaction, archetypes bundle listing, read-only (POST/PUT/DELETE → 405) |

### Frontend
| File | Purpose |
|------|---------|
| `carbon-frontend/src/api/aiPulse.js` | `getPulseInventory(token)`, `getPulseData(token, key)`, `getPulseArchetypes(token)` via apiFetch, base `ai/pulse/` |
| `carbon-frontend/src/pages/admin/ai/PulseDataPanel.jsx` | Generic read-only panel (title/description/dataKey/emptyHint), scope column (`app_identifier · org · user · visibility`), `_type` chip, defensive cell rendering, count chip, offline/empty/loading states, CarbonDataGrid |
| `carbon-frontend/src/pages/admin/ai/PulseArchetypesPanel.jsx` | Archetypes bundle listing (name/kind columns) |
| 13 wrapper panels under `carbon-frontend/src/pages/admin/ai/` | `KnowledgeBasePanel`, `MemoryPanel`, `KnowledgeGraphPanel`, `AgentsPanel`, `McpServersPanel`, `ToolsPanel`, `SkillsPanel`, `PromptsPanel`, `FeedbackPanel`, `LearningJobsPanel`, `MonitoringPanel`, `AuditPanel`, `AILogsPanel` — each renders `<PulseDataPanel>` with the spec §2.4 title/dataKey/emptyHint |

## 2. Files Modified

| File | Change |
|------|--------|
| `backend/ai/ops_urls.py` | Added 3 paths (existing 3 untouched): `inventory/`, `data/<str:key>/`, `archetypes/` |
| `carbon-frontend/src/App.jsx` | Replaced `PulseModulePlaceholder` lazy import + 14 placeholder routes with 14 real panel routes (incl. `/admin/ai/archetypes`) |

## 3. Files Deleted
| File | Reason |
|------|--------|
| `carbon-frontend/src/pages/admin/ai/PulseModulePlaceholder.jsx` | No longer referenced anywhere after the App.jsx changes; spec allows worker's choice to delete |

## 4. Gate Results

| # | Gate | Command | Result |
|---|------|---------|--------|
| 1 | Django check | `python manage.py check` | ✅ "System check identified no issues (0 silenced)." |
| 2 | Migrations dry-run | `python manage.py makemigrations --check --dry-run` | ✅ "No changes detected" |
| 3 | Backend tests | `python -m pytest ai/tests -q` | ✅ **125 passed** in 3.77s (118 baseline + 7 new) |
| 4 | Backend verify | `bash ./.ai-toolkit/scripts/verify.sh backend` | ✅ GATE PASSED |
| 5 | Frontend build | `npm run build` | ✅ built in 11.41s (chunk-size warning only, pre-existing) |
| 6 | Frontend verify | `bash ./.ai-toolkit/scripts/verify.sh frontend` | ✅ GATE PASSED (lint ✓, build ✓) |
| + | Anti-patterns | `bash ./.ai-toolkit/scripts/verify.sh antipatterns` | ✅ GATE PASSED (warnings only in pre-existing untouched files: ForgotPasswordPage/ResetPasswordPage raw fetch, 28 legacy `print()` calls) |

## 5. Deviations from Spec

1. **`_make_serializer` factory (spec §1.1) — behavior-identical rewrite.**
   The spec's literal code sets **both** `fields="__all__"` **and** `exclude=...` in `Meta`. This DRF version raises
   `AssertionError: Cannot set both 'fields' and 'exclude' options on serializer <Model>Serializer.`
   (Triggered by every model with ≥1 secret-named field, e.g. `Instance.host_api_token`, `PulseUser.password_hash`, `RunStep.confirmation_token`.)
   **Fix:** set `fields="__all__"` only when nothing is excluded; otherwise set `exclude` alone (DRF treats exclude-only as "all fields minus excluded" — identical output). Security behavior unchanged: `host_api_token` and all `token|secret|password|api_key`-named fields are still excluded; nested dicts/lists still redacted via `_redact_secrets`.
   A code comment documents this.

2. **Wrapper panels include a `description` prop** (spec §2.4 table lists title/dataKey/emptyHint only; `description` is a declared prop of `PulseDataPanel`). Additions are cosmetic, permitted, and improve the empty/loading states. No spec text was contradicted.

3. **`PulseModulePlaceholder.jsx` deleted** rather than left in place (spec explicitly allows either). Verified unreferenced before deletion.

## 6. Compliance Notes

- ✅ Read-only: no writes anywhere; tests assert POST/PUT/DELETE → 405.
- ✅ No new models, no migrations (gate 2 confirms "No changes detected").
- ✅ Secrets never exposed: serializer exclusion + recursive JSON redaction; test asserts `"host_api_token" not in row` and secret values absent from serialized JSON.
- ✅ `apiFetch` only (no raw fetch), theme tokens only, `PageContainer` + `useDocumentTitle`, CarbonDataGrid.
- ✅ `PulseModulePlaceholder` no longer referenced anywhere in `src/`.
- ✅ Not committed (worker hands off to Master Architect).
