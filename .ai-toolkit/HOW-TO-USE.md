# How to Use the AI Toolkit — Quick Start

## In THIS Project (Carbon Data Trust Platform)

The toolkit is installed and ready. Here's how to use it:

### For you (the human):

```bash
# Regenerate the registry anytime you add/rename files:
./.ai-toolkit/scripts/scan.sh

# Run the verification gate before shipping:
./.ai-toolkit/scripts/verify.sh full

# Get a worker activation prompt:
./.ai-toolkit/scripts/activate.sh backend-worker
# (copy-paste that output to a Zoo Code/Cline chat to activate the worker)

# Check if a bug is already documented:
grep -i "<symptom>" .ai-toolkit/troubleshooting/playbook.md
```

### For Copilot (this chat):

You're already using it. When you start a session:
1. You're Master Architect by default (`.github/copilot-instructions.md` says so).
2. Read `.ai-toolkit/ONBOARDING.md` if you're new or lost.
3. Before planning a feature, run `.ai-toolkit/scripts/scan.sh` — know what exists.
4. Write specs in `TASKS.md` that reference the relevant `shared/*` contract + verification gate.
5. Workers (you in another mode, or Zoo Code) execute phases, verify, write `TASK-RESULTS.md`.

### The workflow loop:

```
You (Master)      → write TASKS.md phase (role, files to read, contract, gate)
Worker (Zoo/You)  → read config + role + registry → build → verify → TASK-RESULTS.md
You (Master)      → review proof → next phase OR done
```

### The enforcement is available but NOT wired:

The secret-blocking script (`scripts/guard.sh`) exists and works, but the hook
(`.github/hooks/guard-secrets.json`) does NOT exist yet — nothing runs before edits today.
You can test guard.sh manually (see "Testing It Works" below) and wire it into CI or a
PreToolUse hook later (wiring pending).

---

## In a NEW Project

```bash
# 1. Copy the toolkit:
cp -r /path/to/carbon/.ai-toolkit /path/to/newproject/

# 2. Edit ONE file (this is the only project-specific file):
vim /path/to/newproject/.ai-toolkit/project.config.md
# Change: PROJECT_NAME, paths, backend/frontend commands, hard rules

# 3. Generate the registry for the new codebase:
cd /path/to/newproject
./.ai-toolkit/scripts/scan.sh

# 4. Wire it to Copilot (create or edit):
echo 'Read `.ai-toolkit/ONBOARDING.md` first. You are Master Architect for the Carbon Data Trust Platform.' \
  > /path/to/newproject/.github/copilot-instructions.md

# Done. All 10 roles are ready. (The guard hook is NOT wired by default — see above.)
```

The toolkit is **100% portable** — the roles/contracts/scripts don't hardcode project paths.
They read `project.config.md`, so you edit one file and everything adapts.

---

## When Something Changes

| You changed | Run this |
|-------------|----------|
| Added a service / component / endpoint | `./.ai-toolkit/scripts/scan.sh` (update registry) |
| Fixed a non-trivial bug | Append entry to `troubleshooting/playbook.md` |
| Made an architectural decision | Add ADR to `decisions/` |
| Added a grep-detectable anti-pattern class | Add a check to `scripts/verify.sh` |
| The codebase violates a `shared/*` rule | Fix toward best practice, flag as debt |

---

## Testing It Works

```bash
# 1. Does the guard block secrets?
python3 -c 'import json; print(json.dumps({"toolName":"create_file","toolInput":{"content":"API_KEY=\"sk-test123456789012\""}}))'  \
  | ./.ai-toolkit/scripts/guard.sh
# Expect: permissionDecision: deny

# 2. Does verify catch anti-patterns?
./.ai-toolkit/scripts/verify.sh antipatterns
# Should flag MUI v5 Grid debt, naive datetime, print() calls

# 3. Does scan work?
./.ai-toolkit/scripts/scan.sh
cat .ai-toolkit/registry/services.md | head -20
# Should list your real backend services
```

---

## How the Toolkit Learns and Evolves

The toolkit **captures** every lesson but doesn't auto-update rules. Here's how it adapts:

### Automatic (happens on every use)
- **Registry** (`registry/*.md`): `scan.sh` regenerates from codebase → always current
- **Guard script** (`scripts/guard.sh`): blocks secrets when run — manual/CI only until `.github/hooks/` is wired (pending)

### Worker-added (manual append after fixes/decisions)
- **Playbook** (`troubleshooting/playbook.md`): Debugger appends after every confirmed bug fix
- **ADRs** (`decisions/*.md`): Master adds after architectural decisions
- **verify.sh checks**: Workers add greps when new anti-pattern classes emerge

### Periodic evolution (close the learning loop)
**Every month or after major work, run a retrospective:**

```bash
# 1. Gather recent learnings:
./.ai-toolkit/scripts/retro.sh 2026-06-01
# Shows: playbook entries, ADRs, verify.sh warnings, root-cause clusters

# 2. Activate the Curator agent:
./.ai-toolkit/scripts/activate.sh curator
# (copy-paste that prompt into a new chat)

# 3. Tell Curator: "Review learnings since 2026-06-01"
# Curator reads playbook + ADRs, clusters patterns, proposes updates

# 4. Curator writes proposals to: decisions/PROPOSALS-YYYY-MM.md
# Review proposals (which contracts to update, which verify checks to add)

# 5. Approve specific proposals:
# "Apply proposal CUR-0001"
# Curator edits the relevant shared/*.md or scripts/verify.sh

# 6. Commit the evolved toolkit:
git add .ai-toolkit/shared/ .ai-toolkit/scripts/
git commit -m "chore(toolkit): evolve contracts based on July retro"
```

**Result:**  
Recurring bugs (3+ occurrences) → become **rules** in `shared/*.md`  
Recurring anti-patterns → become **checks** in `verify.sh`  
Cross-cutting decisions → elevate to `base-rules.md` or a contract

The toolkit evolves from **your team's actual experience**, not generic docs. The Curator identifies patterns, the human reviews and approves, the system captures it forever.

---

## Summary: The Full Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│ 1. WORK: Master plans → Workers build → verify → ship       │
│    • Playbook entries accumulate                            │
│    • ADRs record decisions                                  │
│    • Registry stays current (scan.sh)                       │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. RETRO (monthly): Curator reviews learnings               │
│    • Clusters recurring issues                              │
│    • Proposes contract updates                              │
│    • Human approves → Curator applies                       │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. EVOLVED: Toolkit now enforces new rules                  │
│    • Next worker sees updated contracts                     │
│    • verify.sh catches the anti-pattern class               │
│    • Team never hits that bug again                         │
└─────────────────────────────────────────────────────────────┘
```

The toolkit is now a **living system** that learns from your mistakes and compounds knowledge over time.
