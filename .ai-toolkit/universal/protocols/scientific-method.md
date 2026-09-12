## Scientific Method Protocol — 6 Steps

**Every research task follows this cycle exactly.**

```
1. QUESTION — what are we trying to learn?
2. HYPOTHESIS — what do we expect and why?
3. EXPERIMENT DESIGN — what will we measure, what's the baseline, what's success?
4. EXECUTE — run the experiment, capture raw output
5. ANALYZE — compute metrics, compare to baseline, identify confounders
6. CONCLUDE — accept/reject hypothesis, state confidence, recommend next step
```

### Before Running Any Experiment
- Know your baseline metric BEFORE starting (read from task spec or last TASK-RESULTS.md)
- State the hypothesis explicitly: "I believe X will improve Y because Z"
- Define success criterion: "this succeeds if metric < threshold"
- Check the experiment registry — has this already been run?

### Every Experiment Must Report
- Primary metric + comparison to baseline
- Per-segment or per-horizon breakdown if relevant
- Conclusion: BETTER / WORSE / MIXED / INCONCLUSIVE (with reasoning)
- Recommended next step

### Data Integrity
- NEVER re-pull historical data to test past predictions — it returns hindsight data
- For time-series: training MUST precede validation temporally — no random splits
- Document the exact date ranges used for train/val/test

---

*Source: ~/ai-toolkit/universal/protocols/scientific-method.md*
