# Handoff Protocol — Master ↔ Worker Delegation

**This is the canonical format for all Master-to-Worker delegation and Worker-to-Master completion reports.** Every project, every phase. Copy-paste the template, fill in the blanks.

---

## Part A: Master → Worker (Delegation Prompt)

The Master Architect writes a **copy-paste-ready prompt** for the Worker.
The prompt MUST be self-contained — the Worker should not need to ask the Master for clarification.

### Template

```
[ROLE] — Execute Phase N: [TITLE]

Read TASKS.md lines ~X to ~Y for the full spec. N tasks. Domain: [backend|frontend|devops|...]

FILES TO READ FIRST:
- path/to/file.py — [why]
- path/to/other.py — [why]

TASKS:

1. [TASK TITLE — short, verb-led]
   - CREATE path/to/file.py: [what goes in it]
   - MODIFY path/to/existing.py: [exact change — add X, remove Y, wrap Z]
   - Verify: command → expected output

2. [TASK TITLE]
   - ...

DO NOT TOUCH:
- path/to/never/touch.py
- any/file/outside/scope/

GATES (run ALL in order before reporting done):
  command → expected result
  command → expected result

HARD RULES (project-specific):
- Rule 1 (e.g. "No Redis. No Celery.")
- Rule 2

REPORT BACK:
List each task with ✅ pass / ❌ fail, test count, terminal proof, and any deviations from spec.
```

### Rules for Writing Delegation Prompts

| Rule | Explanation |
|------|-------------|
| **One task = one change focus** | A task should be completable in one edit session. Not "Wire all 8 pages" — break into one per page. |
| **Exact file paths** | Never "the router file" — always `turnkey/training/router.py` |
| **Exact commands + expected output** | "`python -m pytest tests/ -q` → 0 failures" not "run tests and check" |
| **DO NOT TOUCH is mandatory** | Prevents scope creep. Workers fix adjacent bugs unless explicitly told not to. |
| **GATES are the contract** | If a gate fails, the phase is not done. Period. |
| **HARD RULES are per-project** | From `project.config.md` — repeat the ones that apply to this phase. |
| **Keep it under 200 lines** | If your delegation prompt exceeds 200 lines, the phase is too big — split it. |

### Example (Good)

```
BACKEND WORKER — Execute Phase 17: Production Readiness

Read TASKS.md lines ~9615 to ~10090. 5 tasks. Backend + 1 frontend file.

FILES TO READ FIRST:
- turnkey/main.py — app setup, lifespan
- turnkey/training/scheduler.py — background training
- web/vite.config.js — dev proxy

TASKS:

1. FIX TRAILING SLASH 404
   - MODIFY turnkey/main.py: add redirect_slashes=False to FastAPI()
   - MODIFY web/vite.config.js: proxy configure() hook strips trailing slashes
   - Verify: curl http://localhost:8007/api/v1/training/runs/ → 200

2. WEBSOCKET TRAINING PROGRESS
   - CREATE turnkey/training/ws.py: TrainingProgressManager + ws_router
   - MODIFY turnkey/training/scheduler.py: push events at state transitions
   - MODIFY turnkey/main.py: include_router(training_ws_router)
   - Verify: connect WebSocket, start training → see status events

...

DO NOT TOUCH:
- docker-compose.yml (no Docker in dev)
- web/src/ (except vite.config.js)

GATES:
  curl http://localhost:8007/api/v1/training/runs/ → 200
  python -m pytest tests/ -q → 0 failures
  npm run lint -- --max-warnings 0 → clean

HARD RULES:
- No Redis. No Celery. No Yatai.
- No Docker in dev.
- API keys SHA-256 hashed.

REPORT BACK:
List each task with ✅/❌, test count, terminal proof, deviations.
```

### Example (Bad — too vague)

```
Please fix all the bugs and add the WebSocket stuff. Run the tests afterward.
```

---

## Part B: Worker → Master (Completion Report)

The Worker appends to `TASK-RESULTS.md` using this exact format.

### Template

```markdown
## [YYYY-MM-DD] [Role] — Phase N: [Title]

### Summary
N/N gates passed. X files changed (Y created, Z modified). A tests passed, B failed, C skipped.

### Task Results
| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | Task title | ✅ | X files, Y tests |
| 2 | Task title | ✅ | Z files changed |
| 3 | Task title | ❌ | [why — see deviations] |

### Files Changed
| Action | File | Lines | What |
|--------|------|-------|------|
| CREATE | `path/to/new.py` | 120 | Description |
| MODIFY | `path/to/existing.py` | +5/-3 | Description |

### Verification Output
```
[paste EXACT terminal output from gate commands]
```

### Deviations
[What you did differently from the spec and WHY. NONE if you followed the spec exactly.]

### Issues Found
[Bugs or problems you noticed but did NOT fix (scope discipline). NONE if clean.]
```

### Rules for Completion Reports

| Rule | Explanation |
|------|-------------|
| **Paste terminal output** | Not "tests passed" — paste the actual `pytest` output. Master verifies the counts. |
| **Deviations require justification** | If you changed the spec, explain WHY. "The backend doesn't have that endpoint" is valid. "I thought this was better" is not. |
| **Issues Found ≠ fixed** | Adjacent bugs go here. Do NOT fix them unless the spec says to. |
| **Never claim a gate passed if it didn't** | A red X is better than a lie. Master can adjust the spec. |
| **Report AFTER real-time progress** | During execution, report step-by-step (`✅ task 1 done, 10 tests`). The completion report is the summary. |

---

## Part C: The Full Cycle

```
MASTER                            WORKER
  │                                  │
  │  1. Write Phase N spec in        │
  │     TASKS.md                     │
  │                                  │
  │  2. Generate delegation prompt   │
  │     using Part A template ──────→│
  │                                  │  3. Read spec + prompt
  │                                  │  4. Execute tasks
  │                                  │     Report progress in real time
  │                                  │  5. Run all gates
  │                                  │  6. Append Part B report to
  │                                  │     TASK-RESULTS.md
  │                                  │
  │←──── Worker reports "done" ──────│
  │                                  │
  │  7. Verify: read TASK-RESULTS.md │
  │     Check gate output matches    │
  │     Spot-check key files         │
  │  8. Report: VERIFIED or REJECTED │
  │                                  │
```

---

## Part D: Real-Time Progress (During Execution)

Workers: do NOT save all output for the completion report. Report after every significant operation:

```
✅ Created turnkey/training/ws.py — 98 lines
✅ Modified scheduler.py — added 3 progress_manager.push() calls
❌ pytest tests/test_training.py — 1 FAILED: test_optuna — study name collision
   → Fixing: added uuid study names
✅ Fixed. 0 failures.
✅ curl trailing slash — 200 OK
📦 npm run build — 1012 modules, 3.5s
```

The completion report **summarizes** what the user already saw step-by-step.

---

*This is the universal handoff protocol. Every project in the AI Toolkit uses this format. Update it here — it propagates to all projects.*
