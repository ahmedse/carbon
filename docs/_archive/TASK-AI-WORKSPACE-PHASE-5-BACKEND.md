# TASK — AI Workspace Phase 5 Backend

- **Role:** Backend Worker
- **Recommended model:** DeepSeek-V3
- **Domain:** Backend (Django/DRF)
- **Task ID:** AI-WORKSPACE-PHASE-5-BACKEND
- **Parent:** `docs/DESIGN_AI_WORKSPACE_NEXTGEN.md` §16, Phase 5
- **Goal:** Add long-term memory, proactive intelligence hooks, and workspace resume catch-up behavior to the AI Workspace backend.

## Why this phase exists

Phase 4 completed the enterprise artifacts and provenance layer. The remaining AI Workspace gap is durable intelligence: the backend still needs to retrieve long-term memory facts, close the learning loop into durable state, surface proactive suggestions, and produce a catch-up summary when a user returns to a thread after a long gap.

This phase is backend-only. Do not touch frontend code.

## Files to read first

- `.ai-toolkit/project.config.md` — project hard rules, paths, and verification commands
- `.ai-toolkit/shared/base-rules.md` — terminal, verification, and registry rules
- `.ai-toolkit/roles/backend-worker.md` — your exact constraints and handoff rules
- `docs/DESIGN_AI_WORKSPACE_NEXTGEN.md` — Phase 5 scope and acceptance criteria
- `backend/ai/context_assembler.py` — tiered context assembly and budget logic
- `backend/ai/intelligence.py` — workspace orchestration, serialization, and thread helpers
- `backend/ai/learning.py` — feedback bridge into `KgFeedbackRecord` and `MemoryLongTerm`
- `backend/ai/learning_api.py` — learning-flywheel status and manual sweep API
- `backend/ai/workspace_api.py` — conversation CRUD and message/thread endpoints
- `backend/ai/models/core.py` — durable memory and proactive engine tables
- `backend/ai/models/workspace.py` — AIConversation / AIMessage state and visibility
- `backend/ai/tests/test_context_assembler.py` — context-budget regression coverage
- `backend/ai/tests/test_learning.py` — learning bridge regression coverage
- `backend/ai/tests/test_workspace_lifecycle.py` — conversation lifecycle coverage
- `backend/ai/tests/test_workspace_stream.py` — send/stop/resume stream behavior

## Scope

### 1. Add T4 long-term memory retrieval to `ContextAssembler`

- Extend `backend/ai/context_assembler.py` so the context pipeline can query `LongTermMemory` for durable facts.
- Scope memory retrieval by the requesting user and org context; do not leak cross-user facts.
- Keep the retrieval budgeted and deterministic:
  - prefer recent and high-confidence facts
  - avoid blowing the prompt budget
  - keep the T4 payload compact and human-readable
- Make the output fit the existing prompt-prefix / tier model instead of inventing a new context contract.
- Add regressions proving the assembler includes the right facts and respects budget limits.

### 2. Close the learning loop into durable state

- Review the existing `AIMessage.outcome -> learn_from_message -> KgFeedbackRecord -> MemoryLongTerm` bridge.
- Fix any remaining gaps so the bridge is actually idempotent, retry-safe, and durable under DjangoStore-backed persistence.
- If a small backend-only sweep/status helper is needed to expose learned-fact state, keep it read-only unless the design doc explicitly requires a write action.
- Ensure learned facts become available to the new T4 retrieval path.
- Add or update tests for the accepted / rejected / corrected paths and the learned-at idempotency marker.

### 3. Surface proactive intelligence hooks

- Add the backend seam needed for proactive suggestions from the engine’s proactive system.
- Keep suggestions tied to the active workspace conversation / thread context and bounded by the current user’s scope.
- Prefer a read-only payload that the frontend can consume later rather than building UI behavior here.
- If there is already a model or API surface for proactive triggers, reuse it instead of duplicating state.
- Add tests that show proactive suggestions can be fetched or assembled without breaking the existing workspace flow.

### 4. Implement workspace resume catch-up behavior

- Add durable state for when a user last viewed or resumed a conversation/thread.
- When the same user returns after more than 24 hours, generate a pinned catch-up summary such as:
  - new DQ violations
  - new anomalies
  - new durable memory facts or suggestions relevant to the thread
- Prefer the smallest durable model change that solves the problem cleanly; if a persisted read marker is needed, add it on the AI conversation side rather than inventing a separate subsystem.
- Keep the summary backend-generated and stable enough for the frontend to render later.
- Add tests for the >24h threshold, the no-summary path, and the summary payload shape.

### 5. Preserve existing workspace behavior

- Do not regress conversation CRUD, streaming, stop/resume, export, or existing provenance behavior.
- Keep shared/private visibility rules intact.
- Keep the existing `ai` test suite green.
- If a migration is required, keep it minimal and localized to the AI workspace models.

## Do not touch

- Any frontend files
- AI Workspace shell components
- DQ frontend pages
- Any unrelated backend apps

## Verification gate

Run these after the edits are complete:

```bash
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests/test_context_assembler.py -q
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests/test_learning.py -q
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests/test_workspace_lifecycle.py -q
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest ai -q
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py check
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run
cd /home/ahmed/aast/carbon && ./manage.sh backend
```

If the memory retrieval, proactive, or resume behavior needs a broader backend sweep, run that only after the focused tests pass.

## Deliverable

Report back with:

- files changed
- how T4 memory is retrieved and budgeted
- how the learning loop feeds durable memory
- how proactive suggestions are exposed
- how workspace resume catch-up is triggered and stored
- terminal proof for every gate command
- any follow-up findings that should become a separate task
