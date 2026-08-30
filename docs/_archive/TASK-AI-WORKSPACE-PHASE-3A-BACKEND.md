# TASK — AI Workspace Phase 3A Backend

- **Role:** Backend Worker
- **Recommended model:** DeepSeek-V3
- **Domain:** Backend (Django/DRF)
- **Task ID:** AI-WORKSPACE-PHASE-3A-BACKEND
- **Parent:** `docs/DESIGN_AI_WORKSPACE_NEXTGEN.md` §16, Phase 3-A
- **Goal:** Finish the backend context-engineering seam for AI Workspace: mention-aware context assembly, budget telemetry, and summary-compaction memoization.

## Why this phase exists

The AI Workspace backend already has the Phase 2 conversation lifecycle, `send_message_stream`, `summarize_conversation`, and `context_snapshot_json` plumbing. What is still incomplete for Phase 3 is the context-engineering layer: workspace mentions are not yet represented in the protocol, the tiered assembler does not yet inject mention descriptors into T1 context, and conversation summary compaction does not yet have a durable memoization marker.

This phase must extend the existing implementation. Do not recreate the workspace stack.

## Files to read first

- `.ai-toolkit/project.config.md` — project hard rules, paths, and verification commands
- `.ai-toolkit/shared/base-rules.md` — terminal, verification, and registry rules
- `.ai-toolkit/roles/backend-worker.md` — your exact constraints and handoff rules
- `docs/DESIGN_AI_WORKSPACE_NEXTGEN.md` — Phase 3-A scope and acceptance criteria
- `backend/ai/protocol.py` — `WorkspaceContext`, `ConversationContext`, scope contract
- `backend/ai/context_assembler.py` — current tiered assembler implementation
- `backend/ai/intelligence.py` — `send_message`, `send_message_stream`, `summarize_conversation`
- `backend/ai/models/workspace.py` — conversation/message models and summary fields
- `backend/ai/tests/test_context_assembler.py` — current regression coverage
- `backend/ai/workspace_api.py` — summarize/export workspace endpoints

## Scope

### 1. Make `WorkspaceContext` mention-aware

- Extend `WorkspaceContext` in `backend/ai/protocol.py` so it can carry sanitized `mentions` data from the source workspace.
- Keep the dataclass pure and framework-free.
- Update `from_dict()` to accept the new field without breaking existing callers.
- Keep `to_prompt_prefix()` compact and human-readable; it should mention the current workspace, view, entity, intent, recent actions, and a short mention summary when present.

### 2. Complete tiered context assembly

- Update `backend/ai/context_assembler.py` so T1 includes structured workspace context plus resolved mention descriptors.
- The assembler must continue to cap verbatim history to the most recent `recent_turns`.
- Preserve the existing summary-first behavior, but make summary compaction budget-aware instead of blindly prepending summary in every case.
- Keep T3/T4 as reserved retrieval seams if they remain stubs for now, but do not fake engine calls.
- Preserve `context_snapshot_json` token-budget telemetry and keep the per-tier keys stable.

### 3. Add a durable memoization marker for summary compaction

- Extend `AIConversation` in `backend/ai/models/workspace.py` with a field that records the last message used for summary compaction, so summarization can skip work when nothing changed.
- Use a clear name such as `last_summarized_message_id`.
- Add the migration.
- Update `summarize_conversation()` in `backend/ai/intelligence.py` to:
  - skip recompute when the summary source has not changed and `force=False`
  - refresh the memoization marker when the summary is regenerated
  - keep the current deterministic fallback if the cheap summary seam is not yet wired

### 4. Add/adjust regressions

- Add a regression for mention-aware context assembly.
- Add a regression that proves summary compaction is skipped when no new messages were added.
- Keep the existing context-budget and `context_snapshot_json` assertions intact.
- Add any migration-safe test coverage needed for the new memoization field.

## Do not touch

- Anything under `carbon-frontend/`
- Any AI workspace UI components
- Any DQ UI or route changes
- Any unrelated backend apps

## Verification gate

Run these after the edits are complete:

```bash
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests/test_context_assembler.py -q
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests/test_workspace_lifecycle.py -q
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py check
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run
```

If those pass and the scope stayed local, run the broader backend AI suite:

```bash
cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest ai -q
```

## Deliverable

Report back with:

- files changed
- the exact mention/compaction behavior implemented
- migration added or not added
- terminal proof for every gate command
- any follow-up findings that should become a separate task
