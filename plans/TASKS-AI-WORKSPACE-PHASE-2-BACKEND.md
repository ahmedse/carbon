# TASKS.md — Phase 2: AI Workspace Backend Residuals

**Role:** Backend Worker  
**Model:** DeepSeek-V3  
**Domain:** backend  
**Primary context:** [docs/AI_WORKSPACE_ARCHITECTURE.md](../docs/AI_WORKSPACE_ARCHITECTURE.md), [plans/CARBON_AI_WORKSPACE_PHASED_PLAN.md](CARBON_AI_WORKSPACE_PHASED_PLAN.md), [plans/CARBON_AI_WORKSPACE_EXECUTION_DELTA.md](CARBON_AI_WORKSPACE_EXECUTION_DELTA.md)

Read the phase spec in full. This phase has 1 task. Keep scope narrow and backend-only.

FILES TO READ FIRST:
- backend/ai/migrations/0002_alter_aiconversation_conversation_type.py — current migration state for AI conversation type choices
- backend/ai/models.py — AIConversation model definition and current choices
- backend/ai/tests/test_workspace_messages.py — backend AI workspace behavior coverage
- backend/ai/tests/test_intelligence.py — backend AI orchestration coverage
- backend/ai/tests/test_protocol.py — response-shape coverage if normalization changes are needed

TASKS:

1. FINALIZE AI CONVERSATION TYPE RESIDUALS
   - REVIEW backend/ai/migrations/0002_alter_aiconversation_conversation_type.py and confirm it matches the current AI conversation_type choices
   - MODIFY backend/ai/models.py only if the model and migration have drifted; keep the choice set synchronized with the migration
   - If backend response-shape normalization is still needed for AI workspace conversations, fix it in the backend AI layer only
   - Do not touch frontend AI workspace files, shell files, DQ editor files, or generated task-result files
   - Verify: backend AI tests pass and Django reports no migration drift

DO NOT TOUCH:
- carbon-frontend/**
- TASK-RESULTS-*.md files
- docs/AI_WORKSPACE_ARCHITECTURE.md
- plans/CARBON_AI_WORKSPACE_PHASED_PLAN.md
- plans/CARBON_AI_WORKSPACE_EXECUTION_DELTA.md

GATES (run ALL in order before reporting done):
  cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests -q → backend AI test suite passes
  cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py check → system checks pass
  cd /home/ahmed/aast/carbon/backend && /home/ahmed/aast/carbon/.venv/bin/python manage.py makemigrations --check --dry-run → no migration drift
  cd /home/ahmed/aast/carbon && bash ./.ai-toolkit/scripts/verify.sh backend → backend gate passes

HARD RULES (project-specific):
- Backend-only phase: do not touch frontend files.
- Keep the scope to AI workspace backend residuals only.
- Do not edit generated task-result files.
- Follow the AI contract and security guardrails in `.ai-toolkit/shared/ai-contract.md`.

REPORT BACK:
List each task with ✅ pass / ❌ fail, test count, terminal proof, and any deviations from spec.
