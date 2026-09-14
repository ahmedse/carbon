# TASKS-PHASE3.md — Second-Master Handoff (Phase 3: Registry + Pilot Process)

> **Owner:** Second Master (parallel to Gate 2 master).
> **Canonical spec:** `docs/pulse/PULSE-UNIFIED-REMEDIATION-PLAN.md` §Phase 3.
> **Created:** 2026-09-13 by Master Architect (Gate 2 master), at user request to parallelize.

---

## 0. Coordination Contract (binding for BOTH masters)

These rules prevent the two masters from stepping on each other. A violation on either
side wastes a full verification cycle (the test DB is single-tenant).

1. **One verifier at a time.** The test DB (`test_carbon_dev`, Postgres) is shared via
   `--reuse-db`. Only ONE master may run `pytest ai` / `pytest accounts` / `manage.py check`
   at any moment. Before verifying, check that the other master is not mid-verification.
   Gate 2 master owns `ai` app verification; Phase 3 master owns `accounts` + new `ai` model
   modules it introduces — but **still one process at a time**.
2. **Split tracking files.** Gate 2 master writes `TASKS.md` + `TASK-RESULTS.md`.
   Phase 3 master writes **only** `TASKS-PHASE3.md` + `TASK-RESULTS-PHASE3.md` (create the
   latter). Never edit the other master's files.
3. **`domain_packs/` is Gate 2 master's handoff.** The `domain_packs/carbon/*` + `DomainPack`
   port are produced by P2-08 (Gate 2). Phase 3 master **waits** for P2-08 before starting
   **P3-01 → P3-02 → P3-03** (the loader chain depends on `api_catalog.yaml` + the port).
   Phase 3 master may start **P3-05b** and **P3-06** immediately — they have no P2-08 dep.
4. **Fixed seam invariant (RULE_20 / ADR-0007).** `ai/engine/` MUST NOT import
   `ai.command_boundary`, `ai.command_boundary_factory`, `ai.protocol`, `ai.pdp`, or
   `ai.adapters`. Engine DELEGATES to the executor; the host (`host_executor.py`) builds the
   `Command` and calls `CommandBoundary.execute()`. Anything new must preserve this.
   Run `python3 .ai-toolkit/scripts/import-boundary-lint.py` after ANY engine edit.
5. **Separate session memory.** Phase 3 master keeps its own `/memories/session/` file
   (`pulse-phase3-progress.md`). Do not touch the Gate 2 session file.

**Shared invariants (do not re-derive):** Django 5.2 + DRF, Python 3.12, venv at
`/home/ahmed/ws/carbon/.venv/bin/python`; `pytest ai -q -m "not live"` (one app at a time,
NEVER full suite, NEVER xdist); SQLAlchemy is **uninstalled — do not reinstall**; CBAC via
`accounts/capabilities.py`; fail-closed/fail-visible everywhere; `manage.py check` must be clean.

---

## 1. Phase 3 — Full Task Map (for awareness; ownership marked)

| ID | Task | Dep | Owner | Status |
|----|------|-----|-------|--------|
| P3-01 | `Capability` model + loader from `api_catalog.yaml` | P2-08 | Gate 2 master (P2-08) → Phase 3 master | **DONE** |
| P3-02 | Pilot capability contracts (`dq.rule.validate/review/publish` + predicate) | P3-01, P0-10 | Phase 3 master | **DONE** |
| P3-03 | `ProcessDefinition` unified JSON Schema | P2-08 | Phase 3 master | **DONE** |
| P3-04 | Process-owner interview kit | P3-03 | Phase 3 master | **DONE** |
| P3-05a | Registry API (draft/diff/review/publish/deprecate + autonomy dial + kill switch) | P3-03 | Phase 3 master | **DONE** |
| **P3-05b** | **Roles: `process_owner`, `policy_owner`, `publisher`, `operator`, `auditor`; `AI_VIEW_CONSOLE` view-only** | **—** | **Phase 3 master** | **DONE** |
| P3-05c | Registry + Review Queue screens (`/admin/ai/*`) | P3-05a | Phase 3 master (frontend) | **DONE** |
| **P3-06** | **`ApprovalGrant` model + boundary stage; authorization/business-approval/consent separation** | **P2-06a** | **Phase 3 master** | **DONE** |
| P3-07a | Durable run machine (planned → … → cancelled states, idempotency key) | P3-03 | Phase 3 master | **DONE** |
| P3-07b | Workflow/activity split (deterministic orchestration + replayable journal) | P3-07a | Phase 3 master | **DONE** |
| P3-08 | Reconciliation worker (`outcome_unknown` read-back, escalate) | P3-07a | Phase 3 master | **DONE** |
| P3-09 | Human Task Inbox (durable approval tasks, SSE, writes `ApprovalGrant`) | P3-06 | Phase 3 master | **DONE** |
| P3-10 | `invoke_skill` reimplementation (resolve `process.id@version` → run → boundary) | P3-07, P2-06 | Phase 3 master | **DONE** |
| P3-11 | Cancellation vs compensate semantics | P3-07a | Phase 3 master | **DONE** |
| P3-12 | Pilot E2E (run via UI + Pulse; restart-survival / concurrent-edit invalidation / duplicate-submit / revoked-permission / self-approval) | all above | Phase 3 master (qa-validator) | **DONE** |

---

## 2. P3-05b — Roles + `AI_VIEW_CONSOLE` capability (S, no deps) — DONE

### Objective
Add five governance roles as CBAC capabilities, and a read-only `AI_VIEW_CONSOLE`
capability that grants *view only* to the AI console. Mirrors existing CBAC pattern in
`accounts/capabilities.py` (single source of truth).

### Files
- `backend/accounts/capabilities.py` — add capabilities to `CAPABILITY_REGISTRY` +
  map to groups in `GROUP_CAPABILITIES`.
- `backend/accounts/constants.py` — add role group-name constants (follow existing naming).
- `backend/ai/permissions.py` — create if absent: a permission class that uses
  `has_capability()` from `accounts.capabilities` for `AI_VIEW_CONSOLE` (SAFE_METHODS only).
- `backend/accounts/models.py` — no schema change to `ScopedRole` (it already binds
  `user × group × org_unit × module`). Verify `ScopedRole` works with the new groups as-is.

### Roles (capability keys, follow existing `"{domain}:{action}"` convention)
- `ai:process_owner` — own/approve a process definition.
- `ai:policy_owner` — own/approve PDP policies.
- `ai:publisher` — publish reviewed definitions/contracts (author ≠ publisher enforced later in P3-05a).
- `ai:operator` — run/observe/reconcile process instances.
- `ai:auditor` — read-only across registry + decisions + grants.
- `ai:view_console` — `AI_VIEW_CONSOLE`: **view only** (SAFE_METHODS); must not imply any write.

### Acceptance (verify with `pytest accounts -q -m "not live"` + `pytest ai -q -k "console|view_console" -m "not live"`)
- Test matrix **role × action**: each role resolves to its declared capabilities only.
- `AI_VIEW_CONSOLE` permits GET/HEAD/OPTIONS, **refuses** POST/PUT/PATCH/DELETE.
- No other file hardcodes these group names (grep `process_owner|policy_owner|publisher|operator|auditor|view_console`
  outside `capabilities.py`/`constants.py`/`permissions.py` returns only test + registry references).
- `import-boundary-lint` + `manage.py check` clean.

---

## 3. P3-06 — `ApprovalGrant` model + boundary stage (M, dep P2-06a done) — DONE

### Objective
Introduce a durable **business approval** concept, strictly separated from the other two
authorization concepts that already exist:

| Concept | Code location | Meaning |
|---------|---------------|---------|
| Authorization | `ai/pdp.py` (`PolicyDecisionPoint`) | *Can* the principal take this action? (default-deny) |
| **Business approval** | **`ai/models/approval.py` (NEW — this task)** | *Has a human approved this specific effect?* (grant) |
| User consent | `CommandBoundary` stage 7 (`consent`) / RULE_21 | *Is the human confirming right now?* (per-action) |

### Model spec — `ApprovalGrant` (vendored `app_label="ai"`, `AppScopeMixin` for CBAC)
Bound to every material dimension of the effect it authorizes. Any change in any of them
invalidates the grant:

- `id` (UUID pk, `generate_uuid`)
- `tenant` / `app_identifier` — tenant + app scope (inherit from `AppScopeMixin`).
- `process_instance` (FK → future `ProcessInstance`; nullable until P3-07a lands — use a
  generic `object_id`/`object_type` char pair for now so P3-06 is testable standalone).
- `process_version` (Text) — pins the definition version.
- `capability` (Text) — the capability key.
- `capability_version` (Text) — pins the capability contract version.
- `canonical_args` (JSONField) — canonicalized (sorted/key-normalized) arguments.
- `object_revisions` (JSONField) — `{object_id: revision}` map.
- `evidence_digest` (Text) — hash over the evidence the approver saw.
- `effect_limits` (JSONField) — budget/scope limits on the effect.
- `expires_at` (DateTime) — required; expired grants are inert.
- `status` (Text) — `active` / `consumed` / `revoked` / `superseded`.
- `granted_by` (Text) — principal who approved.
- `created_at` / `revoked_at`.

**Invalidation rule:** a grant only authorizes the *exact* (process version, capability
version, canonical args, object revisions, evidence digest) tuple it was minted for, within
its effect limits and before expiry. Mismatch on any field → refuse.

### Boundary stage
Add a `grant` check stage (after `pdp`/`consent`, before `execute`) that, when the capability
declares `requires_grant=True`, loads the matching `ApprovalGrant` and fails closed if none is
`active` and fully matching. Keep it **seam-safe**: the boundary (host side) reads the grant;
the engine never imports `ai.models`.

### Acceptance (verify with `pytest ai -q -k "grant or approval" -m "not live"`)
- **Revision pinning:** a grant for revision 7 does **not** authorize revision 8.
- **Expiry:** an expired grant is refused.
- **Three-concept separation:** PDP decision (authorization), grant (business approval), and
  consent stage (RULE_21) are distinct code paths; a refused grant still yields a PDP row +
  a `PolicyDecisionRow`, with the refusal attributed to the grant stage.
- `import-boundary-lint` + `manage.py check` clean.

---

## 4. Phase 3 master — next steps checklist

1. Create `/memories/session/pulse-phase3-progress.md` (own session file).
2. Read `.ai-toolkit/ONBOARDING.md` (mandatory first read).
3. Read `backend/accounts/capabilities.py` + `backend/ai/pdp.py` + `backend/ai/command_boundary.py`
   + `backend/ai/models/pdp.py` + `backend/ai/models/base.py` before writing code.
4. Implement P3-05b (roles + `AI_VIEW_CONSOLE`).
5. Implement P3-06 (`ApprovalGrant` + boundary stage).
6. Verify (coordinate with Gate 2 master per §0.1), then write `TASK-RESULTS-PHASE3.md`.
7. Wait for **P2-08** handoff signal (Gate 2 master) before P3-01 → P3-02 → P3-03.

---

## 5. P2-08 HANDOFF SIGNAL — ISSUED (Gate 2 master, 2026-09-13)

The Gate 2 master has **completed P2-08** and is handing off the `domain_packs/` seam. The
Phase 3 master may now start **P3-01 → P3-02 → P3-03**.

**What is handed off (stable, do not re-derive):**
- `backend/ai/engine/ports/domain.py` — `DomainPack` Protocol (`vocabulary()`, `api_catalog()`,
  `processes()`, `skills()`, `triggers()`, `prompts()`), `NeutralDomainPack` (empty fallback),
  `_InMemoryDomainPack`, and `load_domain_pack(pack_dir) -> DomainPack` (stdlib + PyYAML,
  degrades to neutral on missing/invalid). Re-exported from `ports/__init__.py`.
- `domain_packs/carbon/` — `api_catalog.yaml` (the `default_source_type` + `tools` the P3-01
  loader consumes), `vocabulary.yaml`, `triggers.yaml`, plus `processes/` / `skills/` /
  `prompts/` skeletons and an index README.

**Verification the handoff is green (Gate 2 master ran these):**
- `forbidden-term-lint.py` → **EXIT 0** ("engine is domain-agnostic") — P2-08 acceptance gate.
- `import-boundary-lint.py` → **EXIT 0** (engine imports only engine/stdlib/SDK).
- `manage.py check` → **EXIT 0** (0 silenced).
- `pytest ai -q` → 1762 passed (the 3 `test_grant.py` failures were P3-06 async-context bugs,
  since fixed by the Phase 3 master).

**Loader-chain contract for P3-01:** read `api_catalog.yaml` through `load_domain_pack(...).api_catalog()`;
NEVER import the YAML directly from engine code, and NEVER reintroduce domain vocabulary into
`engine/**` (the forbidden-term lint must stay EXIT 0). The loader must tolerate a `NeutralDomainPack`
(empty catalog → no capabilities registered, not an error).

---

## N. P3-12 — Pilot end-to-end (L, dep all above) — DONE

### Objective
Integration/acceptance layer over P3-01..P3-11. Prove the pilot governance loop end-to-end through
**two paths** — (1) "via Pulse" (Django service/API, pytest) and (2) "via UI" (Playwright HTTP + browser)
— covering the five done-when scenarios:
1. **Restart survival** — durable run/registry state read back byte-identical through a fresh service instance.
2. **Concurrent edit invalidates approval** — an `ApprovalGrant` pinned to revision/version N never authorizes N+1.
3. **Duplicate submit → no duplicate effect** — repeated submit/command is refused or deduplicated (effect fires once).
4. **Revoked permission blocks publish** — deactivating `ai:publisher` turns publish into 403, document stays `review`.
5. **Self-approval refused** — non-superuser author==publisher cannot self-publish (separation of duties).

### Delivered (qa-validator, test-only — no production code changed)
- `backend/ai/tests/pilot/__init__.py` (NEW) — package marker.
- `backend/ai/tests/pilot/test_pilot_e2e.py` (NEW) — **8 tests**, all `not live` (no LLM/SQLAlchemy/network).
- `carbon-frontend/tests/pilot-governance.spec.cjs` (NEW) — **5 Playwright tests** (4 HTTP scenario flows + 1 UI smoke); reads `CARBON_API_URL`/`CARBON_BASE_URL`/`CARBON_ADMIN_*` env with localhost defaults (mirrors `ci.yml` e2e env).

### Verification (Master Architect, terminal) — ✅ GREEN
1. `backend/ai/tests/pilot/test_pilot_e2e.py` → **8 passed** (`-m "not live"`).
2. Pilot + `test_registry_api.py` in one invocation → **27 passed** (no interference; CI runs everything together).
3. Playwright `pilot-governance.spec.cjs` against live :8009/:5179 → **4/4 API scenario tests passed**; UI smoke blocked locally only by missing system lib `libnspr4.so` (CI installs via `npx playwright install --with-deps chromium`). Heading text (`Process Registry`/`Review Queue`) confirmed to render as `<Typography variant="h5">`.
4. Gates: `manage.py check` → **0 issues**; `makemigrations ai --check --dry-run` → **No changes detected**; `import-boundary-lint` → **clean**; `failopen-lint` → **clean**.
5. CI auto-pickup confirmed: backend job `python -m pytest ...` discovers `ai/tests/pilot/test_*.py` (`python_files = test_*.py`); e2e job `npx playwright test` discovers `*.spec.cjs`.

### Flag (pre-existing, out of P3-12 scope)
`forbidden-term-lint.py` now reports **5 hits** in `backend/ai/engine/llm/prompts.py` (campus names
`South Valley`/`Smart Village`/`Abu Qir`) — a RULE_20 "engine must be domain-agnostic" violation in the
uncommitted working tree, NOT introduced by P3-12 (test-only). Needs a dedicated fix (move vocabulary to
`domain_packs/carbon/vocabulary.yaml` + load via DomainPack port). Tracked separately.
