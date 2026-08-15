# TASKS.md — Phase 1: Frontend DQ Editor Polish

**Domain:** frontend  
**Worker:** Frontend Worker  
**Model:** Kimi K3 (or the project’s standard frontend worker model)  
**Primary context:** [plans/CARBON_AI_WORKSPACE_EXECUTION_DELTA.md](CARBON_AI_WORKSPACE_EXECUTION_DELTA.md), [docs/AI_WORKSPACE_ARCHITECTURE.md](../docs/AI_WORKSPACE_ARCHITECTURE.md)

Read TASKS.md lines 1-120 for the full spec. 3 tasks. Domain: frontend.

FILES TO READ FIRST:
- carbon-frontend/src/components/dq/RuleJsonEditor.jsx — current Monaco editor implementation and stale comment/header text
- carbon-frontend/src/pages/dq/tabs/RulesTab.jsx — import surface and create-dialog usage
- carbon-frontend/src/pages/dq/tabs/DefinitionTab.jsx — import surface and save/transfer usage
- carbon-frontend/src/__tests__/PlatformHome.test.jsx — repo test style reference

TASKS:

1. CLEAN UP RULEJSONEDITOR MODULE BOUNDARIES
   - MODIFY carbon-frontend/src/components/dq/RuleJsonEditor.jsx: update the header comment so it no longer says textarea; keep the component focused on Monaco Editor semantics
   - CREATE carbon-frontend/src/components/dq/ruleJsonValidation.js: move RULE_TYPES, RULE_LEVELS, DIMENSION_CODES, SEVERITY_VALUES, validateDefinitionClient, normalizeServerErrors, and EMPTY_DEFINITION_TEMPLATE into this module
   - MODIFY carbon-frontend/src/components/dq/RuleJsonEditor.jsx: import those helpers/constants from the new module and export only the component (or any truly component-local constants that are not causing react-refresh warnings)
   - MODIFY carbon-frontend/src/pages/dq/tabs/RulesTab.jsx and carbon-frontend/src/pages/dq/tabs/DefinitionTab.jsx only as needed to follow the new import path
   - Verify: frontend lint stays clean and no react-refresh warning is introduced by the helper split

2. ADD A MONACO WIRED TEST
   - CREATE carbon-frontend/src/components/dq/__tests__/RuleJsonEditor.test.jsx: test the editor wiring with a mocked `@monaco-editor/react` component
   - Assert that the component renders, passes the JSON value through, and registers the dq rule schema diagnostics in `beforeMount`
   - Keep the test focused on Monaco/schema wiring; do not test unrelated DQ flows here
   - Verify: targeted vitest run for the new test file passes

3. CLEAN UP STALE DOCUMENTATION TEXT
   - MODIFY carbon-frontend/src/components/dq/RuleJsonEditor.jsx: remove any lingering textarea wording in comments or tooltip text and make the copy match the Monaco editor implementation
   - Preserve current behavior and visual layout; this is a polish-only pass
   - Verify: the editor still builds and the DQ frontend test suite passes

DO NOT TOUCH:
- backend/ai/**
- backend/ai/migrations/**
- carbon-frontend/src/shell/**
- TASK-RESULTS-*.md files
- docs/AI_WORKSPACE_ARCHITECTURE.md
- plans/CARBON_AI_WORKSPACE_PHASED_PLAN.md

GATES (run ALL in order before reporting done):
  cd /home/ahmed/aast/carbon/carbon-frontend && npm test -- src/components/dq/__tests__/RuleJsonEditor.test.jsx → new test passes
  cd /home/ahmed/aast/carbon/carbon-frontend && npm run build → build passes
  cd /home/ahmed/aast/carbon && bash ./.ai-toolkit/scripts/verify.sh frontend → gate passes

HARD RULES (project-specific):
- Frontend-only phase: do not touch backend files.
- Keep the change minimal and warning-free; do not widen scope to AI workspace cleanup.
- Do not edit generated task-result files.

REPORT BACK:
List each task with ✅ pass / ❌ fail, test count, terminal proof, and any deviations from spec.