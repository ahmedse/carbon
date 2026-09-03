# Shared Base Rules — All Roles, All Projects
# These rules apply regardless of role, project, or framework.
# Every role file references this document.

---

## 0. Do the Right Thing (Best Practice > Local Convention)

There are two kinds of truth in this toolkit — do not confuse them:

| Source | Describes | Authority |
|--------|-----------|-----------|
| `shared/*` contracts | The RIGHT way (portable best practice) | **How you SHOULD build** |
| `project.config.md`, `registry/`, existing code | What the project IS today (incl. tech debt) | **What currently EXISTS** |

- The existing codebase is **not automatically correct**. It contains known debt
  (e.g. legacy Grid syntax, `print()` instead of logging, naive datetimes, workarounds).
- When existing code conflicts with a `shared/*` contract → **follow the contract**,
  and flag the debt (playbook "Best practice note", or an Issue in TASK-RESULTS.md).
- Match existing patterns for **consistency of GOOD patterns** — never to propagate a bad one.
- Respect real CONSTRAINTS (a genuine platform limitation) — but a constraint is a fact to
  work within, not a license to copy an anti-pattern. If unsure which it is, ask the Master.
- "The code already does it this way" is NOT a justification. Do the right thing.

---

## 1. Activation Protocol (Every Session)

Before doing anything else:
1. Read `project.config.md` — learn the project's paths, commands, and HARD RULES
2. Read your role file — learn your constraints and verification gate
3. Read the assigned task (TASKS.md phase or user message)
4. Read every file listed in "Files to Read First" — BEFORE writing anything
5. Confirm your role: "Ready as [Role] for [Project]. Baseline check: [result of check command]"

---

## 2. Service Operations — ALWAYS Use the Project Ops Script (`manage.sh`)

**Universal law across ALL projects. This is the #1 anti-hang rule.**

Every project has a root ops controller script (default: `./manage.sh`).
See `project.config.md` → OPS_SCRIPT for this project's exact commands.

NEVER start, stop, or tail services with raw commands — they attach to the terminal
PTY and hang your session forever.

```bash
# WRONG — these hang the terminal / leak orphan processes
python manage.py runserver
npm run dev
vite
celery worker
tail -f logs/backend.log

# CORRECT — always via the ops script (detached, PID-tracked, port-cleaning)
./manage.sh start              # start full stack
./manage.sh start backend      # start one service (backend|frontend|worker|db)
./manage.sh stop [service]     # stop
./manage.sh restart [service]  # restart
./manage.sh status             # health + PID + port status
./manage.sh logs backend 100   # last 100 lines (bounded — never streams/hangs)
./manage.sh clean-ports        # free stuck ports
./manage.sh migrate            # run migrations
./manage.sh shell              # app/Django shell
```

**Rules:**
- READ logs: `./manage.sh logs <service> <N>` — bounded count, never `tail -f`.
- CHECK running state: `./manage.sh status` — never `ps`/`lsof` guessing.
- FREE a port: `./manage.sh clean-ports` — never broad `pkill`.
- If the ops script lacks a command you need, report to Master — do NOT improvise a raw server command.

---

## 3. Terminal Safety Rules

### Detach stdin for background processes
```bash
# WRONG — keeps PTY open → terminal hangs forever
nohup cmd >log 2>&1 &

# CORRECT — fully detached
nohup cmd >log 2>&1 </dev/null &
setsid cmd >log 2>&1 </dev/null &  # even better
```
Forbidden unguarded: `runserver`, `npm run dev`, `tail -f`, `watch`, `celery worker`
Use the ops script above; if you must background something, use `setsid` + `</dev/null`.

### Keep output bounded
```bash
# Pipe large output
git log | head -20
find . -name "*.py" | wc -l

# Disable pagers
git --no-pager log --oneline -10
```

### Never use broad kill patterns
```bash
# WRONG — kills unintended processes
pkill -f "python.*"

# CORRECT — kill by specific PID or name
kill $(cat /tmp/server.pid)
pkill -f "python.*manage.py runserver"
```

---

## 4. The Verification Loop (Mandatory)

**Every change must be proven by a tool, not described by the model.**

The verification loop:
```
1. [Pre-flight] Read current state → understand what exists
2. [Change] Make the scoped change
3. [Verify] Run the verification gate commands for your domain
4. [Report] Paste terminal output into TASK-RESULTS.md
```

**The verification gate is NOT optional.** A change that has no terminal proof is not complete.
If the verification command fails → fix before reporting. Never report "probably works."

One-shot gate: `./.ai-toolkit/scripts/verify.sh [backend|frontend|antipatterns|all]`
It runs the domain check + anti-pattern grep (hardcoded secrets, MUI v5 Grid, raw fetch, naive datetime).

---

## 5. Registry-First — Reuse Before You Build (anti-duplication)

**The #1 cause of wasted work is rebuilding something that already exists.**
Before creating ANY endpoint, service, model, component, hook, or config key:

```bash
# Regenerate the inventory (fast, safe to run anytime)
./.ai-toolkit/scripts/scan.sh

# Then SEARCH it before creating:
grep -i "<thing>" .ai-toolkit/registry/services.md     # backend service exists?
grep -i "<thing>" .ai-toolkit/registry/api.md          # endpoint exists?
grep -i "<thing>" .ai-toolkit/registry/components.md   # component exists?
grep -i "<thing>" .ai-toolkit/registry/models.md       # model/field exists?
grep -i "<KEY>"   .ai-toolkit/registry/config-keys.md  # config key exists?
```

Rules:
- If it exists → USE or EXTEND it. Never fork/duplicate.
- If a similar pattern exists → COPY that pattern for consistency.
- If you must create something new → follow the matching contract in `shared/`
  (`api-contract.md`, `data-layer.md`, `design-system.md`, `security.md`, `config.md`).
- After a structural change → re-run `scan.sh` so the registry stays current.

Also check `decisions/` for any ADR constraining the area before you change it.
Also check `patterns/index.md` — universal cross-project traps (`UP-NNNN`) other projects
already hit. Avoid them before writing; they are the distilled lessons of every project.

---

## 6. Read Before Write

NEVER edit a file you haven't read.
NEVER assume a function signature, import path, or variable name — read it first.
NEVER guess file structure — use search tools to find files before referencing them.

```
Wrong: "I'll add this to settings.py" → write without reading
Right: Read settings.py → find exact insertion point → write precisely
```

---

## 7. Scope Discipline

Stay within your assigned scope:
- If the task requires crossing into another domain → STOP, report to Master
- If you discover an adjacent bug → log it in TASK-RESULTS.md under "Issues Found", do NOT fix it
- If you're unsure of scope → report to Master, don't guess

---

## 8. Escalation Protocol

After **2 failed attempts** at the same approach, STOP and report:
```markdown
## BLOCKED: [what you were trying to do]
Attempts:
1. [command/approach] → [result]
2. [command/approach] → [result]
Hypothesis: [why this might be failing]
Needs: [what information or decision is needed from Master]
```

Do NOT spiral into more attempts. Report and wait.

---

## 9. Handoff Protocol (Master ↔ Worker)

**Canonical format:** `.ai-toolkit/universal/handoff.md`

### Quick Reference

**Master → Worker** (delegation prompt — copy-paste ready):
```
[ROLE] — Execute Phase N: [TITLE]

Read TASKS.md lines ~X to ~Y. N tasks. Domain: [backend|frontend|devops]

FILES TO READ FIRST:
- path/to/file.py — [why]

TASKS:
1. [TASK TITLE]
   - CREATE|MODIFY path/to/file: [exact change]
   - Verify: command → expected

DO NOT TOUCH:
- [explicit list]

GATES (run ALL before reporting):
  command → expected

HARD RULES:
- [project-specific rules from project.config.md]

REPORT BACK: task-by-task pass/fail, terminal proof, deviations.
```

**Worker → Master** (append to TASK-RESULTS.md):
```markdown
## [YYYY-MM-DD] [Role] — Phase N: [Title]

### Summary
N/N gates passed. X files changed. A tests.

### Task Results
| # | Task | Status | Notes |

### Files Changed
| Action | File | Lines | What |

### Verification Output
```
[paste terminal output]
```

### Deviations
[...or NONE]

### Issues Found
[...or NONE]
```

**Full details:** read `.ai-toolkit/universal/handoff.md` for rules, examples, and the complete cycle.

---

## 10. Security Non-Negotiables

- NEVER log secrets, tokens, passwords, or API keys — not in code, not in terminal output, not in TASK-RESULTS.md
- NEVER add `DEBUG=True` in production config
- NEVER add `0.0.0.0` or `*` to ALLOWED_HOSTS
- NEVER commit `.env` files
- NEVER hardcode credentials in code — use environment variables

---

## 11. Communication Style

- Short, factual status updates — not essays
- State what you DID, not what you WILL DO
- If uncertain: say so explicitly. Never hallucinate a file path or function name.
- When blocked: say "BLOCKED" clearly, don't silently try workarounds

---

## 12. Progress Reporting — Show Work in Real Time

**The #1 rule for user visibility. Report as you go — never buffer everything for the end.**

After EVERY significant operation, post the result immediately:

| After this | Report this |
|-------------|-------------|
| Running tests / lint / build | Full pass/fail counts, any FAILED lines |
| Creating a file | `Created path/to/file (NNN lines)` |
| Modifying a file | `Modified path/to/file — what changed` |
| Installing a package | `installed pkg==X.Y.Z — OK` |
| Something fails | Paste the ACTUAL error/traceback immediately, before fixing |
| Deploy / migration | Command + verification result |

Post short running-log messages, e.g.:
```
✅ tests/test_x.py — 10 passed
❌ tests/test_y.py — 1 FAILED: KeyError 'k' → fixing: added default
```
The user should see a running log of your work, not a wall of text at the end.

## 13. Handoff — Final Report Summarizes, Never Replaces

Deliver ONE final report at the end (files changed, verification output, decisions, known issues).
But the final report **SUMMARIZES what the user already saw step-by-step** — it does NOT
substitute for real-time reporting. Never save all output for a single end dump.

---

## 14. Model Serving Boundary (TurnKey ↔ source repos)

Datasets and model ops (train/eval/package) are done **local** in the source repo
(`healthy`, `gigacast`, `carbon`). **TurnKey owns serving, monitoring, registry, auth, and
everything else.** Never cross this line — TurnKey never reads a source DB or trains; the source
repo never runs a server or emits alerts.

- Rule: `universal/rules/model-serving-boundary.md`
- Procedure (onboard any model): `shared/model-serving-runbook.md`

---

## 15. Feature Rename / Rebrand Discipline

Renaming a user-facing feature (e.g. "AI Workspace" → "Pulse") is a **labeling** change,
NOT a route/contract change. Preserve the load-bearing seams so tests and integrations survive:

- **Keep stable**: route paths, API endpoints/contracts, and critical `aria-label`/role
  values that E2E selectors depend on (e.g. `Message input`, `Send message`, `New chat`).
- **Change only**: user-visible labels/titles/tooltips/empty-state copy, plus the logo/mark.
- **Verify leftovers by grep**: after the rename, grep the old string across `src/`.
  Internal code comments and `test`/`describe()` names MAY remain (non-user-facing);
  any USER-VISIBLE leftover is a defect (P3).
- **Update E2E assertions** to the new strings, then re-run the affected journeys.
- **Logo/brand assets**: theme tokens only (no raw hex/px); unique gradient `id`s per
  instance to avoid SVG id collisions when the mark mounts more than once.

Rationale: a rebrand that silently changes a route or an `aria-label` breaks E2E + deep
links + screen readers for zero functional gain. Label churn is cosmetic; seams are contract.

---

## 16. No Implementation Leakage in User-Facing Text (universal)

User-facing copy — UI labels, progress/status text, empty states, error messages,
assistant replies, and docs — must describe **outcomes**, never **internals**.

- Describe WHAT the user gets or WHAT is happening, not HOW the system computes it.
- Forbidden in user-facing strings: pipeline/engine mechanics ("translating to SQL",
  "analyzing table profile"), internal component names ("Pulse", "runner", "dispatch"),
  internal status codes ("provider_unavailable", "skipped_unavailable"), and
  provider/vendor jargon (unless a model selector is a deliberate user-facing feature).
- Prefer "Working on your answer…" over "Translating question to SQL…".
- Prefer "I couldn't reach the AI service — try again in a moment." over
  "AI provider is currently unavailable."
- Internal status codes and mechanics belong in logs and TASK-RESULTS, never in UI copy.

Rationale: internal mechanics are an implementation detail that changes freely. Surfacing
them couples UX copy to code and confuses users (they asked a question, not to watch a SQL
compiler). Exposing a model selector is a product decision, not a leak.
