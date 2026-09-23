# PV2 L3 — one executor

**Date:** 2026-09-23  
**G5:** 96/96 after the change (`PV2-g5-2026-09-23r.json`)  
**Unit:** `test_pv2_executor` 4 · `test_pv2_arbiter` 10 · handoff + zero-LLM 44

Pre-S2 and intent-resolution gates no longer return the first body that fired. They **stage**. `pick_staged` returns the body whose decision matches `Arbiter.decide`.

Proven loser: navigate + refuse staged → refuse text is returned, not “open Leave”.  
Proven loser: navigate + handoff staged → handoff text is returned.

Memory-confirm still returns in place (it already wrote `learn_fact`). The tool pipeline still finalizes `answer` / `tool_answer` after S2.

Night 2026-09-23 FAIL not rewritten. Streak 0/5.
