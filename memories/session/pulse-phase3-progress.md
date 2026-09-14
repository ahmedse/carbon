# Pulse Phase 3 — Progress Memory (Second Master)

**Owner:** Second Master (Phase 3), parallel to Gate 2 master.
**Updated:** 2026-09-13

## Coordination contract (binding)
- One verifier at a time — the test DB (`test_carbon_dev`, Postgres) is shared via `--reuse-db`.
- Split tracking: this master writes `TASKS-PHASE3.md` + `TASK-RESULTS-PHASE3.md` only. Never edit `TASKS.md`, `TASK-RESULTS.md`, or `domain_packs/` (Gate 2 master's).
- `domain_packs/` + the `DomainPack` port are Gate 2 master's P2-08 handoff; **handoff received 2026-09-13** → P3-01 → P3-02 → P3-03 now own the `api_catalog.yaml` `capabilities:` list + `processes/dq.rule.release.yaml`.
- Seam invariant (RULE_20 / ADR-0007): `ai/engine/` MUST NOT import `ai.command_boundary`, `ai.command_boundary_factory`, `ai.protocol`, `ai.pdp`, or `ai.adapters`. Run `python3 .ai-toolkit/scripts/import-boundary-lint.py` after ANY engine edit.
- Never docker in dev. Never SQLite. Always timezone-aware datetimes (`django.utils.timezone.now()`).

## Completed
- **P3-05b** — five governance roles as CBAC capabilities (`ai:process_owner`, `ai:policy_owner`, `ai:publisher`, `ai:operator`, `ai:auditor`) + `AI_VIEW_CONSOLE` (`ai:view_console`, pre-existing) mapped in `GROUP_CAPABILITIES`; role group-name constants in `accounts/constants.py` (folded into `PROTECTED_GROUPS` + `ALL_CANONICAL_GROUPS`, left global); `AIViewConsolePermission` (SAFE_METHODS only) in `ai/permissions.py`. `ScopedRole` unchanged (works as-is).
- **P3-06** — `ApprovalGrant` model (`ai/models/approval.py`, `AppScopeMixin`, `app_label="ai"`, exact-match `find_active`, `canonicalize_args`); host-side `ai/grant.py` resolver (writes `stage="grant"` refusal rows); boundary `grant` stage inserted after `consent` (STAGES 13→14); `PolicyDecisionRow.stage` field (default `"pdp"`); factory wiring; `ToolDef.requires_grant`; migrations 0031/0032; admin.
- **P3-01** — `Capability` model + loader (`ai/models/capability.py`, `AppScopeMixin`, `app_label="ai"`, UUID pk, `capability_id` Text unique); import-free `ai/capability_registry.py` (host_action key → `module:qualname` / `human_task:inbox` sentinel); lazy `importlib` `resolve_host_action` fail-closed; `api_catalog.yaml` `capabilities:` list (4 pilot caps); migration 0033.
- **P3-02** — `ai/predicates.py` `dq_rule_active_revision_matches_approved_revision` (fail-closed, reads `definition` dict → mapping → attributes); pilot contracts `dq.rule.validate/review/publish/active_revision_matches_approved_revision`.
- **P3-03** — `ai/models/process.py` `ProcessDefinition` + hand-rolled `validate_definition` (jsonschema NOT in requirements) + `ai/process_schema.json` (canonical draft-07) + `processes/dq.rule.release.yaml` + migration 0034.
- Static validation: `get_errors` clean on all 15 touched files. No engine file touched (seam preserved).

## Pending verification (run when terminal available; coordinate with Gate 2 master per §0.1)
1. `pytest accounts/tests/test_capability_rbac_extensive.py -q -m "not live"`
2. `pytest ai/tests/test_command_boundary.py ai/tests/test_grant.py -q -m "not live"`
3. `python3 .ai-toolkit/scripts/import-boundary-lint.py`
4. `python manage.py makemigrations --check --dry-run` && `python manage.py check`
> ⚠️ `test_grant.py` needs `ai_approvalgrant` + `ai_policydecisionrow.stage`. With `--nomigrations --reuse-db`, a stale shared test DB must be dropped/recreated first (or run once without `--reuse-db`).

## Key design decisions (do not re-litigate)
- Grant stage = position 8 (after `consent`, before `budget`). `STAGES` is 14.
- Three-concept separation is strict: PDP (authorization, stage 6) ≠ grant (business approval, stage 8) ≠ consent (RULE_21, stage 7). A PDP ALLOW does NOT waive `requires_grant`.
- Grant resolution is host-side and injected (`grant_resolver=`) — the engine never imports `ai.models`.
- `requires_grant` defaults `False` (fail-closed) on `Command` and `ToolDef`; readable from dict catalog entries too.
- The five governance roles are intentionally non-overlapping (no `IMPLIES` edges); `ai_auditor_group` carries `ai:view_console` directly.

## Blocked / waiting
- **P3-09** (Human Task Inbox → writes `ApprovalGrant`) — depends on P3-07a; the `dq.rule.review` capability's `host_action: human_task:inbox` sentinel is already reserved for it.
- **P3-05a** publish path — `dq.rule.publish` currently shares `dq.services:run_single_rule` with `validate`; needs a dedicated `publish_rule` host action + a real `DQRule` revision source (the verify predicate reads `definition` dict defensively; `DQRule` has NO `approved_revision`/`active_revision` fields).
