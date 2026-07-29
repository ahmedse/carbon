# Troubleshooting Playbook

**The known-issues knowledge base.** Every confirmed bug + its verified fix lives here
so it is NEVER re-diagnosed from scratch. This is how repeated problems stop costing time.

## How to use it
1. **Before debugging anything**, search this file:
   `grep -i "<symptom keyword>" .ai-toolkit/troubleshooting/playbook.md`
2. If your symptom matches an entry → apply the documented fix. Done.
3. If it's new → after you confirm the root cause and fix it, **append a new entry**
   (use the format in [playbook.md](playbook.md) header). This is mandatory, not optional.

## Relationship to other files
- **playbook.md** — symptom → root cause → verified fix (portable, lives in the toolkit).
- **GOTCHAS_FILE** (project.config.md) — deep forensic notes, project-specific memory.
- **decisions/** — architectural decisions (why we do it a certain way).
- **verify.sh** — for bug CLASSES that are grep-detectable, add an automated check.

The rule: a bug fixed once should be **findable** (playbook), **locked** (regression test),
and if possible **auto-caught** (verify.sh). See `shared/debugging.md`.
