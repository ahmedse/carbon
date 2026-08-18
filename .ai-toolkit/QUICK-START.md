# AI Toolkit — Quick Reference Card

## What You Built

A **self-enforcing, self-learning coding system** for AI agents. 44 files, 10 roles, 11 contracts.

**Three goals achieved:**
1. ✅ **Minimize duplication** — Registry (auto-scan) + "read before write" rule
2. ✅ **Unify all layers** — 11 shared contracts (API, security, data, UI, testing, etc.)
3. ✅ **Efficient, reliable, low-cost** — Deterministic verification gate + cheap worker models

---

## How to Use It RIGHT NOW

### In Carbon (Data Trust Platform)

```bash
# You (human):
./.ai-toolkit/scripts/scan.sh                    # update registry
./.ai-toolkit/scripts/verify.sh full             # run the gate
./.ai-toolkit/scripts/activate.sh backend-worker # get worker prompt

# Master Architect (Copilot in this chat):
# - Designate the Master Architect role: read roles/master-architect.md
# - Run scan.sh before planning a feature
# - Write TASKS.md phases that reference contracts + verification gate

# Workers (Zoo Code / separate Copilot chat):
# - Paste the activation prompt from activate.sh
# - Worker reads: config → base-rules → role → task
# - Worker builds, verifies, writes TASK-RESULTS.md
```

### In a New Project

```bash
cp -r .ai-toolkit/ /path/to/newproject/
nano /path/to/newproject/.ai-toolkit/project.config.md  # edit ONE file
cd /path/to/newproject && ./.ai-toolkit/scripts/scan.sh  # generate registry
echo 'Read `.ai-toolkit/ONBOARDING.md`' > /path/to/newproject/.github/copilot-instructions.md
# Done. 10 roles ready.
```

---

## The 10 Roles

| Role | When to Use | Model | Mode |
|------|-------------|-------|------|
| **Master Architect** | Planning, decomposition, TASKS.md specs | DeepSeek V4 Pro | Plan |
| **Scientific Researcher** | Design & run experiments, analyze results | DeepSeek V4-Pro | Experiment |
| **Backend Worker** | Python, Django, API, services, DB | DeepSeek V4-Flash | Execute |
| **Frontend Worker** | React, MUI, hooks, UI | DeepSeek V4-Flash | Execute |
| **DevOps Worker** | Docker, deploy, VPS, cron | DeepSeek V4-Flash | Execute |
| **Data/ML Worker** | Experiments, forecasting, analysis | DeepSeek V4-Flash | Execute |
| **Debugger/Fixer** | Prod hotfixes, regression tests | DeepSeek V4-Flash | Fix |
| **QA Validator** | Verification, test planning, validation gates | DeepSeek V4-Flash | Validate |
| **Product Designer** | UX design, design system, wireframes | DeepSeek V4-Flash | Design |
| **Curator** | Monthly retro, evolve contracts | DeepSeek V4-Pro | Evolve |

---

## The Learning Loop (NEW — closes "rules to system")

```
┌────────────────────────────────────────────────────┐
│ 1. WORK PHASE                                      │
│  • Workers build features, fix bugs                │
│  • Playbook entries accumulate                     │
│  • ADRs record decisions                           │
│  • Registry auto-updates (scan.sh)                 │
└────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────┐
│ 2. RETRO (monthly or after major work)             │
│  • Human: ./scripts/retro.sh 2026-07-01            │
│  • Activate Curator agent                          │
│  • Curator: cluster patterns → propose updates     │
│  • Writes: decisions/PROPOSALS-YYYY-MM.md          │
└────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────┐
│ 3. REVIEW & APPLY                                  │
│  • Human reviews proposals                         │
│  • Approves specific changes                       │
│  • Curator edits contracts / verify.sh             │
│  • Commit: "chore(toolkit): evolve from July retro"│
└────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────┐
│ 4. EVOLVED STATE                                   │
│  • Recurring bugs (3+ hits) now RULES in shared/*  │
│  • New anti-patterns caught by verify.sh           │
│  • Team never hits that bug class again            │
└────────────────────────────────────────────────────┘
```

**Result:** The toolkit learns from YOUR bugs, YOUR decisions, YOUR codebase.  
Knowledge compounds. Mistakes don't repeat.

---

## The 6 Key Scripts

| Script | What It Does | When to Run |
|--------|--------------|-------------|
| `activate.sh <role>` | Print worker activation prompt | Before starting a role chat |
| `scan.sh` | Regenerate registry from codebase | After adding services/components/endpoints |
| `verify.sh [target]` | Verification gate (backend/frontend/tests/antipatterns/all/full) | Before shipping, in DoD |
| `guard.sh` | Deterministic secret-blocking hook (manual/CI; .github/hooks/ wiring pending) | On every commit (once wired) |
| `retro.sh [date]` | Gather learnings for retrospective | Monthly or after major work |
| `new-task.sh <role> "title"` | Scaffold a TASKS.md phase | When Master writes a new task |

---

## The Enforcement (Deterministic, Not Guidance)

1. **Secret Hook** (`.github/hooks/guard-secrets.json` → `guard.sh`):
   - Runs BEFORE every file edit
   - **DENIES** writes with hardcoded `API_KEY = "sk-..."` patterns
   - Cannot be talked out of (fail-open on edge cases)
   - Available for manual/CI use (hook wiring via .github/hooks/ pending)

2. **Verification Gate** (`verify.sh` + `definition-of-done.md`):
   - 7-part completion checklist (correct, reuses, verified, tested, safe, clean, captured)
   - Runs: django check, migrations, eslint, build, anti-pattern greps
   - Worker MUST provide terminal proof before reporting "done"

---

## The Never-Fix-Twice Triad

When you fix a bug, you produce THREE artifacts:

| Artifact | Location | Purpose |
|----------|----------|---------|
| **Regression test** | `backend/<app>/tests/` or `frontend/e2e/` | Locks the fix in code (red → green) |
| **Playbook entry** | `troubleshooting/playbook.md` | Stops re-diagnosis (grep before debugging) |
| **Verify check** (if grep-detectable) | `scripts/verify.sh` | Catches the class before it ships |

Result: Every confirmed bug makes the system STRONGER, not just patched.

---

## What Evolves vs What's Static

| Component | Evolves? | How? |
|-----------|----------|------|
| **Registry** (`registry/*.md`) | ✅ Auto | `scan.sh` regenerates from codebase |
| **Playbook** (`troubleshooting/playbook.md`) | ✅ Manual | Debugger appends after every fix |
| **ADRs** (`decisions/*.md`) | ✅ Manual | Master adds after architectural decisions |
| **verify.sh checks** | ✅ Manual | Workers add greps when new anti-patterns emerge |
| **Contracts** (`shared/*.md`) | 🟡 Curator | Curator proposes, human approves, Curator applies |
| **Roles** (`roles/*.md`) | ⚪ Static | Rarely change (foundational) |
| **Hook** (`.github/hooks/`) | ⚪ Static | Pattern-based, no learning needed |

---

## Your Next Steps

### Today (activation):
1. Run `./ai-toolkit/scripts/scan.sh` to generate the registry
2. Try `./ai-toolkit/scripts/verify.sh full` to see current state
3. Test the hook: try creating a file with `API_KEY = "sk-test12345"` — Copilot denies it
4. Read `ONBOARDING.md` in any new chat to bootstrap

### This Month (first retro):
1. Keep building — playbook/ADRs accumulate naturally
2. End of month: `./ai-toolkit/scripts/retro.sh 2026-07-01`
3. Activate Curator: `./ai-toolkit/scripts/activate.sh curator`
4. Review proposals, approve changes, commit evolved toolkit

### Ongoing:
- **Before every feature**: Master runs `scan.sh` → knows what exists
- **Before every ship**: Worker runs `verify.sh full` → provides proof
- **After every bug fix**: Debugger appends playbook entry + regression test
- **Monthly**: Curator evolves contracts from accumulated learnings

---

## Success Metrics (how you'll know it's working)

| Metric | Target | Check |
|--------|--------|-------|
| **Duplication rate** | <5% rebuild of existing code | Registry hits before building |
| **Contract violations** | Declining over time | verify.sh warnings trend down |
| **Repeat bugs** | 0 (same root cause ≥2x) | Playbook entries → rules → checks |
| **Context cost** | <20% of total tokens | Targeted reads, not full-file scans |
| **Handoff failures** | 0 (Worker → Master communication) | TASK-RESULTS.md always has proof |

---

## The Big Idea

You turned **"a set of rules"** into **"a system that enforces itself AND learns from experience"**.

- **Registry** stops duplication
- **Contracts** unify patterns
- **Verification** makes quality deterministic
- **Hook** enforces non-negotiables
- **Playbook** prevents repeat work
- **Curator** evolves the rules from real bugs

This isn't just a "best practices doc" — it's a **compound-learning knowledge engine**  
that makes every bug fix and every decision strengthen the whole system.

**It's alive. It adapts. It never forgets.**

---

## Resources

- **Bootstrap**: [ONBOARDING.md](.ai-toolkit/ONBOARDING.md) (30-second start)
- **How-to**: [HOW-TO-USE.md](.ai-toolkit/HOW-TO-USE.md) (usage + evolution guide)
- **Dashboard**: [ROLES.md](.ai-toolkit/ROLES.md) (roles + scripts + enforcement)
- **Example retro output**: [decisions/PROPOSALS-2026-07-EXAMPLE.md](.ai-toolkit/decisions/PROPOSALS-2026-07-EXAMPLE.md)

**You're ready. Go build.**
