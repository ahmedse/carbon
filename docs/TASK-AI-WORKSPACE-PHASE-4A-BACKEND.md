# TASK — AI Workspace Phase 4A Backend

- **Role:** Backend Worker
- **Recommended model:** DeepSeek-V3
- **Domain:** Backend (Django/DRF)
- **Task ID:** AI-WORKSPACE-PHASE-4A-BACKEND
- **Parent:** `docs/DESIGN_AI_WORKSPACE_NEXTGEN.md` §16, Phase 4-A
- **Goal:** Add enterprise governance artifacts to the AI Workspace backend: shared conversations, export permissions, artifact CRUD, and provenance metadata.

## Why this phase exists

Phase 3 completed the context layer. The backend still lacks the enterprise governance layer: shared conversations are not fully enforced, there is no AIArtifact model or CRUD API, and message serialization does not yet expose the provenance payload the frontend needs for the "Why?" tooltip.

This phase is backend-only. Do not touch frontend code.

## Files to read first

- `.ai-toolkit/project.config.md` — project hard rules, paths, and verification commands
- `.ai-toolkit/shared/base-rules.md` — terminal, verification, and registry rules
- `.ai-toolkit/roles/backend-worker.md` — your exact constraints and handoff rules
- `docs/DESIGN_AI_WORKSPACE_NEXTGEN.md` — Phase 4-A scope and acceptance criteria
- `backend/ai/models/workspace.py` — conversation/message models and existing visibility field
- `backend/ai/intelligence.py` — `_serialize_message`, `export_conversation`, workspace helpers
- `backend/ai/workspace_api.py` — conversation CRUD and export endpoints
- `backend/ai/serializers.py` — request/response serializers
- `backend/ai/tests/test_context_assembler.py` — export regression coverage already in place
- `backend/ai/tests/test_workspace_lifecycle.py` — conversation lifecycle regression coverage
- `backend/ai/tests/test_workspace_context.py` — mention/context contract coverage

## Scope

### 1. Add the AIArtifact model and migrations

- Create `AIArtifact` in `backend/ai/models/workspace.py`.
- Use the fields from the design doc:
  - `id`
  - `conversation`
  - `message` (nullable)
  - `title`
  - `artifact_type`
  - `content_json`
  - `visibility`
  - `created_at`
  - `created_by`
- Keep the model Carbon-owned and aligned with existing AI workspace conventions.
- Add the migration.
- Add any indexes needed for list browsing and org-scoped filtering.

### 2. Add artifact CRUD endpoints

- Add `GET /carbon-api/ai/workspace/artifacts/` and `POST /carbon-api/ai/workspace/artifacts/`.
- Add `GET /carbon-api/ai/workspace/artifacts/{id}/`, `PATCH`, and `DELETE`.
- Enforce the existing AI workspace permission model and visibility rules.
- Scope list queries to the requesting user / allowed shared conversations as appropriate.
- Keep the API response shapes straightforward for the frontend browser.

### 3. Enforce shared conversation visibility

- Keep `AIConversation.visibility` as the source of truth.
- Update conversation retrieval, export, and any helper paths so `visibility="shared"` behaves as the design doc describes:
  - shared conversations are readable by users in the same org
  - owner-only actions remain owner-only unless a higher capability is required
  - delete of shared conversations is capability-gated
- Do not relax visibility beyond the documented org scope.

### 4. Extend message provenance serialization

- Update `_serialize_message()` in `backend/ai/intelligence.py` so assistant messages include a `provenance` payload.
- Populate provenance from the fields already available on the message / conversation object:
  - model
  - scope snapshot
  - context snapshot
  - guard results
  - engine turn id
- Keep the payload stable and human-readable so the frontend can render it directly.
- Preserve the current `metadata_json` and `token_usage_json` behavior.

### 5. Preserve export behavior

- Keep the existing export `?fmt=` contract intact.
- Ensure export obeys the shared/private visibility rules.
- Preserve the JSON and Markdown formats already verified in the earlier phase.
- If any export permission check changes are needed, make them in the backend only.

### 6. Add regressions

- Add tests for artifact model/API behavior.
- Add tests for shared conversation read/write behavior.
- Add a test that `provenance` is present in serialized messages.
- Add a test that export obeys visibility rules.
- Keep the existing AI workspace regressions passing.

## Do not touch

- Any frontend files
- AI Workspace shell components
- DQ frontend pages
- Any unrelated backend apps

## Verification gate

Run these after the edits are complete:

```bash
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests/test_context_assembler.py -q
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests/test_workspace_lifecycle.py -q
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest ai -q
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py check
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run
```

If the artifact endpoints or visibility rules require a broader backend sweep, run that only after the focused tests pass.

## Deliverable

Report back with:

- files changed
- the artifact model/API added
- how shared visibility is enforced
- how provenance is serialized
- terminal proof for every gate command
- any follow-up findings that should become a separate task
