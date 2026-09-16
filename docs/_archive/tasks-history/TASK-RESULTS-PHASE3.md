# TASK-RESULTS-PHASE3.md

## [2026-09-13] Second Master (Phase 3) — P3-05b (AI governance roles + `AI_VIEW_CONSOLE`) + P3-06 (`ApprovalGrant` + boundary `grant` stage)

**Role:** Master Architect (DeepSeek V4-Pro) · **Kind:** CBAC roles + business-approval grant (Phase 3). Implemented both immediately-startable tasks end-to-end with tests, preserving the RULE_20 / ADR-0007 seam invariant (engine never imports `ai.models` / host modules).

### Delivered

**P3-05b — five governance roles + read-only console (all as CBAC capabilities):**
- `backend/accounts/capabilities.py` — added `AI_PROCESS_OWNER` (`ai:process_owner`), `AI_POLICY_OWNER` (`ai:policy_owner`), `AI_PUBLISHER` (`ai:publisher`), `AI_OPERATOR` (`ai:operator`), `AI_AUDITOR` (`ai:auditor`) (category `admin`), registered all five in `ALL_CAPABILITIES`, and added five `GROUP_CAPABILITIES` entries (`ai_*_group` → declared key only; `ai_auditor_group` additionally carries `ai:view_console`). Intentionally non-overlapping — no new `IMPLIES` edges. `AI_VIEW_CONSOLE` already existed and was NOT duplicated.
- `backend/accounts/constants.py` — added `AI_PROCESS_OWNER_GROUP` … `AI_AUDITOR_GROUP`, `AI_GOVERNANCE_GROUPS`, and folded `*AI_GOVERNANCE_GROUPS` into `PROTECTED_GROUPS` + `ALL_CANONICAL_GROUPS`. Left out of `VISIBILITY_ROLES` / `READ_ONLY_ROLES` / `GROUP_BRAND_SCOPE` (global, per spec).
- `backend/ai/permissions.py` (NEW) — `AIViewConsolePermission(permissions.BasePermission)`: authenticated + `SAFE_METHODS` only (refuses POST/PUT/PATCH/DELETE before any capability check) + `has_capability(user, AI_VIEW_CONSOLE.key)`.
- `backend/accounts/models.py` — confirmed `ScopedRole` binds `user × group × org_unit × module` with no schema change needed.

**P3-06 — `ApprovalGrant` + boundary `grant` stage (strict three-concept separation):**
- `backend/ai/models/approval.py` (NEW) — `ApprovalGrant(AppScopeMixin)`, `app_label="ai"`, UUID pk via `generate_uuid`, pins `(process_version, capability, capability_version, canonical_args, object_revisions, evidence_digest, effect_limits)` + `expires_at` (required) + `status` (`active|consumed|revoked|superseded`); `find_active()` is an exact-match, unexpired, `status=active` filter (fail-closed on any mismatch); `is_expired()` / `revoke()` (timezone-aware); module-level `canonicalize_args()` (recursive sorted/key-normalized).
- `backend/ai/grant.py` (NEW, host-side) — `resolve_grant(command)` reads `ApprovalGrant.find_active` via `sync_to_async`; on no-match persists a `PolicyDecisionRow` with `stage="grant"` / `decision="refuse"` / `reason=GRANT_REFUSAL_REASON` / `policy_version="grant"` and returns `None`.
- `backend/ai/command_boundary.py` — `STAGES` 13→14 (inserted `grant` after `consent`, before `budget`); new `Command` fields (`requires_grant`, `capability`, `process_version`, `capability_version`, `object_revisions`, `evidence_digest`, `object_id`, `object_type`, `process_instance`); `GrantResolver` type alias + injectable `grant_resolver`; stage-8 gate that resolves the capability from the catalog entry when unset and fails closed on exception/no-match. Helpers `_catalog_entry()` / `_command_requires_grant()` / `_catalog_capability()` read dict-based or `ToolDef`-based catalog entries.
- `backend/ai/command_boundary_factory.py` — wired `grant_resolver=resolve_grant` (overridable).
- `backend/ai/adapter/types.py` — `ToolDef.requires_grant: bool = False`.
- `backend/ai/models/pdp.py` — added `stage = TextField(default="pdp", db_index=True)` so grant refusals are attributed distinctly from PDP decisions.
- `backend/ai/models/__init__.py` — exported `ApprovalGrant`; `backend/ai/admin.py` — read-only `ApprovalGrantAdmin`.
- `backend/ai/pdp.py` — `_persist()` now writes `stage="pdp"`.
- Migrations `backend/ai/migrations/0031_approvalgrant.py` + `0032_policydecisionrow_stage.py` (hand-authored, mirror `makemigrations` output; deps chain `0030 → 0031 → 0032`).

### Tests (added / updated)
- `backend/accounts/tests/test_capability_rbac_extensive.py` — role×action matrix: governance caps exist, resolve to declared caps only, `ai:view_console` implies no write, no cross-implication; `test_capability_count` bound 60–75 (now 70); exact group-set assertion updated.
- `backend/ai/tests/test_command_boundary.py` — renamed `test_budget_exceeded_refused_at_stage_8` → `_stage_9`; `test_stage_order_runs_exactly_1_to_13` → `_1_to_14` (`len == 14`); added 5 grant-stage tests (default fail-closed, resolver match, catalog-flag enforcement, resolver-exception fail-closed, stage-skip-when-not-required).
- `backend/ai/tests/test_grant.py` (NEW) — `django_db(transaction=True)`: `canonicalize_args` determinism/coercion; revision pinning (rev 7 ≠ rev 8); process/capability-version pinning; capability/evidence/object-identity pinning; expired + revoked inert; async PDP-ALLOW + grant-REFUSE row attribution (`stage="pdp"` vs `stage="grant"`); consent-vs-grant stage separation.

### Verification
- **Static (this session):** `get_errors` on all 15 touched files → **No errors found**.
- **Seam invariant:** no file under `backend/ai/engine/` was touched; the grant resolver is host-side and injected via `grant_resolver=` (engine never imports `ai.models`). `ai/grant.py` imports only `ai.models.*` + stdlib.
- **Verifier run (Master Architect, terminal):** ✅ ALL GREEN
  1. `pytest accounts/tests/test_capability_rbac_extensive.py -q -m "not live"` → **249 passed**
  2. `pytest ai/tests/test_command_boundary.py ai/tests/test_grant.py -q -m "not live"` → **34 passed**
  3. `.ai-toolkit/scripts/import-boundary-lint.py` → **Import boundary: clean**
  4. `manage.py makemigrations --check --dry-run` → **No changes detected**; `manage.py check` → **0 issues**

### Fixes applied during verification (drift + async-test bugs found by the verifier)
1. **Migration index drift** — `ApprovalGrant.Meta.indexes` was unnamed in the model but named `ai_approvalgrant_active_idx` in `0031_approvalgrant.py`. Django's autodetector wanted to rename it. Fixed by giving BOTH the model and migration the same explicit name `ai_approval_active_idx`. (Rule: Django `ModelState` requires an explicit `name=` on `models.Index` in migration files — never leave it unnamed.)
2. **`SynchronousOnlyOperation` in `test_grant.py`** — the 3 `@pytest.mark.asyncio` tests called synchronous ORM directly (`_make_grant()` and `PolicyDecisionRow.objects.filter()`). Added `_amake_grant`/`_aquery` helpers using `asgiref.sync.sync_to_async` and wrapped the `.filter()` read. (Rule: all ORM calls inside `@pytest.mark.asyncio` tests must go through `sync_to_async`.)

### Deviations / decisions
1. Grant stage placed at position 8 (after `consent`, before `budget`/`execute`) — matches "after pdp/consent, before execute"; `STAGES` 13→14.
2. `PolicyDecisionRow.stage` (default `"pdp"`) added so the audit ledger attributes grant refusals to `stage="grant"`, distinct from `stage="pdp"`.
3. `requires_grant` threads through `Command` (fail-closed `False`) + `ToolDef` + dict catalog entries; capability resolved from `command.capability` or catalog `required_capability`.
4. `AI_VIEW_CONSOLE` already existed — not duplicated; only the five role capabilities + group mappings + DRF permission were added.

### Next
Wait for the **P2-08** handoff signal (Gate 2 master) before P3-01 → P3-02 → P3-03 (the loader chain). P3-09 (Human Task Inbox) now has its `ApprovalGrant` dependency satisfied.

---

## [2026-09-13] Second Master (Phase 3) — P3-01 (`Capability` model + loader) + P3-02 (pilot contracts + predicate) + P3-03 (`ProcessDefinition` schema)

**Role:** Master Architect (DeepSeek V4-Pro) · **Kind:** loader chain (registry → contracts → process schema). Implemented the P2-08-dependent loader chain end-to-end with production code + tests, preserving the RULE_20 / ADR-0007 seam invariant (engine never imports host modules; host may import engine *ports* only).

### File inventory (all CREATED unless noted EDITED)

**P3-01 — `Capability` model + loader**
- `backend/ai/capability_registry.py` (NEW) — import-free host registry mapping capability `host_action` key → `"module:qualname"` (or `HUMAN_TASK_SENTINEL = "human_task:inbox"`). Stdlib only → no import-time cycle, no DB access.
- `backend/ai/models/capability.py` (NEW) — `Capability(AppScopeMixin)`, `app_label="ai"`, UUID pk, `capability_id` (Text, unique), full contract fields, `Meta.indexes=[Index(fields=["kind","owner"], name="ai_capability_lookup_idx")]`; `from_spec()` / `load_capabilities()` / `sync_capabilities()` / `resolve_host_action()` (lazy `importlib`, fail-closed `CapabilityValidationError`) / `iter_capability_specs()` / `default_pack_dir()`.
- `backend/ai/migrations/0033_capability.py` (NEW) — hand-authored `CreateModel`, deps `0032`, explicit index name `ai_capability_lookup_idx`.

**P3-02 — pilot contracts + predicate**
- `backend/ai/predicates.py` (NEW) — `dq_rule_active_revision_matches_approved_revision(rule)` fail-closed (reads `definition` dict → mapping → attributes; missing/incoercible → `False`).
- `domain_packs/carbon/api_catalog.yaml` (EDITED) — added `capabilities:` list (4 pilot capabilities) below the existing `tools:` list (tools untouched): `dq.rule.validate` (read_only), `dq.rule.review` (human_task, `host_action: human_task:inbox`), `dq.rule.publish` (mutation, `requires_confirmation: true`, `approval_requirements.requires_grant: true`), `dq.rule.active_revision_matches_approved_revision` (assertion).

**P3-03 — `ProcessDefinition` schema + validator**
- `backend/ai/models/process.py` (NEW) — `ProcessDefinition(AppScopeMixin)`, `app_label="ai"`, UUID pk, `process_id`/`version`/`owner`/`status` denormalized + `definition` JSONField; `Meta.indexes=[Index(fields=["process_id","version"], name="ai_process_lookup_idx")]`; `validate()` / `from_document()` raise on error; module-level hand-rolled `validate_definition()` enforcing required fields, `status` enum, `step.kind` enum, `autonomy` enum, capability resolution, `depends_on` refs.
- `backend/ai/process_schema.json` (NEW) — canonical JSON Schema (draft-07) for the process definition document (the external contract; the hand-rolled validator is the runtime enforcement fallback because `jsonschema` is NOT in `backend/requirements.txt`).
- `domain_packs/carbon/processes/dq.rule.release.yaml` (NEW) — pilot `dq.rule.release` definition (validate → review → publish → verify) as a single-doc YAML consumed by `load_domain_pack(...).processes()`.
- `backend/ai/migrations/0034_processdefinition.py` (NEW) — hand-authored `CreateModel`, deps `0033`, explicit index name `ai_process_lookup_idx`.

**Wiring (EDITED)**
- `backend/ai/models/__init__.py` — exported `Capability` + `ProcessDefinition`.
- `backend/ai/admin.py` — read-only `CapabilityAdmin` + `ProcessDefinitionAdmin` (mirrors the `ApprovalGrantAdmin` pattern).

### Tests (NEW, 3 files)
- `backend/ai/tests/test_capability_loader.py` — 6 tests (pilot ids registered, kind/approval contract assertions, unknown host_action raises, missing host_action raises, NeutralDomainPack → [], `sync_capabilities` idempotent).
- `backend/ai/tests/test_predicates.py` — 6 tests (match, mismatch, fail-closed missing active, fail-closed missing approved, reads `definition` dict, string/int equivalence).
- `backend/ai/tests/test_process_schema.py` — 7 tests (pilot validates + `from_document`, rejects unknown step kind, unknown capability, missing required field, bad status, bad autonomy, missing dependency).
- **Total: 19 tests** across 3 files.

### Design decisions
1. **Dedicated host-action registry (not the engine tool catalog).** The agent-facing tools (`ai.engine.agent.tools.get_tool_definitions`, `ai.domain.*.get_tools`) enumerate agent tools (`search_knowledge`, `create_dq_rule`, …), whereas a capability names a *governed host action* (`dq.rule.validate`, `dq.rule.publish`, …). A separate, import-free host registry is the single non-circular resolution point for both P3-02 contracts and the P3-03 validator.
2. **Lazy `importlib` resolution.** `resolve_host_action()` imports `"module:qualname"` on demand → `capability_registry.py` never imports `dq` / `ai.predicates`, and importing `ai.models` cannot create a cycle or hit the DB.
3. **`dq.rule.review` → `human_task:inbox` sentinel.** The review step has no synchronous host callable (P3-09 inbox is future work), so its `host_action` is the sentinel; `from_spec` enforces it may only pair with `kind == "human_task"`.
4. **`dq.rule.validate` / `dq.rule.publish` both bind `dq.services:run_single_rule`** — today's single DQ host service; `validate` is the read-only projection and `publish` is the post-approval mutation whose RULE_21 consent gate lives in the command boundary. A dedicated `dq.services.publish_rule` will supersede the publish binding in P3-05a (no DQ model change yet).
5. **Hand-rolled validator because `jsonschema` is absent** from `backend/requirements.txt`; `process_schema.json` remains the canonical external contract and `validate_definition()` mirrors its enums (declared as module constants).
6. **Capability resolution in the process validator** defaults to the P3-01 loader (`load_capabilities()`), so an unknown capability id in a step is a validation error (fail-closed).

### Migration chain
`0032_policydecisionrow_stage` → **`0033_capability`** → **`0034_processdefinition`** (hand-authored, mirror `makemigrations`; each `models.Index` carries an explicit `name=` per the P3-06 lesson).

### Deviations / risks
1. **`DQRule` has no `approved_revision` / `active_revision` fields** — the predicate reads them defensively from `definition` (dict) → mapping → attributes. If the DQ source of truth stores these elsewhere (e.g. a revision table or `version` int), the predicate's attribute read path is dead code until P3-05a wires the real revision source. **Flag for P3-05a.**
2. **`publish` shares `run_single_rule` with `validate`** — no distinct publish mutation exists in DQ today. The registry binding is a placeholder until a real `publish_rule` host action exists.
3. **Test DB `--nomigrations --reuse-db`** — `ai/capability` + `ai/processdefinition` tables are created only from the models on a *fresh* test DB. If `test_carbon_dev` is stale (created before these models), the verifier must drop/recreate it first (same caveat as P3-06's `test_grant.py`).
4. **No runtime verification this session** (no terminal). All correctness is static (`get_errors` clean on all 16 files). The verifier must run the test commands below.

### Verification (Master Architect, terminal) — ✅ ALL GREEN
1. `pytest ai/tests/test_capability_loader.py ai/tests/test_predicates.py ai/tests/test_process_schema.py -q -m "not live" --create-db` → **19 passed**.
2. `.ai-toolkit/scripts/import-boundary-lint.py` → **Import boundary: clean** (engine untouched; host modules import only `ai.engine.ports.domain`).
3. `.ai-toolkit/scripts/forbidden-term-lint.py` → **Forbidden domain term: clean** (engine is domain-agnostic).
4. `manage.py makemigrations --check --dry-run` → **No changes detected**; `manage.py check` → **0 issues**.
5. Full `ai` regression (`pytest ai -q -m "not live"`) → **1796 passed**, 8 failed + 3 errors — ALL pre-existing/environmental, none from Phase 3 (see below).

### Regression triage (full `ai` suite — 8 failed + 3 errors are NOT Phase 3)
- **7× `test_code_sandbox.py`** — environmental: `ModuleNotFoundError: No module named 'matplotlib'` / missing pandas / OS sandboxing (os.system/network/file-write blocking) unavailable in this container. Known exclusion (`pytest ai -k "not code_sandbox"`).
- **1× `test_skill_admission.py::test_admission_rejects_on_harmlessness_llm_error`** + **2× `test_port_adapters_kg_watches.py`** — pass in isolation (**8 passed** when run standalone) → test-ordering pollution, not deterministic. Files untouched by Phase 3.

### Next
P3-05c (Registry + Review Queue screens under `/admin/ai/*`) is now unblocked (dep P3-05a, frontend). P3-09 (Human Task Inbox) remains the sink for `dq.rule.review` (sentinel already reserved). P3-07a (durable run machine) is the next backend milestone (dep P3-03).

---

## [2026-09-13] Second Master (Phase 3) — P3-04 (process-owner interview kit) + P3-05a (Registry API)

**Role:** Master Architect (DeepSeek V4-Pro) · **Kind:** host-side interview provenance + process registry lifecycle. Both host-side; RULE_20 / ADR-0007 seam intact (engine untouched, only `ai.engine.ports.domain` imported by the host).

### Delivered

**P3-04 — process-owner interview kit:**
- `domain_packs/carbon/prompts/process_interview.yaml` (NEW) — 4 pilot questions (emergency waivers → `exceptions`, approval validity after edit → `scope.approval_validity`, reconciliation owner → `owner`, SLA → `constraints.sla`). All fields schema-compatible (no new top-level keys; `additionalProperties:false` intact).
- `backend/ai/models/process_interview.py` (NEW) — `ProcessInterview(AppScopeMixin)`: `process_id`, `questions` (JSON list snapshot), `answers` (JSON list of `{question_id, answer, answered_by, answered_at}`), `status` (open/signed), `signed_by`, `signed_at`, `signature_digest`. Index `ai_interview_lookup_idx`. Provenance kept OUT of the definition doc (side-channel model).
- `backend/ai/process_interview.py` (NEW) — `load_questions()` (pack → `DEFAULT_QUESTIONS` fallback), `build_interview_kit()`, `record_answers()` (merge + provenance + `validate_definition` gate), `sign_definition()` (sha256 over sorted doc + owner).

**P3-05a — Registry API:**
- `backend/ai/models/autonomy.py` (NEW) — `AutonomyOverride(AppScopeMixin)` per `(process_id, step_id, org_unit)` with `autonomy` (6-level dial), `set_by`. Index `ai_autonomy_lookup_idx` + `UniqueConstraint` `ai_autonomy_override_unique`.
- `backend/ai/registry_service.py` (NEW) — `ProcessRegistry`: `create_draft`, `edit_draft` (draft-only; author or `ai:process_owner`), `submit_for_review`, `publish` (**author ≠ publisher** enforced via `_identity(actor) != owner`), `deprecate`, `diff` (recursive added/removed/changed), `set_autonomy` (validates 6-level enum + step exists), `get_autonomy`, `set_kill_switch`, `is_killed`. CBAC via `has_capability`/`has_any_capability` (no hardcoded group names).
- `backend/ai/registry_api.py` + `backend/ai/registry_urls.py` (NEW) — `RegistryViewSet` mounted at `/carbon-api/ai/registry/` (added to `config/urls.py`). Reads gated by 4 governance caps; writes gated per operation.
- `backend/ai/migrations/0035_processinterview_autonomyoverride.py` (NEW, deps 0034).
- `backend/ai/models/__init__.py` + `backend/ai/admin.py` — exported + read-only admin for `ProcessInterview`, `AutonomyOverride`.

### Verification (Master Architect, terminal) — ✅ ALL GREEN
1. `manage.py check` → **0 issues** (after fixing E034 index-name length, below).
2. `manage.py makemigrations ai --check --dry-run` → **No changes detected**.
3. `pytest ai/tests/test_process_interview.py ai/tests/test_registry_api.py -q -m "not live" --create-db` → **14 passed** (5 interview + 9 registry).
4. Combined Phase-3 regression (loader + grant + boundary + interview + registry) → **67 passed**.
5. `import-boundary-lint.py` → **clean**; `forbidden-term-lint.py` → **clean**.

### Fix applied during verification
- **Index-name length (E034)** — `ai_process_interview_lookup_idx` (31) and `ai_autonomy_override_lookup_idx` (31) exceeded PostgreSQL's 30-char limit. Renamed to `ai_interview_lookup_idx` + `ai_autonomy_lookup_idx` in BOTH model `Meta.indexes` and migration 0035 (names must match exactly).

### Deviations / risks
1. **Autonomy-dial mismatch (deferred to P3-07a)** — `ai/pdp.py` runtime `_AUTONOMY_LEVELS = {human_only, act_confirm, auto}` (3-level) vs the registry's 6-level schema dial (`observe/propose/act_confirm/act_notify/act_silent/human_only`). Registry stores/validates the 6 levels now; PDP reconciliation is out of scope here and re-checked before every effect in P3-07a.
2. **`set_autonomy` gate at view layer** — service method signature has no `actor`, so the `ai:process_owner` gate is applied in the view (`set_autonomy` action), per the per-operation-write rule.
3. **`reconciliation_owner` maps to `owner`** — reuses the definition `owner` field for the accountable reconciliation owner (no new top-level key). Flag if a distinct reconciliation-owner field is later required.

---

## [2026-09-13] Master Architect — P3-05a re-verification + P3-07a (Durable Run Machine) completion

**Role:** Master Architect (DeepSeek V4-Pro) · **Kind:** registry API expansion + durable run machine verification. Both host-side; RULE_20 / ADR-0007 seam intact (`import-boundary-lint` clean — `run_machine.py` is pure, `plans_service.py`/`registry_service.py` are host modules; engine never imports them).

### P3-05a — Registry API (re-verified, test suite expanded 9 → 19)
- `backend/ai/tests/test_registry_api.py` expanded to **19 tests** (was 9): full lifecycle, CBAC gating, self-publish refusal, superuser self-publish, diff vs active, no-active-version diff, autonomy dial get/patch + rejection of unknown step / invalid value, kill-switch round-trip + operator/owner gating, illegal-transition → 400.
- **Fix applied during verification:** `test_illegal_transitions_return_400` authenticated as a process owner (no `ai:publisher`), so `publish` was refused at the *permission* gate (403) before the *status* check (400) could run. Added `grant_role(owner, group_name=AI_PUBLISHER_GROUP)` so an authorized actor reaches the status-transition check — the test's actual intent.

### P3-07a — Durable run machine (completed + verified)
- `backend/ai/run_machine.py` (NEW, pure) — closed 9-state alphabet (`planned → awaiting_approval → ready → executing → succeeded|failed|outcome_unknown → awaiting_reconciliation | cancelled`), `RUN_TRANSITIONS`/`STEP_TRANSITIONS` tables, `can_transition`/`assert_transition`/`transition`/`allowed_targets`/`is_terminal`/`validate_state`, `InvalidStateTransition`. No Django/engine imports.
- `backend/ai/models/core.py` — `Run` + `run_state`/`definition_id`/`definition_version`/`idempotency_key`/`kill_switched_at` + `pin_definition()`/`pin_definition_version()` (write-once). `RunStep` + `step_state`/`step_id`/`idempotency_key`/`outcome`/`retry_count`/`last_error` + `ai_runstep_lookup_idx` + `UniqueConstraint (run_id, step_id)`.
- `backend/ai/plans_service.py` — `begin_step` (idempotent `get_or_create` keyed on `(run_id, step_id)`), `advance_step` (closed-table), `reconcile_outcome` (`executing → outcome_unknown → awaiting_reconciliation`, idempotent), `preflight` (kill-switch fail-closed FIRST → PDP re-check).
- `backend/ai/migrations/0036_runmachine.py` (NEW, deps 0035) — adds all fields + index + constraint; `makemigrations --check` clean.

### Verification (Master Architect, terminal) — ✅ ALL GREEN
1. `pytest ai/tests/test_run_machine.py -q -m "not live" --create-db` → **11 passed**.
2. Combined Phase 3 suite (`test_capability_loader` + `test_predicates` + `test_process_schema` + `test_grant` + `test_command_boundary` + `test_process_interview` + `test_registry_api` + `test_run_machine`) `-q -m "not live"` → **88 passed**.
3. `manage.py check` → **0 issues**; `manage.py makemigrations --check --dry-run` → **No changes detected**.
4. `import-boundary-lint.py` → **clean**; `forbidden-term-lint.py` → **clean**; `failopen-lint.py` → **clean**.

### Deviations / risks (carried forward)
1. **Autonomy-dial mismatch (PDP 3-level vs registry 6-level) remains** — `plans_service.preflight()` accepts a PDP-level `autonomy` arg (defaults to conservative `human_only`); full 3↔6 reconciliation is deferred to the effect loop in P3-07b/P3-08 (unchanged from P3-05a note).
2. **`registry_service.py` is a live dependency, not dead code** — `ProcessRegistry` is imported by `plans_service.preflight` (kill-switch check) and `command_boundary.py` (injectable `process_registry`). It must NOT be deleted; it is the service layer under `registry_api.py`.

---

## [2026-09-13] Master Architect — P3-08 (Reconciliation worker)

**Role:** Master Architect (DeepSeek V4-Pro) · **Kind:** host-side `outcome_unknown` reconciliation. RULE_20 / ADR-0007 seam intact — `reconciliation.py` is host-side (imports `ai.models`/`ai.plans_service`/`ai.run_machine` only); engine never imports it.

### Delivered
- `backend/ai/reconciliation.py` (NEW) — `reconcile_step` / `reconcile_pending` + `ReadBackResult` (`committed|absent|unknown`), `register_read_back(effect_name, fn)` provider seam, `ReconciliationResult` dataclass. **Structural "exactly one effect" guarantee**: the module has NO effect-dispatch code path — it only reads back and advances state or escalates.
- `backend/ai/models/reconciliation.py` (NEW) — `ReconciliationEscalation(AppScopeMixin)` (CBAC-scoped): `run_id`, `step_id`, `process_id`, `operation_id`, `read_back_status/detail`, `reason`, `resolved_at`; unique `(run_id, step_id)` (`ai_reconcile_step_uniq`) → idempotent escalation, no stacked duplicates.
- `backend/ai/management/commands/reconcile_outcomes.py` (NEW) — `manage.py reconcile_outcomes [--limit N]` scheduler entrypoint (cron documented, no Celery).
- `backend/ai/models/core.py` — `RunStep.operation_id` (Text) — persisted read-back key.
- `backend/ai/plans_service.py` — `reconcile_outcome` now persists `op_id` → `step.operation_id` at dispatch time.
- `backend/ai/migrations/0037_reconciliation_escalation.py` (NEW, deps 0036).
- `backend/ai/models/__init__.py` — exports `ReconciliationEscalation`.

### Verification (Master Architect, terminal) — ✅ ALL GREEN
1. Combined Phase 3 suite (reconciliation + run_machine + registry_api + grant + process_interview + capability_loader + predicates + process_schema + command_boundary) `-q -m "not live" --create-db` → **99 passed**.
2. `manage.py check` → **0 issues**; `makemigrations --check --dry-run` → **No changes detected**.
3. `import-boundary-lint.py` → **clean**; `forbidden-term-lint.py` → **clean**; `failopen-lint.py` → **clean**.

### Acceptance evidence
- **"timeout-after-commit → exactly one effect"** (`test_timeout_after_commit_exactly_one_effect`): dispatch committed then timed out → read-back `committed` → step `succeeded` with the committed-effects list unchanged (no re-dispatch) and no escalation.
- **committed→succeeded**, **absent→failed**, **inconclusive→escalation**, **never-blind-retry** (no dispatch path), **missing operation-id → fail-closed escalate**, **escalation idempotency**, **provider seam** all covered (11 tests).

### Deviations / notes
1. **`operation_id` is a new `RunStep` field** (not reusing `idempotency_key`) — semantically distinct: `idempotency_key` dedupes dispatch, `operation_id` is the downstream read-back key.
2. **Read-back defaults to fail-closed inconclusive** when no provider is registered (no downstream integration exists yet) — `register_read_back` is the documented hook for future integrations (P3-09 inbox will surface the escalation rows).
3. **No `select_for_update` row-locking** — single-threaded cron + atomic `get_or_create` + unique constraint suffice; "exactly one effect" holds by the absence of a dispatch path, not locking.

## [2026-09-13] Master Architect — P3-07b (Workflow/activity split + deterministic step journal)

**Role:** Master Architect (DeepSeek V4-Pro) · **Kind:** host-side deterministic orchestration + append-only replay journal. RULE_20 / ADR-0007 seam intact — `step_journal.py` is host-side (imports `ai.models`/`ai.run_machine` only); engine never imports it.

### Delivered
Two complementary append-only journals (distinct consumers, never redundant):

**Step-level event journal (replay source of truth):**
- `backend/ai/models/step_journal.py` (NEW) — `StepJournalEntry(AppScopeMixin)` (CBAC-scoped): `run_id`, `step_id`, `event_type`, `sequence`, `payload`, `created_at`. **Closed event vocabulary** `EVENT_*` (`step_queued|step_started|step_retried|step_completed|step_failed|step_consent_requested|step_consent_granted|step_consent_declined|outcome_unknown`); `TERMINAL_JOURNAL_EVENTS = {step_completed, step_consent_declined}` — **`step_failed` deliberately EXCLUDED** (failed = not committed = retryable). `STEP_KIND_WORKFLOW`/`STEP_KIND_ACTIVITY`; index `ai_journal_run_seq_idx` + unique `ai_journal_run_seq_uniq`.
- `backend/ai/step_journal.py` (NEW) — `StepJournal` service: `append` (rejects unknown events), `for_step`, `next_sequence` (Max+1, append-only monotonic), `reconstruct(entries)` **pure deterministic fold** → `{step_state, status, retry_count, outcome, consent, last_event, committed}`. `canonical_step_id(step)` (uses `step_id` else `step_index`).
- `backend/ai/migrations/0038_step_journal.py` (NEW, deps 0037) — `RunStep.step_kind` + `StepJournalEntry`.

**Run-level activity journal (deterministic driver source of truth):**
- `backend/ai/models/journal.py` (NEW) — `RunJournalEntry(AppScopeMixin)` (CBAC-scoped): `run_id`, `step_id`, `step_index`, `activity_kind` (`llm`/`host`), `sequence`, `operation_id`, `canonical_inputs_json`, `status` (`planned|dispatched|succeeded|failed|outcome_unknown|skipped`), `result_json`, `error`, `attempt`. Index `ai_runjournal_step_idx` + unique `ai_runjournal_seq_uniq`.
- `backend/ai/workflow.py` (NEW) — **pure deterministic workflow driver**: `ActivitySpec` (frozen dataclass), `next_activity(specs, entries)` (committed skipped, `outcome_unknown` blocked, lowest-`step_index` eligible wins), `reconcile_inflight(specs, entries, retry_max=3)` (requeue dispatched/failed up to cap), `latest_statuses` (fold by sequence), `RunJournal` (append-only facade). No wall-clock, no randomness, no DB in the pure fold functions.
- `backend/ai/migrations/0039_runjournalentry.py` (NEW, deps 0038).

**Host integration:**
- `backend/ai/plans_service.py` — `is_activity(step)` (workflow vs activity: `step_kind` marker, fallback `tool_name`, fail-safe "retry don't skip"), `replay_step(run, step)` (noop/resume/requeue), `_restore_step_from_recon`, `_retry_activity_step`, `_ADVANCE_EVENT_BY_STATE`, `_ensure_operation_id`, `_invoke_effect`; `dispatch_activity` (bounded RETRY_* dispatch writing run-journal entries before/after each effect; `outcome_unknown` routes to `reconcile_outcome`; never blind-retries), `resume_workflow` (restart-mid-run: reconcile inflight → re-enter driver), `resume_and_run_next`. Step-journal `append` wired into `begin_step` (`step_queued`), `advance_step` (`step_started`/`step_completed`/`step_failed`/`step_consent_requested`), `reconcile_outcome` (`outcome_unknown`), retry (`step_retried`).
- `backend/ai/models/core.py` — `RunStep.step_kind` (default `'activity'`).
- `backend/ai/models/__init__.py` — exports `StepJournalEntry` + `RunJournalEntry`.
- `backend/ai/tests/test_step_journal.py` (NEW) — 20 tests (16 written by the batch subagent + 4 acceptance tests added by Master Architect on re-verification).

### Verification (Master Architect, terminal) — ✅ ALL GREEN
1. `test_step_journal.py` alone → **20 passed**; combined Phase 3 suite (step_journal + reconciliation + run_machine + registry_api + grant + process_interview + capability_loader + predicates + process_schema + command_boundary) `-q -m "not live" --reuse-db` → **119 passed**.
2. `manage.py check` → **0 issues**; `makemigrations ai --check --dry-run` → **No changes detected in app 'ai'**.
3. `import-boundary-lint.py` → **clean**; `forbidden-term-lint.py` → **clean**; `failopen-lint.py` → **clean**.

### Acceptance evidence
- **Restart mid-run → resumes from journal** (`test_restart_mid_run_resumes_from_journal`): committed activity `noop` (never re-executed), interrupted activity `resume`, workflow step `requeue` — all deterministic across a second replay.
- **Exactly-one-effect** (`test_replay_completed_step_is_noop_not_reexecuted`): completed activity restored to fold state with **no new events**.
- **RULE_21** (`test_consent_never_auto_confirmed_on_replay`, `test_fold_consent_granted_never_auto_confirmed`, `test_three_day_approval_survives_restart`): consent-gated activity resumes WITHOUT granting consent; `consent_granted` is non-terminal; a 3-day restart leaves the step `awaiting_approval` (the `now` clock never auto-expires consent).
- **Fold determinism + closed vocabulary** (`test_fold_is_deterministic`, `test_append_rejects_unknown_event`): same events → same state; unknown events rejected.
- **Bounded retry** (`test_activity_retry_policy_capped`): a transiently failing activity is dispatched exactly `RETRY_MAX_ATTEMPTS` times, then terminal `failed`.
- **Never blind-retry `outcome_unknown`** (`test_dispatch_outcome_unknown_never_blind_retries`): exactly one dispatch, routed to `awaiting_reconciliation` with `operation_id` persisted.
- **Operation-id persistence** (`test_operation_id_persisted_on_successful_dispatch`): `operation_id` persisted at dispatch and survives success (stable read-back key, P3-08).

### Deviations / notes
1. **Two journals, distinct consumers** — `StepJournalEntry` (step lifecycle events → replay fold / `replay_step`) vs `RunJournalEntry` (activity dispatch status → workflow driver / `next_activity` + `reconcile_inflight`). Not redundant: one answers "what state is this step in", the other "what to dispatch next" honoring dependency order. Both append-only, keyed on monotonic `sequence`.
2. **`step_failed` is not a terminal/committed journal event** — a failed step is retryable; only `step_completed`/`step_consent_declined` mark "committed" (exactly-one-effect guard).
3. **Journal is the source of truth, not `RunStep.status`** — replay reconstructs from the append-only log; `_restore_step_from_recon` writes only differing fields.
4. **No engine imports** — the fold + driver are pure Python reconstruction; the engine never reads the journal (RULE_20 / ADR-0007).
5. **`dispatch_activity`/`resume_workflow`/`resume_and_run_next` are service-layer entry points** not yet wired to a view — they are the host-side driver consumed by the P3-10 scheduler (in scope, not dead code).

---

## [2026-09-13] Second Master (Phase 3) — P3-09 (Human Task Inbox) + P3-10 (`invoke_skill` reimplementation)

**Role:** Master Architect (DeepSeek V4-Pro) · **Kind:** durable approval inbox + skill invocation through the command boundary. Both depend on P3-06 (`ApprovalGrant`) / P3-07a (run machine), now satisfied. Implemented end-to-end with production code + tests + frontend screens, preserving RULE_20 / ADR-0007.

### P3-09 — Human Task Inbox (durable approval tasks)

**Model — `backend/ai/models/human_task.py` (NEW):**
- `HumanTask(AppScopeMixin)` (CBAC-scoped, UUID pk via `generate_uuid`). Pins the grant tuple: `consequence` (required), `objects_revisions_json`, `before_json`, `after_json`, `evidence_json` + `evidence_digest` (sha256 of evidence), `reversibility` (required, closed vocab `reversible|irreversible`), `effect_limits`, `canonical_args`, `object_id`/`object_type`/`process_instance`, `required_authority` (required, db_index), `expires_at` (required), `alternatives_json`, `status` (`pending|approved|declined|expired|cancelled`), `grant_id`, `decided_by`, `decided_at`, `decline_reason`. Indexes `ai_humantask_inbox_idx` + `ai_humantask_authority_idx`. Methods `is_expired()` / `is_pending()`.

**Service — `backend/ai/task_inbox.py` (NEW):**
- `TaskInbox` — `create_task(...)` (fail-closed: consequence + required_authority required; reversibility validated), `list_pending(user, now)` (CBAC-scoped via `accounts.ai_scoping.scope_ai_queryset`), `get()` (`TaskNotFound`), `approve()`/`decline()` (`select_for_update` + `_decide_locked`; idempotent; approve mints a bound `ApprovalGrant` via `_mint_grant`), `expire_stale()`, `_principal()`. Defaults `DEFAULT_REQUIRED_AUTHORITY="ai:operator"`, `DEFAULT_REVERSIBILITY=IRREVERSIBLE`, `DEFAULT_TASK_TTL=7d`. Exceptions: `TaskInboxError`, `TaskNotFound`, `TaskExpired`, `TaskNotPending`, `UnauthorizedApprover`, `InvalidTask`.

**Boundary seam — `enqueue_inbox_task(command, now=)`** (async): wired into the boundary via `command_boundary_factory.py` (`task_enqueuer=enqueue_inbox_task`) → `command_boundary.py` grant stage defers to the inbox when no grant matches (instead of hard-refusing). Sentinel `human_task:inbox` defined in `capability_registry.py`, resolved/validated in `models/capability.py` (`KIND_HUMAN_TASK`).

**API — `backend/ai/task_inbox_api.py` (NEW):** `TaskInboxViewSet` (list/retrieve/approve/decline) + `TaskInboxStreamView` (SSE) + `InboxReadPermission`; `task_inbox_urls.py` mounted at `/carbon-api/ai/inbox/` in `config/urls.py`.

**Admin:** `HumanTaskAdmin` (read-only, list_display = consequence/status/required_authority/expires_at/decided_by/decided_at).

**Frontend:** `carbon-frontend/src/api/aiInbox.js` + `carbon-frontend/src/pages/admin/ai/HumanTaskInbox.jsx` (inbox list + approve/decline actions).

**Migration:** `backend/ai/migrations/0040_humantask.py` (deps `0039_runjournalentry`, real Django-generated, index names explicit and ≤30 chars).

**Tests — `backend/ai/tests/test_task_inbox.py` (NEW):** 9 tests covering the six done-when behaviours (approve mints a pinned grant; expired refused+marked; missing authority fail-closed; decline never mints; survives restart with identical fields; re-approve idempotent) + the boundary `task_enqueuer` seam.

### P3-10 — `invoke_skill` reimplementation

- `backend/ai/engine/agent/tools.py` — `execute_invoke_skill` (~L1376): resolves `process.id@version` via the registry, routes the run through `invoke_skill_via_boundary` (the host seam), and refuses legacy `kind` values that reach the tool.
- `backend/ai/host_executor.py` — `invoke_skill_via_boundary` (~L713): resolves the `ProcessDefinition`, builds the command, and routes through the command boundary with idempotency key `invoke_skill:{process_ref}:{principal}`.
- `backend/ai/pdp.py` — added `invoke_skill` action; `command_boundary_factory.py` registers `invoke_skill`.
- `backend/ai/engine/ports/process.py` — `ProcessDefinition` resolve `id@version`.
- **Tests — `backend/ai/tests/test_invoke_skill_boundary.py` (NEW):** 6 tests (registry resolve of `id@version`; boundary routing produces no direct run / PDP row for `invoke_skill`; legacy-kind refusal; idempotency key).

### Verification (Master Architect, terminal) — ✅ ALL GREEN
1. `test_task_inbox.py` → **9 passed** (fresh DB `--create-db`); `test_invoke_skill_boundary.py` → **6 passed**.
2. Combined Phase 3 suite (capability_loader + predicates + process_schema + grant + command_boundary + process_interview + registry_api + run_machine + reconciliation + step_journal + task_inbox + invoke_skill_boundary) `-q -m "not live" --create-db` → **134 passed**.
3. `manage.py check` → **0 issues**; `makemigrations ai --check --dry-run` → **No changes detected in app 'ai'**.
4. `import-boundary-lint.py` → **clean**; `forbidden-term-lint.py` → **clean**; `failopen-lint.py` → **clean**.

### Deviations / notes
1. **Double-dispatch collision resolved** — P3-09 was dispatched twice (once "go", once "go both"), producing two competing `HumanTask` schemas (`models/inbox.py` + `0040_human_task_inbox.py` vs `models/human_task.py` + `0040_humantask.py`) with inconsistent wiring. Consolidated onto the `human_task.py` / `TaskInbox` / `task_inbox_*` variant; deleted the `inbox.*` files and the stale `0040_human_task_inbox.py` migration; rewrote `0040_humantask.py` as a real Django migration matching the model.
2. **`--create-db` required** — because migration `0040` landed mid-session, the reused test DB was stale (missing `ai_humantask`), yielding `django.db.utils` errors under `--reuse-db`. Fresh DB (`--create-db`) is authoritative: **9 passed**. Lesson recorded: after any new migration lands, re-run tests with `--create-db`.
3. **The `task_enqueuer` seam is the P3-09 → P3-06 link** — the boundary grant stage defers to `enqueue_inbox_task` (which creates a pending `HumanTask`) rather than hard-refusing, so an unapproved high-stakes action becomes a durable inbox item instead of a silent refusal.
4. **`invoke_skill` routes entirely through the boundary** — no engine-side direct execution; the host seam (`invoke_skill_via_boundary`) is the only execution path, preserving RULE_20 / ADR-0007.
5. **Expiry side-effect rollback bug (found + fixed on re-verification)** — `_decide_locked`'s "mark expired" `task.save()` ran inside `approve()`/`decline()`'s `transaction.atomic()`, so the raised `TaskExpired` rolled the status write back and left the task stuck `pending` (surfaced as `test_expired_task_refuses` failing under `--reuse-db`). Fixed with `TaskInbox._mark_expired_outside_atomic`: persist `status=expired` (via a scoped `UPDATE … WHERE status=pending`) and raise `TaskExpired` *before* entering the atomic decide block, so the fail-closed side effect survives the caller's rollback.
6. **Frontend URL segment fix** — `carbon-frontend/src/api/aiInbox.js` called `ai/inbox/{id}/…`, but the backend routes carry a literal `tasks/` collection segment (`ai/inbox/tasks/<id>/…`, same convention as `registry`'s `processes/`). Added `BASE_TASKS = ai/inbox/tasks/` for list/retrieve/approve/decline; the SSE `stream/` stays at `ai/inbox/stream/`.

### Verification addendum (Master Architect, after fixes 5–6)
- `test_task_inbox.py` → **9 passed** (`--create-db` then `--reuse-db` both green); `test_invoke_skill_boundary.py` → **6 passed**.
- Combined Phase 3 suite (the 12 files above) `-q -m "not live" --create-db` → **134 passed**.
- `manage.py check` → **0 issues**; `makemigrations ai --check --dry-run` → **No changes detected**; `import-boundary-lint` / `forbidden-term-lint` / `failopen-lint` → **clean**.

## [2026-09-14] Master Architect — P3-11 (Cancellation vs compensate semantics)

**Role:** Master Architect (DeepSeek V4-Pro) · **Kind:** host-side run-lifecycle semantics. RULE_20 / ADR-0007 seam intact (`import-boundary-lint` clean).

### Delivered (backend-worker, verified by Master Architect)
- `backend/ai/pdp.py` — `_CANCEL_ACTIONS = frozenset({"cancel"})`, `_COMPENSATE_ACTIONS = frozenset({"compensate"})`, `_cancel_outcome` / `_compensate_outcome`, policies `permit-cancel-run` (ALLOW, "no further work will start") and `permit-compensate-effects` (ALLOW_WITH_CONFIRMATION, "reverses prior effects and requires separate approval").
- `backend/ai/command_boundary.py` — `LIFECYCLE_ACTIONS` table + `_command_requires_grant` / `_catalog_capability` gate `cancel` (no grant) vs `compensate` (grant required).
- `backend/ai/command_boundary_factory.py` — registers `cancel` + `compensate`; declaration shape `{"cancel": {requires_grant: False, required_capability: run.cancel}, "compensate": {requires_grant: True, required_capability: run.compensate}}`.
- `backend/ai/plans_service.py` — `_apply_cancel` (run → `cancelled`, skip only `planned`/`ready`/`awaiting_approval` steps, already-started steps untouched), `_apply_compensate` (writes `run.working_notes["compensation"]`), `cancel_plan` / `compensate_plan` (fail-closed through the boundary, idempotency keys `cancel:{run_id}` / `compensate:{run_id}`), `stop_plan` delegates to `cancel_plan`. ORM writes wrapped in `sync_to_async(..., thread_sensitive=True)`.
- `backend/ai/plans_api.py` — `PlanCompensateSerializer` + `compensate` `@action`; `backend/ai/plans_urls.py` — `ai-plan-compensate` route.
- **Tests — `backend/ai/tests/test_cancel_compensate.py` (NEW):** 8 tests (cancel transition + skip-not-started + PDP row; cancel idempotency; compensate fail-closed without grant; cancel-grant never authorizes compensate; compensate distinct PDP row + record; compensate unreachable via cancel path; 2 boundary-awareness tests).

### Fix applied during verification (Master Architect)
- **Test bug, not service bug** — `test_compensate_unreachable_via_cancel_path` created a run with `status="failed"` (terminal) then asserted `cancel_plan` flipped it to `cancelled`. The service is correct: `cancel_plan` no-ops on terminal states (`completed`/`failed`/`cancelled`) since "no further work" already holds. Fixed the test to use a cancellable run (`status="approved", run_state="ready"`).
- **Stale migration re-surfaced** — `backend/ai/migrations/0040_human_task_inbox.py` (old P3-09 schema) was still on disk alongside `0040_humantask.py`, causing a `makemigrations --check` conflict (two leaf nodes). Deleted the stale file; `makemigrations ai --check --dry-run` now clean.

### Verification (Master Architect, terminal) — ✅ ALL GREEN
1. `test_cancel_compensate.py` → **8 passed**; regression `test_run_machine.py` + `test_plans.py` → **51 passed**.
2. Clean rebuild `--create-db` (P3-09 + P3-10 + P3-11 + run_machine + plans) → **74 passed**.
3. `manage.py check` → **0 issues**; `makemigrations ai --check --dry-run` → **No changes detected in app 'ai'**.
4. `import-boundary-lint.py` → **clean**; `forbidden-term-lint.py` → **clean**; `failopen-lint.py` → **clean**.

## [2026-09-14] Master Architect — P3-05c (Registry + Review Queue screens)

**Role:** Master Architect (DeepSeek V4-Pro) · **Kind:** frontend admin screens driving the P3-05a registry backend. No `.ai-toolkit` violations; no SQLAlchemy.

### Delivered (frontend-worker, verified by Master Architect)
- `carbon-frontend/src/api/aiRegistry.js` (NEW) — `apiFetch` wrappers for all 11 registry endpoints (list/create/get/update/submit/publish/deprecate/diff/autonomy/set-autonomy/kill).
- `carbon-frontend/src/pages/admin/ai/ProcessRegistry.jsx` (NEW) — registry table + status tabs + New/Edit JSON dialog (client validation) + detail drawer (steps, objective, evidence/tests/kill counts, gated actions, structured diff, autonomy dial, kill switch).
- `carbon-frontend/src/pages/admin/ai/ReviewQueue.jsx` (NEW) — lists `status=review` processes and renders the **seven** review dimensions from real data: diff, rationale (objective), evidence, missing-evidence (derived), permissions-delta (derived from `diff.changed.steps`), tests, affected-runs (owner-scoped).
- `carbon-frontend/src/capabilities.js` — added `AI_PROCESS_OWNER`/`AI_PUBLISHER`/`AI_OPERATOR`/`AI_AUDITOR`.
- `carbon-frontend/src/App.jsx` — lazy imports + routes `/admin/ai/registry` + `/admin/ai/review-queue` (gated `AI_VIEW_CONSOLE`).
- `carbon-frontend/src/shell/ShellSidebar.jsx` — "Governance" group (Process Registry + Review Queue).
- `backend/ai/plans_service.py` — `_serialize_run` now includes `definition_id` (enables affected-runs filtering); `backend/ai/tests/test_plans.py` added `test_serialize_run_includes_definition_id`.

### Verification (Master Architect, terminal) — ✅ ALL GREEN
1. `backend/ai/tests/test_plans.py` → **41 passed** (incl. new `definition_id` test).
2. Frontend vitest `ProcessRegistry.test.jsx` + `ReviewQueue.test.jsx` → **15 passed**.
3. `manage.py check` → **0 issues**; `makemigrations ai --check --dry-run` → **No changes detected**; `import-boundary-lint`/`forbidden-term-lint`/`failopen-lint` → **clean**.
4. No compile/lint errors across the 6 touched frontend files (verified via diagnostics).

### Fixes / notes during verification
1. **Worker report said `kill-switch/` but code is correct (`kill/`)** — the actual `aiRegistry.js` `setKillSwitch` posts to `.../kill/` (matches `registry_urls.py`). Report-only inaccuracy; code verified correct.
2. **Pre-existing failure (NOT P3-05c)** — `src/__tests__/routes.test.jsx` "redirects bare /carbon to /carbon/chairman" fails because the `/carbon` redirect is wrapped in `<AppEnabledRoute>` (committed in HEAD) and the test's regex only matches a bare `<Navigate>` directly inside `element=`. The worker did not touch this route (git diff = 6 insertions only). Out of scope; flagging as a separate RULE_22 test-infra issue.

### Next
Phase 3 **complete** — all P3-01 … P3-12 DONE and verified. (See P3-12 below.)

---

## P3-12 — Pilot end-to-end (L, dep all above) — DONE ✅

### Delivered (qa-validator, test-only)
- `backend/ai/tests/pilot/__init__.py` (NEW) — package marker.
- `backend/ai/tests/pilot/test_pilot_e2e.py` (NEW) — 8 tests, all `not live` (restart survival ×2, concurrent-edit invalidation, duplicate submit ×2, revoked-permission publish, self-approval ×2).
- `carbon-frontend/tests/pilot-governance.spec.cjs` (NEW) — 5 Playwright tests (4 HTTP scenario flows + 1 UI smoke); env-driven (`CARBON_API_URL`/`CARBON_BASE_URL`/`CARBON_ADMIN_*`).

### Verification (Master Architect, terminal) — ✅ ALL GREEN
1. `backend/ai/tests/pilot/test_pilot_e2e.py` → **8 passed** (`-m "not live"`).
2. Pilot + `test_registry_api.py` together → **27 passed** (no interference; CI runs all `ai/tests/**` together).
3. Playwright spec vs live :8009/:5179 → **4/4 API scenario tests passed** (restart, duplicate-submit, revoked-permission, self-approval). UI smoke blocked locally only by missing `libnspr4.so` (CI's `npx playwright install --with-deps chromium` provides it); heading render confirmed at `<Typography variant="h5">`.
4. Gates: `manage.py check` **0 issues**; `makemigrations ai --check` **No changes detected**; `import-boundary-lint` **clean**; `failopen-lint` **clean**.
5. CI auto-pickup: backend job `python -m pytest` → `ai/tests/pilot/test_*.py`; e2e job `npx playwright test` → `*.spec.cjs`.

### Fixes / notes during verification
1. **Playwright account-provisioning contract verified against reality** — `accounts/urls.py` registers `users`/`groups`/`scoped-roles` (router); `UserSerializer` accepts `{username,password,is_active}`; `GroupSerializer` returns `id`; `ScopedRoleCreateSerializer` accepts `{user,group,org_unit,module,is_active}` (PKs) while list `ScopedRoleSerializer` returns `user`/`group` as StringRelatedField (username/name) — so the spec's `deactivateRole` (`r.user===username && r.group===groupName`) is correct. Superuser passes `AdminOrSuperuserOnly` for all three viewsets.
2. **`User.__str__` → username** confirmed, so StringRelatedField round-trips cleanly.
3. **Pre-existing flag (not P3-12)** — `forbidden-term-lint.py` now reports 5 hits in `backend/ai/engine/llm/prompts.py` (campus names `South Valley`/`Smart Village`/`Abu Qir`) — RULE_20 domain-agnostic violation in the uncommitted tree. Not touched by P3-12 (test-only). Needs a dedicated fix (move vocabulary into `domain_packs/carbon/vocabulary.yaml` + DomainPack port).
