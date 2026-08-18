# AI Agent Toolkit — Role Dashboard

## How to Activate a Role

### Option A — Script (recommended)
```bash
# List all roles
./.ai-toolkit/scripts/activate.sh

# Print the activation prompt for a role
./.ai-toolkit/scripts/activate.sh backend-worker
# → copy the output → paste into Zoo Code / any chat window
```

### Option B — Manual paste
Tell the agent:
> "Your role is **[ROLE]**. Read `.ai-toolkit/project.config.md` then `.ai-toolkit/roles/[ROLE].md` to learn your exact rules and constraints. Confirm by stating your role."

---

## Role Reference

**Model policy (budget directive, 2026-08-18):** all worker roles (backend, frontend, devops, data-ml, debugger-fixer, qa-validator, product-designer) run **DeepSeek V4-Flash**; researcher + curator + Master Architect run **DeepSeek V4-Pro**. Kimi / V3 / R1 are RETIRED on the provider — never reference them.

| Role | File | Recommended Model | Cognitive Mode | Tools |
|------|------|-------------------|---------------|-------|
| **Master Architect** | `roles/master-architect.md` | DeepSeek V4 Pro | Plan + Decompose | read, search, edit, todo |
| **Scientific Researcher** | `roles/researcher.md` | DeepSeek V4-Pro | Experiment + Analyze | read, search, edit, terminal |
| **Backend Worker** | `roles/backend-worker.md` | DeepSeek V4-Flash | Execute (Python/Django) | read, edit, terminal |
| **Frontend Worker** | `roles/frontend-worker.md` | DeepSeek V4-Flash | Execute (React/MUI) | read, edit, terminal |
| **DevOps Worker** | `roles/devops-worker.md` | DeepSeek V4-Flash | Execute (Docker/VPS) | read, edit, terminal |
| **Data/ML Worker** | `roles/data-ml-worker.md` | DeepSeek V4-Flash | Execute (Data/ETL) | read, edit, terminal |
| **Debugger/Fixer** | `roles/debugger-fixer.md` | DeepSeek V4-Flash | Diagnose + Hotfix | read, edit, terminal |
| **QA/Validator** | `roles/qa-validator.md` | DeepSeek V4-Flash | Validate + Evidence (4-layer) | read, search, browser, terminal |
| **Product/UX Designer** | `roles/product-designer.md` | DeepSeek V4-Flash | Discover + Design (story/journey/acceptance) | read, search, edit |
| **Curator** | `roles/curator.md` | DeepSeek V4-Pro | Evolve + Reason | read, search, edit (contracts) |

---

## Shared Files (Read by All Roles)

| File | Purpose |
|------|---------|
| `project.config.md` | **Project-specific facts** — edit this per project |
| `shared/base-rules.md` | Universal rules: ops script, terminal, verification, handoff protocol |
| `shared/design-system.md` | Enterprise UI/UX constitution — Frontend Worker + Master (UI planning) |
| `shared/api-contract.md` | Unified API shape — Backend Worker (writing), Frontend Worker (consuming) |
| `shared/security.md` | Auth, access control, secrets, OWASP — Backend/DevOps/Debugger |
| `shared/data-layer.md` | DB & data conventions — Backend/Data-ML/Debugger |
| `shared/config.md` | Env/prod config, no hardcoding — all workers |
| `shared/testing.md` | Test pyramid, regression-first, run commands — all workers |
| `shared/debugging.md` | Debugging methodology + never-fix-twice loop — Debugger/Fixer |
| `shared/logging.md` | Observability & logging standard — Backend/DevOps/Debugger |
| `shared/git-workflow.md` | Commit/branch conventions — all workers |
| `shared/definition-of-done.md` | The universal completion gate — all workers |

## Troubleshooting (Never Fix the Same Bug Twice)

| File | Purpose |
|------|---------|
| `troubleshooting/playbook.md` | Known issues → root cause → verified fix (grep before debugging) |
| `troubleshooting/incident.md` | Prod-down runbook: stabilize → diagnose → fix → prevent |
| `troubleshooting/README.md` | How the playbook + tests + verify.sh work together |

Every confirmed bug fix produces a **triad**: a regression test (locks it in code),
a playbook entry (stops re-diagnosis), and — if class-detectable — a `verify.sh` grep.

## Registry (Auto-Generated — the Anti-Duplication Engine)

| File | Lists |
|------|-------|
| `registry/api.md` | All API endpoints & @action routes |
| `registry/services.md` | Backend services + management commands |
| `registry/models.md` | All data models |
| `registry/components.md` | Frontend components, hooks, API modules |
| `registry/config-keys.md` | Every env/config key |

**Regenerate anytime:** `./.ai-toolkit/scripts/scan.sh`
**Consult BEFORE building anything** — reuse by name, never rebuild what exists.

## Decisions (ADRs)

`decisions/` — architectural decisions recorded once, never re-debated.
Read relevant ADRs before touching an area. Master owns them.

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/activate.sh <role>` | Print a role's activation prompt to paste into a chat |
| `scripts/new-task.sh <role> "<title>"` | Scaffold a TASKS.md phase |
| `scripts/scan.sh [section]` | Regenerate the registry from the codebase |
| `scripts/verify.sh [target]` | Verification gate: backend/frontend/tests/antipatterns/all/full |
| `scripts/guard.sh` | Blocks hardcoded secrets — manual/CI use; PreToolUse hook (`.github/hooks/`) NOT wired yet |
| `scripts/retro.sh [since-date]` | Gather learnings for retrospective (playbook + ADRs + current warnings) |

## Toolkit Evolution (the Learning Loop)

The toolkit **captures** learnings but doesn't auto-update rules. Here's the feedback loop:

### Automatic (no human needed)
- **Registry**: `scan.sh` regenerates it from the codebase → always current
- **Hook enforcement**: NOT wired yet (pending) — `guard.sh` runs manually/CI until `.github/hooks/` is created

### Worker-added (manual append)
- **Playbook entries**: Debugger/Fixer adds after every confirmed fix (RULE 9 in debugging.md)
- **ADRs**: Master adds after architectural decisions
- **verify.sh checks**: Any worker adds when a new anti-pattern class emerges

### Periodic evolution (Curator + human review)
Every month (or after major work), run a **retrospective**:
```bash
# 1. Gather learnings since last retro:
./.ai-toolkit/scripts/retro.sh 2026-06-01

# 2. Activate the Curator:
./.ai-toolkit/scripts/activate.sh curator
# (paste prompt into a chat)

# 3. Tell Curator: "Review learnings since YYYY-MM-DD"
# Curator clusters patterns, proposes contract updates

# 4. Review proposals in: decisions/PROPOSALS-YYYY-MM.md
# Approve specific proposals

# 5. Tell Curator: "apply proposal CUR-NNNN"
# Curator edits the contracts
```

**Result:** Recurring bugs (3+ occurrences) become **rules** in `shared/*` or **checks** in `verify.sh`.  
The toolkit evolves from your team's actual experience, not generic best-practice docs.

## Enforcement (deterministic, not guidance)

- **Guard hook is NOT wired yet (pending).** `.github/hooks/guard-secrets.json` does not exist,
  so nothing runs before edits today. `scripts/guard.sh` is available for manual use and can be
  wired into CI or a PreToolUse hook later — once wired, it **denies** writes that introduce a
  hardcoded secret. This is the one piece that cannot be talked out of.
- `scripts/verify.sh` is the completion gate — see `shared/definition-of-done.md`.

---

## The Protocol

```
Master Architect (Copilot)
  → writes TASKS.md phase spec
  → specifies: role, model, files to read, verification commands

Worker (Zoo Code)
  → reads: project.config.md + base-rules.md + role file + TASKS.md phase
  → executes: scoped change only
  → verifies: runs the verification gate
  → writes: TASK-RESULTS.md update

Master Architect (Copilot)
  → reads TASK-RESULTS.md
  → reviews verification output
  → decides next phase
```

---

## Copying to a New Project

```bash
cp -r .ai-toolkit/ /path/to/new-project/
# Then edit ONE file:
nano /path/to/new-project/.ai-toolkit/project.config.md
# Done. All roles are ready.
```
