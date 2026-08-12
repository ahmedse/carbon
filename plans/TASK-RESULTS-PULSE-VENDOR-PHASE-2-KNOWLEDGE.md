# TASK-RESULTS — Pulse Vendoring Phase 2: Migrate System-of-Intelligence Modules

**Completed:** 2026-08-12
**Status:** ✅ ALL GATES PASS
**Role:** Backend Worker (continuing R5 after R1–R4 landed in prior windows)

---

## Scope of this window — R5: In-process adapter (retire HTTP path)

Per the locked spec `plans/TASKS-PULSE-VENDOR-PHASE-2-KNOWLEDGE.md` ruling:

> Rewrite `backend/ai/providers/pulse.py` so `PulseProvider` calls the in-hand engine
> **in-process** — no HTTP. Remove `AI_PROVIDER_CLASS` runtime swapping. Delete
> `providers/_http.py` once no tests reference them.

R1–R4 (49 Django models in `backend/ai/models/`, `Store` interface, `AI_STORE_BACKEND`,
CBAC) were completed in prior windows. This window **completed the R5 retirement**:
deleted the HTTP transport, migrated every affected test off `ai.providers._http.requests.*`,
and fixed one missed production call site.

---

## Files Deleted

| File | Reason |
|------|--------|
| `backend/ai/providers/_http.py` | Retired HTTP transport (no longer referenced) |
| `backend/ai/tests/test_provider_http.py` | Tested the retired HTTP transport |

## Files Edited (production)

| File | Change |
|------|--------|
| `backend/ai/providers/pulse.py` | `PulseProvider` now dispatches in-process via `ai.engine_runtime.dispatch_task`/`list_modules` (no HTTP) |
| `backend/ai/intelligence.py` | `CarbonIntelligence` delegates to the in-process `PulseProvider`; removed `_get_provider`/`AI_PROVIDER_CLASS` swapping |
| `backend/ai/protocol.py` | Docstring updated — no runtime provider swapping (Phase 2) |
| `backend/dq/engine.py` | `_evaluate_nl_check` now instantiates `PulseProvider()` directly (removed `_get_provider` import — was a latent ImportError) |

## Files Edited (tests)

| File | Change |
|------|--------|
| `backend/ai/tests/test_provider_pulse.py` | Rewritten: patches `backend.ai.providers.pulse.dispatch_task`/`list_modules`; 9 task types + ABC conformance |
| `backend/ai/tests/test_intelligence.py` | Rewritten: patches `backend.ai.intelligence.dispatch_task`/`get_task`; removed `_get_provider` tests |
| `backend/dq/tests/test_phase3_jobs.py` | `ai.providers._http.requests.post/get` → `ai.intelligence.dispatch_task/get_task` |
| `backend/dq/tests/test_phase3_suggest.py` | Same seam migration; degradation via `pulse_unavailable` return dicts |
| `backend/dq/tests/test_phase4_pulse.py` | `requests.post/get` → `ai.intelligence.dispatch_task/get_task`; removed `import requests` |
| `backend/dq/tests/test_nl_check.py` | 8 patches → `ai.providers.pulse.dispatch_task` (engine path); 1 patch → `ai.intelligence.dispatch_task` (job path) |

---

## Gate Results (same shape as Phase 1)

| Gate | Command | Status |
|------|---------|--------|
| G1 | `manage.py check` → "no issues (0 silenced)" | ✅ |
| G2 | `manage.py makemigrations --check --dry-run` → "No changes detected" | ✅ |
| G3 | `pytest ai/tests -q` → 77 passed | ✅ |
| G4 | `bash ./.ai-toolkit/scripts/verify.sh backend` → GATE PASSED | ✅ |
| G5 (extra) | `pytest dq/tests -q` → 247 passed | ✅ |

---

## Residual scan

No remaining references in `backend/**/*.py` to:
`_http`, `providers._http`, `post_task`, `_get_provider`, `AI_PROVIDER_CLASS`,
`AI_PROVIDER_URL`, `AI_PROVIDER_API_KEY`.

Remaining `import requests` usages are legitimate and unrelated to the AI seam:
- `backend/accounts/services.py` — external auth service call
- `backend/_test_login.py` — manual login smoke script

`backend/config/settings.py` retains only `AI_STORE_BACKEND` (R2 bootstrap) — the
`AI_PROVIDER_CLASS` runtime-swapping block is gone.

---

## Key engineering note (seam-correct mocking)

`intelligence.py` and `pulse.py` bind `dispatch_task`/`get_task`/`list_modules` via
`from backend.ai.engine_runtime import …`, which copies the reference into the importing
module's namespace. Patching the **source** (`backend.ai.engine_runtime.dispatch_task`)
does **not** affect those modules — each module's **local name** must be patched:

- `backend.ai.providers.pulse.dispatch_task` / `list_modules` (and `ai.providers.pulse.*`)
- `backend.ai.intelligence.dispatch_task` / `get_task` (and `ai.intelligence.*`)

`engine_runtime.dispatch_task`/`get_task` are **fail-visible**: they return
`{"status": "pulse_unavailable", "error": {"code": "not_wired"}}` and never raise.
Degradation tests therefore mock **return values**, not `Timeout`/`ConnectionError`
side-effects.
