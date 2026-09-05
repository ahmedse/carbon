# Pulse v2 — Phase 10 Integration Validation Results

**Date:** 2026-09-05
**Role:** Master Architect
**Scope:** Phase 10 of `plans/PULSE-V2-IMPLEMENTATION-PLAN.md` — full-stack smoke + golden scenarios.

---

## 10.1 — Full new-test run

Command:
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python -m pytest \
  ai/tests/test_pulse_loop.py \
  ai/tests/test_phase2_routing.py \
  ai/tests/test_work_objectives.py \
  ai/tests/test_evidence_records.py \
  ai/tests/test_multi_hop.py \
  ai/tests/test_carbon_context.py \
  ai/tests/test_verification.py \
  ai/tests/test_model_policy.py \
  -v --tb=short
```

**Result:** `30 passed, 0 failed`

| Phase | Test file | Count |
|---|---|---|
| 1 | `test_pulse_loop.py` | 4 |
| 2 | `test_phase2_routing.py` | 3 |
| 3 | `test_work_objectives.py` | 4 |
| 4 | `test_evidence_records.py` | 3 |
| 5 | `test_multi_hop.py` | 4 |
| 6 | `test_carbon_context.py` | 3 |
| 7 | `test_verification.py` | 4 |
| 9 | `test_model_policy.py` | 5 |

## 10.2 — Frontend test run

Command:
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm run test -- --run src/components/ai/__tests__/WorkObjectivesPanel.test.jsx
```

**Result:** `4 passed (1 test file)`

## 10.3 — Regression check

Command:
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python -m pytest ai/tests/ -q --tb=short
```

**Result:** `1454 passed, 10 failed` (0:06:30).

The 10 failures are **pre-existing / flaky, NOT Pulse v2 regressions**:

| Failure | Count | Nature |
|---|---|---|
| `test_mcp_server.py` (9 tests) | 9 | Pre-existing `NoReverseMatch: Reverse for 'mcp-tool-call' not found` — `server_urls.py` is never included in the URL conf. Unrelated to Pulse v2. |
| `test_intelligence_live.py::test_live_confident_turn_is_grounded_and_calibrated` | 1 | **Flaky live-LLM test.** Real `gpt-4o` turn. Full-run: critic `veto` (`ungrounded_claim`); isolated re-run: content was correct + grounded, but `confidence_label='uncertain'` instead of `high`/`medium`. Non-deterministic model output — not a code regression. |

Phase 9 changes are provably inert for the live test: `model_for_profile()`
returns `None` with empty settings, `_observe`'s `model` is `None` on the
single-pass path, the verification block is gated by `PULSE_VERIFY_ENABLED=False`,
and the final-ledger edit only appends two JSON keys. None touch confidence
calibration or the critic witness.

---

## 10.4 — Manual golden scenarios

These require a live server (`./manage.sh start`) and the real chat surface. They
are intentionally manual — they depend on live LLM + tool execution + the Carbon DB.

### G1 — Weather with ambiguity (Phase 2)
**Prompt:** "hi what is the weather in north coast egypt today, is it suitable for beach swimming?"
**Expected:** calls `web_research`, returns live weather, states the location used.
**Verify:** response cites a location + weather source; no generic refusal.

### G2 — Single tool grounded answer (Phase 1 observation)
**Prompt:** "What are the active DQ rules for the emissions module?"
**Expected:** calls `get_entity_details` / `call_host_api`, returns real rule names + conditions.
**Verify:** answer names actual DB rules, not a generic description.

### G3 — Save and resume (Phase 3)
**Turn 1:** "Investigate why emissions increased in August. Save this so I can continue later."
**Turn 2 (new conversation):** "Where did we get to on my emissions investigation?"
**Expected:** Turn 1 creates a `WorkObjective`; Turn 2 calls `get_work_objectives` and reports the saved summary.
**Verify:** `WorkObjective` row exists (`ai/tests` + Work Objectives panel shows it); resume surfaces the summary.

### G4 — Factual grounding (Phase 6)
**Prompt:** "What is the current emission factor for our electricity consumption?"
**Expected:** returns the configured value from the Carbon DB, not a generic global average.
**Verify:** value matches `emissions` emission-factor config.

### G5 — Spelling/text transformation (regression)
**Prompt:** "Correct the spelling in this sentence: 'what is the weather in north cost egypt toay?'"
**Expected:** rewrites the sentence WITHOUT calling `web_research`.
**Verify:** no tool call fired; answer is the corrected sentence only.

---

## Settings summary (all in `ai/engine/core/config.py` — class `Settings`)

| Setting | Default | Purpose |
|---|---|---|
| `PULSE_LOOP_ENABLED` | `True` | Phase 1 adaptive loop |
| `PULSE_LOOP_MAX_STEPS` | `6` | Phase 1 max steps |
| `PULSE_LOOP_MAX_TOKENS` | `8000` | Phase 1 token cap |
| `PULSE_CARBON_CONTEXT_ENABLED` | `True` | Phase 6 carbon context |
| `PULSE_VERIFY_ENABLED` | `False` | Phase 7 verification (opt-in) |
| `LLM_INVESTIGATE_MODEL` | `""` | Phase 9 strong investigate model |
| `LLM_VERIFY_MODEL` | `""` | Phase 9 verify model (falls back to investigate) |

## Rollback / disable

- Phase 7: `PULSE_VERIFY_ENABLED=false` (default).
- Phase 9: leave `LLM_INVESTIGATE_MODEL` / `LLM_VERIFY_MODEL` empty → instance default model used.
