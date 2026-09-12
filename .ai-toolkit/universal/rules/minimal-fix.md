## Minimal Fix Principle

```
WRONG: Fix bug + refactor the function + improve naming + add extra logging
RIGHT: Fix only the confirmed root cause. One change. Prove it with a test.
```

If you see other bugs while fixing: log them in TASK-RESULTS.md under "Issues Found."
**Do NOT fix them.** That's scope creep. Master decides what gets fixed next.

This applies to ALL workers:
- Debugger/Fixer: one bug, one fix, one regression test
- Backend Worker: implement only what the spec says, no bonus features
- Frontend Worker: fix the component, don't refactor adjacent ones
- DevOps Worker: change the one config/file needed, don't clean up others

---

*Source: ~/ai-toolkit/universal/rules/minimal-fix.md*
