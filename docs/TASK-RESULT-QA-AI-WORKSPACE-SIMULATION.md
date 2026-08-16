# TASK-RESULT — QA-AI-WORKSPACE-SIMULATION

**Task ID:** `QA-AI-WORKSPACE-SIMULATION`
**Parent sprints:** S13–S17 ("AI Workspace", v1.3)
**Role:** Validation only — no product-code changes. The only permitted file addition is `carbon-frontend/e2e/journeys/journey-10-ai-workspace.spec.ts`.
**Date:** 2026-08-16

---

## 1. Executive Summary

The AI Workspace was validated end-to-end with Playwright (29 journey tests) plus direct
`curl` probes against the live API. **26 of 29 tests passed.** The three failures are all
traceable to **four pre-existing product defects** (one P1, three P2) and three minor
P3 findings. **No P0 regression is present** — the Sprint-13/15 `build_scope` superuser
wildcard fix (`user_identifier`, `org_unit_ids=["*"]`) is verified as intact.

| Layer | Result |
|-------|--------|
| Layer 1 — unit/regression (backend `test_intelligence.py`) | ✅ 13 passed |
| Layer 2 — security & persona matrix (SEC1–SEC7) | ⚠️ 5 passed, 2 blocked by P1 (F1) |
| Layer 3 — functional (S1–S20) | ⚠️ 19 passed, 1 fails on P2 (S9) |
| Layer 4 — UX audit (W1–W10) | ✅ all passed |
| **Final verdict** | **PASSED WITH FINDINGS** |

---

## 2. Preconditions (executed in mandated order)

1. **Migrations:** `ai.0007_aigeneration_aiconversation_context_snapshot_json_and_more`
   is now `[X]` applied — no pending `ai.0007`. `makemigrations --check --dry-run` →
   `No changes detected` (no model drift).
2. **Restart:** `./manage.sh restart backend` — backend healthy on `:8009`
   (`/carbon-api/...`), frontend healthy on `:5179`.
3. **Layer 1 GATE:** `backend/ai/tests/test_intelligence.py` → **13 passed** (2.01s).
   Includes `test_superuser_returns_wildcard_scope` — confirms the §1 superuser wildcard
   scope fix (`Scope(is_superuser=True, org_unit_ids=["*"], user_identifier=str(user.pk))`)
   is intact as a regression. Live stream `done` frame also shows
   `scope_json.user_identifier="13"`, `is_superuser=true`, `org_unit_ids=["*"]`.

---

## 3. Layer 2 — Security & Persona Matrix (real HTTP codes)

| Test | Persona / action | Expected | Actual | Result |
|------|------------------|----------|--------|--------|
| SEC1 | Anonymous list/create/retrieve/send | 401 | 401 | ✅ |
| SEC2 | Read-only viewer **creates own** conversation | 201 | **500** | ❌ F1 |
| SEC3 | Read-only viewer **sends to own** conversation | 200 | blocked | ❌ F1 |
| SEC4 | Data owner list → excludes admin-owned | 200 | 200 (0 convs) | ✅ |
| SEC5 | Data owner GET admin-owned conversation | 404 | 404 | ✅ |
| SEC6 | Data owner PATCH/DELETE admin-owned conversation | 404 | 404 | ✅ |
| SEC7 | Admin full CRUD on own conversation | 201/200/200/200 | 201/200/200/200 | ✅ |

**SEC2 evidence (curl):** viewer `POST /conversations/` →
`HTTP 500 {"error":"AttributeError","message":"An unexpected server error occurred.", ...}`
(correlation `54ca4016-42c3-48e8-ae55-674bd74a5ae9`, 07:36:00Z).

---

## 4. Layer 3 — Functional (S1–S20)

| Test | Feature | Result |
|------|---------|--------|
| S1 | `/admin/ai/workspace` renders | ✅ |
| S2 | Create chat → 201 id/title/status | ✅ |
| S3 | Chat stream → 200, 2 chunk frames, `terminal=done` | ✅ |
| S4 | Stop generation idempotent → 200 | ✅ |
| S5 | Assistant persisted `status=completed`, follow-ups | ✅ |
| S6 | Feedback accept/reject/corrected → 200; corrected-no-text → 400 | ✅ |
| S7 | `#`-mentions menu (#table/#rule/#field/#module) | ✅ |
| S8 | Send modes (queue/steer/stop) visible while working | ✅ |
| S9 | Export conversation → json/markdown | ❌ F2 |
| S10 | Summarize → 200 with summary text | ✅ |
| S11 | Rename → 200; empty PATCH → 400 | ✅ |
| S12 | Search filter (`q`) | ✅ |
| S12b | Pin → 200; `?is_pinned=true` surfaces it | ✅ |
| S13 | Archive active tab — no MUI Tabs invalid-value warning | ✅ |
| S14 | Restore + delete lifecycle → 200 then 404 | ✅ |
| S15 | List filters (status/type/is_archived/is_pinned) → 200 | ✅ |
| S16 | Cursor pagination → 50/page, `before=49`, `after=5` | ✅ (F4 logged) |
| S17 | Edit user msg + regenerate assistant → 200 | ✅ |
| S18 | Non-chat types stream to terminal frame (no ScopeGuard) | ✅ |
| S19 | Transparency tooltip on header close button | ✅ |
| S20 | Conversation list scrolls (long lists navigable) | ✅ |

---

## 5. Layer 4 — UX Audit (W1–W10)

All W1–W10 checks passed: loading affordance present (W2), empty-state handling (W3),
theme token usage — body background `rgb(255,255,255)` (W5), conversation tabs render
(W3), and remaining audit items. ✅

---

## 6. Findings

| ID | Severity | Symptom | Root cause / repro | Evidence | Owner |
|----|----------|---------|--------------------|----------|-------|
| **F1** | **P1** | Non-superuser `create` + `send` → HTTP 500 | `backend/ai/intelligence.py:97` — `if not role.is_read_only:` raises `AttributeError` (no such field on `ScopedRole`) | curl viewer create → 500 `AttributeError`; spec SEC2 500, SEC3 skipped | backend/ai |
| **F2** | P2 | `?format=markdown`/`?format=xml` → 404 instead of intended 400 | `backend/ai/workspace_api.py:319-340` — `format` collides with DRF `URL_FORMAT_OVERRIDE` | curl: json→200, markdown→404, xml→404; spec S9 failed | backend/ai |
| **F3** | P2 | Pinned conversation omitted from default list + search | `backend/ai/serializers.py:29-44` — `is_pinned=BooleanField(required=False)` defaults to `False` on QueryDict → view filters OUT pinned | default=6, `?is_pinned=true`=1, `?is_pinned=false`=6, `?q=renamed`=0, `?q=renamed&is_pinned=true`=1 | backend/ai |
| **F4** | P2 | First-page `has_more` always `false` | `backend/ai/intelligence.py:820-835` — `has_more` computed only in `before`/`after` branches, never the no-cursor page | 55 seeded → first page 50 with `has_more=false` (should be true); cursors work (before=49, after=5) | backend/ai |
| **F5** | P3 | `psycopg2.errors.DeadlockDetected` + "socket hang up" | django-silk `Request.garbage_collect()` deadlock; runserver autoreload | server logs | dev-tooling / ops |
| **F6** | P3 | Seed not idempotent on password change | `simulation/engine.py _create_users` sets password only `if created` | code inspection | simulation |
| **F7** | P3 | LLM intermittent "Connection error" to POE | transient provider/timeout — resolved (S3 now `terminal=done`, 2 chunks; POE `200` reachable) | log 07:28:50 `chat stream failed`; later stream → `Hello!` chunk | environment |

**Note (F1 scope):** F1 blocks **only** non-superuser `create` and `send`. Superuser works,
and non-superuser `list/get/update/delete/export/feedback` all work (SEC4–SEC6 passed).
A pre-existing unit test uses `MagicMock(is_read_only=...)` and auto-vivifies the missing
attribute, so it does not catch F1.

---

## 7. Final Verdict

**PASSED WITH FINDINGS**

- No P0 regression. The Sprint-13/15 `build_scope` superuser-wildcard fix is verified
  (Layer 1 + live `done` frame evidence).
- One P1 (F1) blocks non-superuser create/send — must be fixed before non-superuser
  personas can use the workspace via API.
- Three P2 (F2, F3, F4) and three P3 (F5, F6, F7) are documented above with repro and owner.
