# Carbon AI Workspace — Execution Delta

**Date:** 2026-08-12  
**Status:** Master Architect execution delta  
**Canonical references:** [docs/AI_WORKSPACE_ARCHITECTURE.md](../docs/AI_WORKSPACE_ARCHITECTURE.md), [plans/CARBON_AI_WORKSPACE_PHASED_PLAN.md](CARBON_AI_WORKSPACE_PHASED_PLAN.md)

## 0. Why this exists

The architecture is already unified. What remains is execution drift:
- DQ rule unbind + Monaco editor work is functionally complete, but a few polish items remain
- AI Workspace is real, but the follow-up changes split across frontend, backend, and generated work logs
- the repo still carries legacy task-result noise that should stay out of the final product surface

This delta turns that state into a clean execution sequence.

## 1. What is complete

### DQ rule track
- bindings are optional, not required
- client validation matches backend behavior
- RuleJsonEditor uses Monaco Editor
- Monaco loads the JSON schema for diagnostics/autocomplete
- DQ backend and frontend gates pass

### AI Workspace track
- conversation persistence exists
- workspace REST API exists
- task transfer context exists
- AI workspace shell exists
- DQ pages can launch AI workspace tasks
- the AI workspace architecture has been unified in docs

## 2. What is still in motion

### Frontend cleanup
- stale textarea comments in RuleJsonEditor
- RuleJsonEditor helper/constants export layout still creates react-refresh noise
- Monaco editor behavior lacks a dedicated UI test

### AI workspace residuals
- backend/ai/migrations/0002_alter_aiconversation_conversation_type.py
- carbon-frontend/src/shell/AIConversationView.jsx
- carbon-frontend/src/shell/AITaskTransferContext.jsx (if any follow-up normalization is still pending)

### Generated work logs
- TASK-RESULTS-* files are execution evidence, not product deliverables

## 3. Recommended execution order

### Phase 1 — Frontend DQ editor polish
**Worker:** Frontend Worker  
**Goal:** finish the Monaco migration cleanly.

Scope:
- update stale comments in RuleJsonEditor
- move helper/constants out of the component file to remove react-refresh warnings
- add a focused UI test for Monaco/schema wiring

Do not touch:
- backend AI files
- AI workspace shell files
- task-result / generated report files

Gate:
- frontend test covering the editor
- `npm run build`
- `bash ./.ai-toolkit/scripts/verify.sh frontend`

### Phase 2 — AI Workspace backend residuals
**Worker:** Backend Worker  
**Goal:** finalize any remaining persistence / migration / API normalization work.

Scope:
- backend/ai/migrations/0002_alter_aiconversation_conversation_type.py
- any backend normalization still needed for conversation persistence or response shape handling

Do not touch:
- frontend DQ editor files
- generated task-result files

Gate:
- backend AI tests relevant to the touched files
- `python manage.py check`
- `bash ./.ai-toolkit/scripts/verify.sh backend`

### Phase 3 — AI Workspace frontend residuals
**Worker:** Frontend Worker  
**Goal:** finish the workspace shell cleanup and any remaining UI normalization.

Scope:
- carbon-frontend/src/shell/AIConversationView.jsx
- carbon-frontend/src/shell/AITaskTransferContext.jsx if the remaining changes still need normalization

Do not touch:
- RuleJsonEditor polish files from Phase 1
- backend files
- generated task-result files

Gate:
- targeted frontend tests for the shell
- `npm run build`
- `bash ./.ai-toolkit/scripts/verify.sh frontend`

### Phase 4 — Docs and evidence hygiene
**Owner:** Master Architect review, not implementation

Decision:
- keep task-result files as evidence if you want execution traceability
- do not promote them into canonical docs
- archive or exclude them from the final shipped deliverable if the repo should stay visually clean

## 4. Decision summary

1. Keep AI Workspace as a separate track from the original DQ editor task.
2. Keep the Monaco DQ editor cleanup in frontend scope.
3. Keep backend and frontend AI workspace residuals in separate worker phases.
4. Keep generated task-result files out of the canonical documentation surface.

## 5. Success definition

The repo is in the right state when:
- the DQ editor is polished, test-covered, and warning-free
- the AI workspace track is split cleanly by domain
- canonical docs point at one architecture and one execution plan
- generated work logs remain evidence, not clutter
