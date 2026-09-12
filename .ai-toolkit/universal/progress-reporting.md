## Progress Reporting — SHOW YOUR WORK IN REAL TIME

**This is the #1 rule for user visibility. Violating it means the user sees nothing until you're done.**

After EVERY significant operation, report output immediately — do NOT buffer it for the final report.

**Format**: After each step, post a short message. Examples:

```
✅ tests/test_foo.py — 10 passed in 2.3s
❌ tests/test_bar.py — 1 FAILED: test_baz — KeyError: 'missing_key'
   → Fixing: added missing_key default to response dict
✅ Fixed. 10 passed.
```

```
📦 docker cp → grep marker → 5 matches ✅
🔄 docker restart → logs clean, health 200 ✅
```

```
🔍 Reproduced: test_smoke.py FAILED — AssertionError: expected 200, got 500
💡 Hypothesis: middleware crashes on None project_id from test fixture
🔧 Fix: added null-check in middleware. 1 file changed.
✅ Regression test passes. Original symptom gone.
```

The user should see a running log of your work, not a wall of text at the end.

---

*Source: ~/ai-toolkit/universal/progress-reporting.md*
*Each role file's Progress Reporting section contains a role-specific "After this / Report this" table*
*followed by this format block. Both are synced from this canonical source.*
