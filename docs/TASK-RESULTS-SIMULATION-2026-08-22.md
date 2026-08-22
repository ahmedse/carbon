# Agent Workflow Simulation — 2026-08-22 11:00:25 UTC

Deep multi-scenario simulation of the agent task-orchestration (plans) system.

## Executive summary

| # | Scenario | Verdict | Highlight |
|---|----------|---------|-----------|
| B01 | B01 Agent Chain Dag | ✅ | ok |
| B02 | B02 Parallel Fan Out | ✅ | ok |
| B03 | B03 Consent Gate Confirm | ✅ | ok |
| B04 | B04 Consent Gate Decline | ✅ | ok |
| B05 | B05 Veto Failure Surface | ✅ | ok |
| B06 | B06 Pause Resume Ledger | ✅ | ok |

## Part A — Live system stress test (real HTTP API, real engine)

## Part B — Designed workflow simulation (deterministic seams)

### B01 — B01 Agent Chain Dag

**Brief:** Three agents in a sequential chain (1→2→3).  Frames must arrive in
    dependency order and every step completes.

**Verdict:** ✅

**Checks**

    ✅ 3 steps started in order
    ✅ protocol intact
    ✅ run completed
    ✅ ledger 3 completed steps

**Evidence**

```json
{
    "types": [
        "plan_start",
        "step_start",
        "step_result",
        "step_end",
        "step_start",
        "step_result",
        "step_end",
        "step_start",
        "step_result",
        "step_end",
        "done"
    ],
    "step_ids": [
        0,
        1,
        2
    ],
    "pattern": "skill_chain",
    "source": "llm_decompose"
}
```

### B02 — B02 Parallel Fan Out

**Brief:** Three independent agents (no depends_on) — the topological ready-set
    runs them as a fan-out batch; all complete.

**Verdict:** ✅

**Checks**

    ✅ all 3 steps started
    ✅ run completed
    ✅ ledger all completed

**Evidence**

```json
{
    "types": [
        "plan_start",
        "step_start",
        "step_result",
        "step_end",
        "step_start",
        "step_result",
        "step_end",
        "step_start",
        "step_result",
        "step_end",
        "done"
    ],
    "pattern": "fan_out"
}
```

### B03 — B03 Consent Gate Confirm

**Brief:** Mutation step hits the RULE_21 consent gate: run pauses with a
    step_confirm frame → user confirms → staged mutation executes (recorded
    by the fake host executor) → resume → completed.

**Verdict:** ✅

**Checks**

    ✅ consent frame emitted
    ✅ run paused at gate
    ✅ confirm accepted
    ✅ staged mutation executed
    ✅ resume completed

**Evidence**

```json
{
    "gate_frames": [
        "plan_start",
        "step_start",
        "step_confirm",
        "step_start",
        "step_result",
        "step_end",
        "done"
    ],
    "resume_frames": [
        "plan_start",
        "step_start",
        "step_result",
        "step_end",
        "step_start",
        "step_result",
        "step_end",
        "done"
    ],
    "confirmed": [
        [
            "exec-0",
            "1"
        ]
    ]
}
```

### B04 — B04 Consent Gate Decline

**Brief:** User declines the staged mutation: nothing is written (decline recorded)
    and the step is skipped; the run resumes past it and completes.

**Verdict:** ✅

**Checks**

    ✅ consent frame emitted
    ✅ run paused at gate
    ✅ decline accepted
    ✅ mutation NOT executed
    ✅ decline recorded
    ✅ resume completed

**Evidence**

```json
{
    "gate_frames": [
        "plan_start",
        "step_start",
        "step_confirm",
        "step_start",
        "step_result",
        "step_end",
        "done"
    ],
    "resume_frames": [
        "plan_start",
        "step_start",
        "step_result",
        "step_end",
        "done"
    ],
    "declined": [
        [
            "exec-0",
            "1"
        ]
    ]
}
```

### B05 — B05 Veto Failure Surface

**Brief:** A step the critic vetoes is surfaced honestly (step failed, run failed,
    ledger steps_failed=1) — then the plan is edited (re-planned) and a clean
    re-run recovers to completed.

**Verdict:** ✅

**Checks**

    ✅ failed step surfaced
    ✅ failure honest (error present)
    ✅ run status failed
    ✅ ledger steps_failed=1
    ✅ edit returns diff
    ✅ recovery run completed

**Evidence**

```json
{
    "fail_frames": [
        "plan_start",
        "step_start",
        "step_result",
        "step_end",
        "step_start",
        "step_result",
        "step_end",
        "done"
    ],
    "failed_error": "Step failed (simulated critic veto)",
    "diff": {
        "added": 1,
        "removed": 2,
        "changed": 0
    },
    "recovery_frames": [
        "plan_start",
        "step_start",
        "step_result",
        "step_end",
        "done"
    ]
}
```

### B06 — B06 Pause Resume Ledger

**Brief:** Ledger-level pause → resume pre-flight → run: the consent step is never
    corrupted by a ledger pause, and resume re-enters execution from the
    durable RunStep rows.

**Verdict:** ✅

**Checks**

    ✅ pause → paused
    ✅ resume pre-flight ok
    ✅ resumed run completed

**Evidence**

```json
{
    "types": [
        "plan_start",
        "step_start",
        "step_result",
        "step_end",
        "step_start",
        "step_result",
        "step_end",
        "step_start",
        "step_result",
        "step_end",
        "done"
    ],
    "ledger_status": "completed",
    "steps": [
        "completed",
        "completed",
        "completed"
    ]
}
```

## Deep findings

_No findings recorded._

## Scenario count

- Part A (live): 0
- Part B (designed): 6
- Passed: 6
- Failed: 0
