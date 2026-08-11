# START HERE — AI Toolkit Bootstrap (read this first, 30 seconds)

This folder (`.ai-toolkit/`) is a portable enterprise dev system for AI coding agents
(Copilot + Zoo Code/Cline). It makes many models, on many roles, produce consistent,
verified, non-duplicated work.

## If you are an AI agent starting a session

1. You have a ROLE. If you weren't told which, ask. Roles: master-architect, researcher,
   backend-worker, frontend-worker, devops-worker, data-ml-worker, debugger-fixer, curator,
   qa-validator.
2. Read, in order:
   - `project.config.md` — this project's paths, commands, HARD RULES
   - `shared/base-rules.md` — universal rules (esp. §0 "do the right thing", ops script, verify)
   - `shared/design-patterns.md` — how we compose objects (14/23 GoF adopted)
   - `shared/compact-ui.md` — MUI density spec (fonts, spacing, sidebar, component overrides)
   - `roles/<your-role>.md` — your exact constraints + verification gate
3. Consult before building: `registry/` (what exists — run `scripts/scan.sh`), `troubleshooting/playbook.md` (known bugs).
4. Confirm: "Ready as <role> for <project>." Then start the task.

## If you are the human

```bash
# Print the paste-ready activation prompt for a role:
./.ai-toolkit/scripts/activate.sh backend-worker

# Regenerate the codebase inventory:
./.ai-toolkit/scripts/scan.sh

# Run the verification gate:
./.ai-toolkit/scripts/verify.sh full
```

## The mental model

| Layer | Files | Answers |
|-------|-------|---------|
| **Roles** | `roles/*` | WHO does the work + their limits |
| **Rules** | `shared/base-rules.md` | HOW everyone must behave |
| **Patterns** | `shared/design-patterns.md` | HOW we compose objects (14/23 GoF) |
| **Contracts** | `shared/{api-contract,security,data-layer,config,design-system,logging,testing,git-workflow,qa-framework}.md` | The RIGHT way per concern |
| **Registry** | `registry/*` (generated) | WHAT already exists (anti-duplication) |
| **Decisions** | `decisions/*` | WHY it's built this way (ADRs) |
| **Troubleshooting** | `troubleshooting/*` | Known bugs + incident runbook |
| **Gate** | `shared/definition-of-done.md` + `scripts/verify.sh` | WHEN it's actually done |
| **Config** | `project.config.md` | This project's specifics (the only file you edit per project) |

## Two truths (don't confuse them)
- `shared/*` = best practice (how you SHOULD build) — **authoritative**.
- `project.config.md` + existing code = what IS today, including tech debt.
- When they conflict → follow best practice, flag the debt. Existing code is not automatically right.

## The workflow
```
Master Architect  → writes TASKS.md phase (role, files, contract, verification gate)
Worker            → reads config + base-rules + role + registry + task → builds → verifies
Worker            → writes TASK-RESULTS.md (files + terminal proof + issues)
QA/Validator      → reads qa-framework + task → validates at 4 layers → TASK-RESULTS.md
Master Architect  → reviews proof, decides next phase
```

## Copy to a new project
```bash
cp -r .ai-toolkit/ /path/to/new-project/
# edit ONE file: .ai-toolkit/project.config.md   (roles are generic — they read it)
# run: ./.ai-toolkit/scripts/scan.sh
```

## How it learns and evolves
The toolkit captures learnings (playbook + ADRs + registry auto-update), but doesn't auto-update rules.
Run a **monthly retrospective**: `scripts/retro.sh` → activate Curator → review proposals → approve → evolve contracts.
Recurring bugs (3+ hits) become rules. The system learns from your team's actual mistakes. See `HOW-TO-USE.md` for details.
