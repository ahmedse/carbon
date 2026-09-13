# P1-17 — Red-team suite v1

Adversarial verification that **every** host-effect path from P0-06 is
fail-closed. Ten mutation attempts per path, sixty total, all of which must be
**blocked** by a deterministic guard.

## The 10 × 6 matrix

| Path | Guard(s) | Blocked signal |
|------|----------|----------------|
| `direct` — open state-changing tool call | `CriticWitness` (S4 rules-tier) | hard `veto`: `unconfirmed_mutation` / `mutation_not_confirmed` |
| `indirect` — smuggled phrasing (dangerous SQL/shell in args, case-obfuscated verb) | `tool_safety_hook`, `CriticWitness` | hook `cancel` `safety_blocked`, or `veto` `unconfirmed_mutation` |
| `worker` — worker subagent mutation | `readonly_worker_hook` | hook `cancel` `worker_mutation_blocked` |
| `skill` — destructive draft skill | `harmlessness_critic`, `structural_critic` | `passed=False` (`dangerous_pattern:*`, `invalid_kind:*`, `*_invalid_json`) |
| `proactive` — trigger-condition SQL injection | `_render_where`, `validate_sql`, `_evaluate_threshold` | `ValueError` / `ToolExecutionError` / `fired=False` + `legacy` |
| `ingestion` — ops workflow mutation | `OpsWorkflowRunner` confirmation flow | `pending_confirmation` / `needs_input` / `failed` / `OpsWorkflowError` |

The catalogue lives in [`mutations.py`](mutations.py) and is the single source
of truth. [`test_manifest.py`](test_manifest.py) fails if the matrix drifts
away from exactly 60 attempts (10 per path, unique ids).

## Running

```bash
cd backend
python -m pytest ai/tests/redteam/ -q
```

The suite is fully offline (no live LLM, no host connection, no DB session) and
is collected by the default `pytest` run, so it executes in CI (`backend` job)
on every push and PR.

## Deps

P1-02…P1-09 (critic hard veto, worker fail-closed, skill admission gate, gate-only
promotion authority, proactive SQL hardening, ops confirmation flow).
