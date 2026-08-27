# Debugger/Fixer — Phantom Success: DQ Rule Not Created Despite "Completed" Status

**Date:** 2026-08-27  
**Run ID:** `ee853906-e600-4fa1-90f8-9d0217879593`  
**Symptom:** Pulse UI shows task "Completed" with both steps "Finished", but NO DQ rule was created in the database.

---

## ROOT CAUSE

The LLM planner hallucinated an invalid schema for the `create_dq_rule` tool, passing:

```json
{
  "rule_type": "general",
  "validation_logic": "field is a number and positive"
}
```

**Three critical failures:**

1. **Invalid `rule_type`**: `"general"` is NOT in the allowed set. Valid types are:
   - `not_null`, `unique`, `allowed_values`, `range`, `regex`, `reference_integrity`, `threshold`, `nl_check`

2. **Missing required fields**:
   - `name` (required)
   - `level` (required: must be `"field"` or `"business"`)

3. **Hallucinated field**: `validation_logic` does NOT exist in the plugin's schema. The plugin expects `params` with type-specific keys.

**Result:** The tool returned `null` (no output), but the critic still marked it as "pass" and the step status became "completed".

---

## Evidence Trail

### 1. Database Check — NO Rule Created
```bash
$ DQRule.objects.filter(rule_type='general').count()
0  # Confirmed: no "general" type rules exist
```

### 2. Run Record — Status "completed"
```
Run ID: ee853906-e600-4fa1-90f8-9d0217879593
Status: completed
Conversation: b8953e22-5e6e-49b2-b158-b22944f3571e
Created: 2026-08-27 15:12:24
Updated: 2026-08-27 15:14:45
```

### 3. RunStep Analysis — Step 1 (create_dq_rule)

```
Step 1: Create the data quality rule in the system.
Status: completed
Tool: create_dq_rule

TOOL ARGS:
{
  "rule_type": "general",
  "validation_logic": "field is a number and positive"
}

TOOL OUTPUT: null

CRITIC VERDICT: pass
ERROR: None
```

**The smoking gun:** `TOOL OUTPUT: null` but `STATUS: completed` and `CRITIC: pass`.

---

## Multiple Bugs Exposed

### Bug 1: Schema Hallucination (LLM Planner)
The planner did NOT consult the actual `create_dq_rule` schema. It invented:
- A non-existent rule type (`"general"`)
- A non-existent field (`"validation_logic"`)
- Omitted required fields (`name`, `level`)

**Expected:** The planner should have passed args like:
```json
{
  "name": "Positive Number Validation",
  "rule_type": "threshold",
  "level": "field",
  "params": {
    "operator": "gt",
    "value": 0
  },
  "severity": "error"
}
```

### Bug 2: Null Tool Output Treated as Success
The tool returned `null` (indicating failure or no result), but:
- Step status: `"completed"`
- Critic verdict: `"pass"`
- No error recorded

**Expected:** A null/empty tool output from a mutation tool should be treated as a failure, NOT a success.

### Bug 3: Critic Passed Without Output Validation
The critic approved a step that:
- Promised to "create the data quality rule in the system"
- Returned `null`
- Created nothing

**Expected:** The critic should verify that mutation tools (`requires_confirmation=True`) returned a `requires_confirmation` response OR an `execution_id`.

---

## Impact

**User Experience:**
- User asked: "create a dq rule, general. to validate that a field is number and positive"
- UI showed: "Completed ✓" (green badge)
- Reality: **No rule was created**

This is a **false success** — the system claimed to have done something it didn't do.

---

## Recommended Fixes

### Fix 1: Schema-Aware Planning (High Priority)
**Location:** `backend/ai/engine/cognition/plan/planner.py`

The planner MUST validate tool calls against the actual `input_schema` before emitting them. If the LLM hallucinates fields or types:
1. Detect the mismatch
2. Re-prompt with the actual schema
3. OR: fail the planning step explicitly

**Detection:** JSON Schema validation against `ToolPlugin.input_schema` before staging.

### Fix 2: Null-Output Guard (Critical)
**Location:** `backend/ai/engine/cognition/turn/runner.py` or wherever tool outputs are processed.

```python
if tool_output is None or (isinstance(tool_output, dict) and not tool_output):
    if tool.requires_confirmation:
        # Mutation tools MUST return a proposal or error
        status = "failed"
        error = f"{tool.name} returned no output (expected requires_confirmation response)"
```

### Fix 3: Critic Validation for Mutation Tools (Medium Priority)
**Location:** `backend/ai/engine/cognition/turn/critic.py` (or wherever critic runs)

For tools with `requires_confirmation=True`, the critic should verify:
```python
if plugin.requires_confirmation:
    output = step.tool_output_json
    if not output:
        verdict = "fail"
        flags = ["null_output"]
    elif "requires_confirmation" not in output and "error" not in output:
        verdict = "fail"
        flags = ["missing_confirmation_response"]
```

### Fix 4: Tool Schema Hint in System Prompt (Quick Win)
**Location:** `backend/ai/engine/cognition/plan/planner.py` (system prompt)

Explicitly remind the LLM:
> "CRITICAL: Before calling `create_dq_rule`, validate your args against its input_schema. The `rule_type` field MUST be one of: not_null, unique, allowed_values, range, regex, reference_integrity, threshold, nl_check. 'general' is NOT valid. 'validation_logic' does NOT exist; use 'params' instead."

---

## Files to Inspect

1. **Planner:**
   - `backend/ai/engine/cognition/plan/planner.py` — schema validation
   - `backend/ai/engine/cognition/plan/loop.py` — planning loop

2. **Tool Execution:**
   - `backend/ai/engine/cognition/turn/runner.py` — tool invocation + output handling
   - `backend/ai/plugins/create_dq_rule.py` — the plugin itself (correct)

3. **Critic:**
   - `backend/ai/engine/cognition/turn/critic.py` (if exists) — validation logic

4. **Models:**
   - `backend/ai/models/core.py` (RunStep, Run) — status tracking

---

## Regression Test (MUST ADD)

**Test:** `backend/ai/tests/test_create_dq_rule_invalid_args.py`

```python
def test_create_dq_rule_with_invalid_rule_type_returns_error():
    """Regression: 2026-08-27 phantom success with rule_type='general'."""
    from ai.plugins.create_dq_rule import CreateDQRule
    
    plugin = CreateDQRule()
    
    # Simulate the hallucinated args
    result = await plugin.execute(
        {"rule_type": "general", "validation_logic": "field is a number and positive"},
        ctx=mock_ctx
    )
    
    # MUST return an error, not null
    assert result is not None, "Tool returned None instead of error dict"
    assert "error" in result or "validation" in result
    
    if "validation" in result:
        assert result["validation"]["passed"] is False
        errors = result["validation"]["errors"]
        assert any("rule_type" in e["field"] or "type" in e["field"] for e in errors), \
            "Expected validation error for invalid rule_type"

def test_planner_validates_tool_schema_before_emitting():
    """Planner must catch schema mismatches before emitting tool calls."""
    # This test would go in a planner test file
    # Verify that passing invalid args to create_dq_rule is caught during planning
    pass  # TODO: implement when Fix 1 is applied
```

---

## Before/After Evidence

### Before (Current State)
```
User request: "create a dq rule, general. to validate that a field is number and positive"

Step 1 Tool Call:
  Args: {"rule_type": "general", "validation_logic": "..."}
  Output: null
  Status: completed ✓
  Critic: pass

DB Query:
  DQRule.objects.filter(rule_type='general').count() → 0
  
Result: FALSE SUCCESS
```

### After (Expected with Fixes)
```
Step 1 Tool Call:
  Args: {"rule_type": "general", "validation_logic": "..."}
  Output: {
    "error": "Proposed DQ rule is invalid — nothing was written.",
    "validation": {
      "passed": false,
      "errors": [
        {"field": "type", "message": "type must be one of ['allowed_values', ...]"},
        {"field": "name", "message": "name is required..."},
        {"field": "level", "message": "level must be one of ['field', 'business']"}
      ]
    }
  }
  Status: failed
  Critic: fail (null_output OR validation_failed)

Result: HONEST FAILURE (user can retry with correct args)
```

---

## Playbook Entry

**Symptom:** Task shows "Completed" but the promised action (e.g., DQ rule creation) didn't happen.

**Diagnosis:**
1. Check `RunStep.tool_output_json` for the mutation step
2. If `null` → tool invocation failed silently
3. Check `tool_args_json` against the plugin's `input_schema`

**Root Cause:** LLM hallucinated invalid tool args + null output wasn't treated as failure.

**Fix:** Apply schema validation (Fix 1), null-output guard (Fix 2), and critic mutation-tool validation (Fix 3).

---

## Follow-Up Needed

- [ ] Implement Fix 1 (schema validation in planner)
- [ ] Implement Fix 2 (null-output guard)
- [ ] Implement Fix 3 (critic mutation-tool check)
- [ ] Add regression tests
- [ ] Update system prompt (Fix 4)
- [ ] Audit other mutation tools for the same issue (`export_document`, `learn_fact`, `forget_fact`)

---

**Status:** Root cause confirmed. Fixes specified. Awaiting implementation by backend-worker.
