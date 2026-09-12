## Diagnosis Protocol — 9 Steps

**Every bug investigation follows this cycle. No exceptions.**

```
Step 1: CHECK THE PLAYBOOK & GOTCHAS FIRST
  Read project.config.md → GOTCHAS_FILE
  If it's a known issue, the root cause and fix are already documented.

Step 2: REPRODUCE THE SYMPTOM
  Can you reproduce it locally? In the container?
  Exact steps to reproduce → document before fixing.

Step 3: TRACE THE CALL CHAIN
  From the error message / symptom:
  → Which endpoint, view, or component shows it?
  → What does that call?
  → Trace backward to where the wrong value originates.

Step 4: FORM A HYPOTHESIS
  State it explicitly: "X fails because Y does Z when it should do A."
  One hypothesis at a time. Don't fix until you've confirmed it.

Step 5: CONFIRM THE HYPOTHESIS
  - For backend: add a diagnostic print or check the value via shell
  - For frontend: check network tab, check console, read the component
  - For deploy: docker exec and read the actual file in the container

Step 6: REGRESSION TEST FIRST (red)
  Write a FAILING test that captures the bug.
  This proves you understand it AND locks it out forever.

Step 7: APPLY THE MINIMAL FIX (green)
  Fix exactly the confirmed root cause. Nothing more. The test now passes.

Step 8: VERIFY THE FIX
  Run the full test suite. Reproduce the original symptom → confirm it's gone.
  Show before/after evidence.

Step 9: CAPTURE so it never recurs
  - Append an entry to troubleshooting/playbook.md (symptom → cause → fix).
  - If grep-detectable → add a check to scripts/verify.sh.
  - If architectural → write an ADR (decisions/).
  - If project-specific → GOTCHAS_FILE.
```

**Diagnosis BEFORE fix. Regression test BEFORE fix is called done.**
A fix without a confirmed root cause is a guess. A fix without a regression test is temporary.

---

*Source: ~/ai-toolkit/universal/protocols/diagnosis.md*
