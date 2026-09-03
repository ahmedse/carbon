# Git & Change Workflow
# Read by: all roles. How changes are committed, grouped, and messaged.
# NOTE: committing/pushing is a human-gated action — see base-rules & operational safety.

---

## RULE 1 — Commits Are Not Automatic

- Do NOT `git commit`/`git push` unless the task explicitly asks for it or the user approves.
- Never `git push --force`, `git reset --hard`, or amend published commits without explicit OK.
- Never commit with `--no-verify` (bypasses hooks/checks).
- Never commit `.env`, secrets, large build artifacts, or unrelated files.

---

## RULE 2 — One Logical Change Per Commit

- A commit is one coherent change (a feature slice, a fix, a refactor) — not a grab-bag.
- Don't mix a refactor with a bug fix. Don't mix formatting-only churn with logic.
- Keep the diff reviewable: small, focused, self-consistent.

---

## RULE 3 — Commit Message Format (Conventional Commits)

```
<type>(<scope>): <imperative summary ≤ 72 chars>

<why the change was made — the reasoning, not just what>
<any breaking-change or follow-up notes>

Refs: TASKS.md Phase N / ADR 00NN / playbook PB-NN
```

Types: `feat`, `fix`, `refactor`, `perf`, `test`, `docs`, `chore`, `build`, `ci`.

Examples:
```
fix(aihub): clear backfilled actuals on reset so dashboard refreshes

daily_summaries preferred Prediction.actual_value over live ds1, so
deleting source data left stale values. Clear the 3 derived fields too.
Refs: playbook PB-03
```
```
feat(datahub): add is_monday/is_tuesday early-workweek features

Additive columns only; existing models unaffected. Refs: TASKS.md Phase 1
```

---

## RULE 4 — Branching

- Feature work on a branch (`feature/<short-name>`), not directly on main/master.
- Fixes: `fix/<short-name>`. Keep branch names short and descriptive.
- Rebase/merge policy: follow the repo's existing convention (check `git log` shape).

---

## RULE 5 — Before You Commit (pre-commit gate)

```bash
./.ai-toolkit/scripts/verify.sh full     # must pass
git status                                # review EXACTLY what's staged
git --no-pager diff --staged              # read the diff before committing
```
- Never `git add -A` blindly — stage intentionally, review the diff.
- Ensure no secret, no debug leftover, no unrelated file is staged.

---

## RULE 6 — Pull Requests (when used)

- PR description: what + why + how verified (paste the verify output).
- Link the TASKS.md phase / ADR / playbook entry.
- Do NOT comment on / merge PRs autonomously — that's a human-gated action.

---

## Anti-Patterns (reject)

- Committing without being asked / pushing without approval
- `git add -A` + commit-everything without reviewing the diff
- Mixed-concern commits (fix + refactor + formatting together)
- Vague messages ("update", "fix stuff", "wip")
- `--no-verify` / force-push / hard-reset on shared history
- Committing secrets, `.env`, or build artifacts
