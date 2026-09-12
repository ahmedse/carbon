## Cross-Project Curation Mode

**When activated as Curator with a cross-project mandate, you also promote learnings between projects.**
Read this in addition to your project-local curation protocol.

### The loop you own
```
project playbooks (per-project bugs)
   → promote.sh drafts candidates (patterns in ≥2 projects)
   → you review against patterns/README.md contract
   → approved → patterns/index.md (UP-NNNN) → symlinked into ALL projects
   → if grep-detectable → add check to scripts/verify.sh
```

### Cross-project protocol
1. Run `~/ai-toolkit/scripts/promote.sh` — generates `patterns/CANDIDATES-<date>.md`.
2. For each candidate, verify the **root-cause class** (not just keyword) matches across projects — open each project's playbook entry and confirm the cause is the same.
3. Apply the promotion contract (project-agnostic, actionable, not already in a contract).
4. Promote approved patterns to `patterns/index.md` with a new `UP-NNNN` id, citing source projects.
5. If a pattern is really a framework rule → add it to `frameworks/<name>.md` instead.
6. If a pattern is really a universal contract rule → strengthen `shared/<contract>.md` instead.
7. Report: N candidates found, M promoted (with ids), K routed to contracts/frameworks.

### Guardrails
- Never promote a one-off, project-specific bug. Silos stay siloed unless the cause recurs.
- Never duplicate: if the lesson belongs in a contract/framework, put it there, not in patterns/.
- Patterns are for cross-cutting root causes that don't fit an existing contract.

---

*Source: ~/ai-toolkit/universal/cross-project-curation.md*
