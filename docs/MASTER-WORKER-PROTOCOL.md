# Master-Worker Protocol v2.0

> Save this file. Use it in any project. Copy-paste the worker prompts below into DeepSeek Flash sessions.

---

## How It Works

```
You (Human)
  │
  ├─→ Master (DeepSeek V4 Pro / Copilot) — Architect, reviewer, integrator
  │     │
  │     ├─→ Worker BE (DeepSeek Flash) — Backend code
  │     └─→ Worker FE (DeepSeek Flash) — Frontend code
  │
  ▼
Review gates → Approve → Integrate → Git commit
```

| Role | Who | Does |
|---|---|---|
| **You** | Human | Copy prompts to workers, run builds, git commits |
| **Master** | Copilot (DeepSeek V4 Pro) | Survey codebase, write TASK files, review results, integrate |
| **Worker BE** | DeepSeek Flash session | Backend: models, APIs, serializers, tests |
| **Worker FE** | DeepSeek Flash session | Frontend: pages, components, routing, state |

---

## File Structure (in any project)

```
plans/<project>-phase/
  PROTOCOL.md              ← Rules (adapted per project)
  SHARED-CONTEXT.md        ← Models, APIs, patterns (both workers read this)
  MASTER-PLAN.md           ← Phased roadmap
  phase-00-components/
    TASK-FE-00.md          ← Shared component library task
    TASK-RESULTS-FE-00.md
  phase-01-<feature>/
    TASK-BE-01.md
    TASK-FE-01.md
    TASK-RESULTS-BE-01.md
    TASK-RESULTS-FE-01.md
  phase-02-<feature>/
    ...
```

---

## 5 Review Gates (Master checks before approving)

| Gate | What | Fail = |
|---|---|---|
| 1. Syntax | File parses, build passes | Reject, worker fixes |
| 2. Contract | API/page matches TASK spec exactly | Reject, worker fixes |
| 3. Test | Evidence provided (curl, pytest, screenshot) | Reject, ask for evidence |
| 4. Integration | BE + FE contracts align | Reject, adjust contract |
| 5. Style | Follows conventions in PROTOCOL.md | Reject with notes |

---

## Universal DO's (all projects, all workers)

- DO read SHARED-CONTEXT.md before starting ANY task
- DO follow existing code patterns — don't invent new ones
- DO add docstrings/comments on all new functions
- DO scope queries by org/tenant where applicable
- DO write tests for new endpoints
- DO append results to TASK-RESULTS.md immediately on completion
- DO confirm files are saved before declaring done

## Universal DON'Ts (all projects, all workers)

- DON'T touch files outside assigned scope
- DON'T change existing API signatures without master approval
- DON'T remove or rename existing models/fields
- DON'T introduce new dependencies without master approval
- DON'T leave console.log/debug prints in production code
- DON'T create files larger than 400 lines — extract sub-modules
- DON'T skip error handling

---

## Worker Prompt Templates

### How to use these:

1. Master creates `TASK-BE-NN.md` and `TASK-FE-NN.md`
2. You open TWO DeepSeek Flash sessions
3. Copy **Worker BE Prompt** into session 1 + paste the TASK file content
4. Copy **Worker FE Prompt** into session 2 + paste the TASK file content
5. Workers produce `TASK-RESULTS-*.md` — paste back to Master
6. Master reviews, approves/rejects, integrates

---

### Worker BE Prompt

````text
You are Worker BE — a backend engineer. You will receive a TASK file from the master architect. Your job is to execute it exactly.

Before starting:
1. Read the SHARED-CONTEXT.md file attached/provided to understand the codebase
2. Read the TASK file completely — note the DO and DON'T sections
3. Plan your changes before writing any code

While working:
- Follow existing code patterns exactly
- Match the API contract in the TASK file precisely (method, path, request shape, response shape)
- Include docstrings on all new functions/classes
- Write tests for new endpoints
- Keep files under 400 lines — extract sub-modules if needed
- Do NOT introduce new dependencies without asking
- Do NOT touch files outside the scope listed in the TASK

When done:
1. Fill out the TASK-RESULTS file completely
2. Include exact file paths changed/created
3. Include test evidence (curl commands + output, or pytest output)
4. Note any issues or decisions made
5. Confirm all acceptance criteria are met

Output format: Paste the completed TASK-RESULTS file. Include all code you wrote inline.
````

---

### Worker FE Prompt

````text
You are Worker FE — a frontend engineer. You will receive a TASK file from the master architect. Your job is to execute it exactly.

Before starting:
1. Read the SHARED-CONTEXT.md file attached/provided to understand the codebase
2. Read the TASK file completely — note the DO and DON'T sections
3. Plan your changes before writing any code

While working:
- Use the existing API client helper for all API calls
- Use the existing auth context for user/role info
- Use shared components from src/components/ — NEVER create ad-hoc tables or cards
- Use MUI sx prop only — no inline style={{}}
- Support light + dark theme (use theme.palette)
- Handle all 4 states: loading, data, empty, error
- Keep pages under 200 lines — components handle the complexity
- Do NOT introduce new npm dependencies without asking
- Do NOT touch files outside the scope listed in the TASK

When done:
1. Fill out the TASK-RESULTS file completely
2. Include exact file paths changed/created
3. Run `npm run build` and include the output
4. Describe all 4 states (loading, data, empty, error)
5. Note any issues or decisions made
6. Confirm all acceptance criteria are met

Output format: Paste the completed TASK-RESULTS file. Include all code you wrote inline.
````

---

## TASK File Template (Master → Worker)

```markdown
# TASK-XX-NN: [Title]

## Context (from master)
[Why this task exists, what phase, what depends on it]

## Before starting
- Read SHARED-CONTEXT.md completely
- Read PROTOCOL.md DO/DON'T sections
- [Any other prerequisites]

## Scope — DO
- [Exact deliverable 1]
- [Exact deliverable 2]

## Scope — DO NOT
- [Thing explicitly out of scope]
- [File not to touch]

## API Contract (BE tasks)
| Method | Endpoint | Purpose |
|---|---|---|
| GET | /api/v1/xxx/ | Description |

Request: none
Response:
{
  "field": "type"
}

## Page Contract (FE tasks)
| Route | Component | States |
|---|---|---|
| /xxx | XxxPage | loading, data, empty, error |

## Components to use (FE tasks)
- `<SharedComponent>` from `src/components/`

## Files to create/modify
| File | Action |
|---|---|
| path/to/file.py | CREATE |
| path/to/file.py | MODIFY |

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Build passes
- [ ] Tests pass

## Deliverables
1. TASK-RESULTS file filled completely
2. All code inline or paths listed
3. Test evidence
```

---

## TASK-RESULTS Template (Worker → Master)

```markdown
# TASK-RESULTS-XX-NN: [Title]

## Summary
[2-3 sentences describing what was done]

## Files Changed
| File | Action | Lines |
|---|---|---|
| path/to/file.py | CREATE | 45 |
| path/to/file.py | MODIFY | +12 |

## API Endpoints (BE)
| Method | Endpoint | Status |
|---|---|---|
| GET | /api/v1/xxx/ | Working |

## Test Evidence
```
[pytest output or curl commands + responses]
```

## Build Output (FE)
```
[npm run build output]
```

## Issues / Decisions
[Anything the master should know]

## Checklist
- [ ] All acceptance criteria met
- [ ] Build passes
- [ ] Tests pass
- [ ] No breaking changes
```

---

## UI/UX Conventions (for any project)

| Decision | Rule |
|---|---|
| **Density** | Compact: `size="small"` inputs, 24px table rows, 16px card padding |
| **Colors** | Blue primary + Zinc/slate neutrals. Light + dark themes. |
| **Typography** | System font stack. No custom fonts. No Google Fonts. |
| **Cards** | `border: 1px solid divider`, 8px radius, NO shadow |
| **Tables** | One shared DataGrid component. Never ad-hoc tables. |
| **Page width** | Full fluid — no max-width |
| **Animations** | Hover color shifts only, <200ms |
| **Empty states** | Icon + title + description + CTA button |
| **Forms** | Single column, labels above, save bar pinned bottom |
| **Loading** | Skeleton matching layout shape |
| **Errors** | Alert at top with retry button, never toast-only |

---

## Quick Start (new project)

1. Open Copilot Chat, type `/bootstrap-protocol`
2. Master surveys codebase and creates all files in `plans/<name>-phase/`
3. Review MASTER-PLAN.md — adjust phases if needed
4. Open 2 DeepSeek Flash sessions
5. Copy-paste Worker BE prompt + TASK-BE-01.md → Session 1
6. Copy-paste Worker FE prompt + TASK-FE-00.md → Session 2 (components first!)
7. Workers deliver results → Master reviews → Approve/reject
8. Repeat for Phase 02, 03, ...
