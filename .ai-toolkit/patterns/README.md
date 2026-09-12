# Cross-Project Patterns — The Learning Organism

**This is where a lesson learned in ONE project becomes knowledge for ALL projects.**

Per-project `troubleshooting/playbook.md` files capture bugs local to that project.
When the **same root-cause class** appears in **2 or more projects**, it stops being a
project quirk and becomes a **universal pattern** — it gets promoted here, and because
`patterns/` is symlinked into every project, every agent everywhere now avoids it.

```
project A playbook  ─┐
project B playbook  ─┼─►  curator sees it twice  ─►  promote to patterns/  ─►  symlinked into ALL projects
project C playbook  ─┘         (promote.sh helps)         (index.md)              (agents read on activation)
```

## The Promotion Contract

A playbook entry is promoted to a universal pattern when ALL are true:
1. The **same root-cause class** appears in **≥2 projects** (not the same symptom — the same *cause*).
2. It is **project-agnostic** — the lesson holds regardless of framework/domain (or is scoped to a framework already in `frameworks/`).
3. It is **actionable** — states the trap AND the correct practice.

## What does NOT get promoted
- One-off bugs specific to a single project's data or architecture → stays in that project's playbook.
- Anything already enforced by a `shared/` contract or `frameworks/` module → strengthen that instead.

## How to promote
1. Run `scripts/promote.sh` — it scans all projects' playbooks and drafts candidates.
2. Curator (cross-project mode) reviews candidates against the contract above.
3. Approved patterns get an entry in `index.md` with a stable `UP-NNNN` id.
4. If grep-detectable, add a check to `scripts/verify.sh` so it's caught mechanically.

---

*Source: ~/ai-toolkit/patterns/README.md*
