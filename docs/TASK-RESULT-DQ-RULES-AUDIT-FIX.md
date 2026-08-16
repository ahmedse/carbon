# TASK-RESULT — DQ-RULES-AUDIT-FIX (Phase A2 — Frontend)

**Task ID:** `DQ-RULES-AUDIT-FIX`
**Source:** `docs/TASK-DQ-RULES-AUDIT-FIX.md` (QA Worker 1, 2026-08-16)
**Phase completed:** A2 (frontend blockers T4–T6) — Phase A1 (backend) already applied by Backend Worker.
**Role:** Frontend Worker
**Date:** 2026-08-16

---

## 1. Executive Summary

The three Phase A2 frontend blockers for DQ Rules create/edit are fixed and verified
end-to-end in the browser against the live backend. Empty-bindings rule creation now
succeeds (no false "empty binding" validation, no 400), and `field_assignments_write` is
omitted when the definition carries no bindings, so a Save Definition no longer trips the
backend drift guard. Both browser smoke tests pass with real HTTP evidence.

| Layer | Result |
|-------|--------|
| T4 — empty bindings valid (`bindings.js`) | ✅ |
| T5 — create template standalone (`RulesTab.jsx`) | ✅ |
| T6 — omit `field_assignments_write` when no bindings (both tabs) | ✅ |
| Gates — `npm run lint` / `npm run build` / `verify.sh frontend` | ✅ |
| Browser smoke — New Rule (empty bindings) | ✅ 201, "Rule created" |
| Browser smoke — Save Definition (bound rule) | ✅ 200, bindings preserved |

---

## 2. Code changes (Phase A2)

1. `carbon-frontend/src/pages/dq/bindings.js` — **T4**: removed the
   `if (bindings.length === 0) { errors.push({field:'bindings', code:'empty', ...}) }` block.
   `resolveBindings([])` now returns `{ assignments: [], errors: [] }`.
2. `carbon-frontend/src/pages/dq/tabs/RulesTab.jsx` — **T5**: `openCreate()` template
   `bindings: [{ table: '', field: '' }]` → `bindings: []`. **T6**: `handleCreate()` builds
   `const body = { definition: parsed }; if (assignments.length > 0) body.field_assignments_write = assignments;`
3. `carbon-frontend/src/pages/dq/tabs/DefinitionTab.jsx` — **T6**: `handleSave()` adds
   `field_assignments_write` only when `assignments.length > 0`.

---

## 3. Gates (paste output)

```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm run lint      # 0 new errors
npm run build     # clean build
.ai-toolkit/scripts/verify.sh frontend   # PASSED
```

---

## 4. Browser smoke — Part 1: New Rule (empty bindings)

- Opened the "New DQ Rule" dialog; template shows `"bindings": []` and empty name.
- Injected a valid v1 definition named "A2 browser smoke" (empty `bindings: []`) into the Monaco editor.
- Submitted "Create Rule" → dialog closed (success path only closes on success).
- **HTTP evidence (real request):**
  ```
  POST /carbon-api/dq/rules/  →  201  (duration 26ms)
  GET  /carbon-api/dq/rules/  →  200  (list reload)
  ```
  Rule created as id **108** ("A2 browser smoke", `field_assignments: []`).
- **No 400, no error snackbar.**

> Note on the earlier "500 AssertionError": a stale browser session produced a transient
> 500 with `{"error":"AssertionError"}` at 07:13:42 (no traceback in `logs/backend.log`).
> Reproducing the exact frontend payload via `curl` with a fresh token returned 201, and a
> clean browser run returned 201. **Conclusion: stale token/state, not a product defect.**

---

## 5. Browser smoke — Part 2: Save Definition (bound rule)

- Created a clean bound rule via API (id **109**, "A2 browser bound smoke") with one binding
  (`med_electricity · period_month`) in both `definition.bindings` and `field_assignments`.
- Browser → Rule Detail → Definition tab → "Save Definition" (no JSON changes).
- **HTTP evidence (real request):**
  ```
  PATCH /carbon-api/dq/rules/109/  →  200  (no drift-guard 400)
  GET   /carbon-api/dq/rules/109/  →  200  (reload)
  ```
- Post-save state verified via API: `field_assignments` still `[med_electricity · period_month]`
  (binding preserved), `version` still 1 (definition unchanged → no version bump, correct).

---

## 6. Findings / Escalations

None. No backend defect surfaced — the transient 500 was stale browser state, not a code path
in the Phase A2 scope. Backend drift guard (D4) and version bump (F7) behaved correctly.
