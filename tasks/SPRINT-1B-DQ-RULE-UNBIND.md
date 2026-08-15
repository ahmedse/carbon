# TASK-DQ-RULE-UNBIND — DQ Rules Standalone + Professional JSON Editor

**Date:** 2026-08-12
**Author:** Master Architect
**Area:** backend (DQ), frontend (DQ Workspace)
**Depends on:** ADR-0006 (accepted)
**Status:** Phase A → B → C, execute in order

---

## Objective

1. **Unbind rule creation from table binding.** `DQRule` is a standalone policy.
   Bindings happen at the data product level, not during rule authoring.
2. **Upgrade JSON authoring** from plain `<textarea>` to Monaco Editor with
   syntax highlighting, autocomplete, and inline validation.

---

## Phase A — Backend: Make Bindings Optional

**Role:** backend-worker  **Est:** 15 min  **Risk:** Low

### Files
- `backend/dq/rule_schema.py`

### Changes
1. `validate_definition()` line ~105-120: Change `bindings` from required non-empty
   to optional. Empty list or absent → valid. If present, validate each entry.
2. Update the test at `backend/dq/tests/test_rule_schema.py` (if exists) to cover
   both cases: rule WITH bindings, rule WITHOUT bindings.

### Verification gate
```bash
cd backend && source ../.venv/bin/activate
python -m pytest dq/tests/test_rule_schema.py --reuse-db -q
python -m pytest dq/tests/ --reuse-db -q        # full DQ suite
python manage.py check
```

---

## Phase B — Frontend: Update RuleJsonEditor Template

**Role:** frontend-worker  **Est:** 10 min  **Risk:** Low

### Files
- `carbon-frontend/src/components/dq/RuleJsonEditor.jsx`

### Changes
1. `EMPTY_DEFINITION_TEMPLATE` — remove `bindings` array, or set to `"bindings": []`
2. `validateDefinitionClient()` — remove the non-empty bindings check. Keep the
   structural validation of individual binding entries when present.
3. No visual changes — the textarea stays as-is for now.

### Verification gate
```bash
cd carbon-frontend && npm run lint
cd carbon-frontend && npm run build
```

---

## Phase C — Frontend: Monaco Editor for DQ Rule JSON

**Role:** frontend-worker  **Est:** 1-2 hr  **Risk:** Medium

### Files
- `carbon-frontend/package.json` — add `@monaco-editor/react`
- `carbon-frontend/src/components/dq/RuleJsonEditor.jsx` — replace `<TextField multiline>` with `<Editor>`
- `carbon-frontend/src/components/dq/` — new file: `dqRuleSchema.json` (JSON Schema for v1 rules)
- (No backend changes)

### Requirements
1. **Monaco Editor** (`@monaco-editor/react`) replacing the plain `<textarea>`.
2. **JSON Schema** (`dqRuleSchema.json`) defining v1 rule shape — fed to Monaco for:
   - Autocomplete (field names: `name`, `level`, `dimension`, `type`, `severity`...)
   - Enum suggestions (`not_null` | `unique` | `allowed_values` | ...)
   - Inline hover documentation (description from schema)
3. **Live JSON parse errors** — red squigglies on invalid JSON (Monaco built-in).
4. **"Validate" button** stays — runs `validateDefinitionClient()` for schema-level checks.
5. **"Draft with AI" button** stays — unchanged behavior.
6. **Schema version indicator** — badge showing `v1` near the editor.
7. **Minimap disabled** — saves space for what's usually a 20-40 line JSON doc.
8. **Theme** — matches Carbon's dark/light mode (MUI theme → Monaco theme mapping).

### Monaco Editor config sketch
```jsx
import Editor, { useMonaco } from '@monaco-editor/react';
import dqRuleSchema from './dqRuleSchema.json';

<Editor
  height="400px"
  defaultLanguage="json"
  value={value}
  onChange={onChange}
  beforeMount={(monaco) => {
    monaco.languages.json.jsonDefaults.setDiagnosticsOptions({
      validate: true,
      schemas: [{
        uri: 'carbon://dq-rule-v1.json',
        fileMatch: ['*'],
        schema: dqRuleSchema,
      }],
    });
  }}
  options={{
    minimap: { enabled: false },
    lineNumbers: 'on',
    folding: true,
    fontSize: 13,
    tabSize: 2,
    scrollBeyondLastLine: false,
  }}
/>
```

### JSON Schema (`dqRuleSchema.json`) structure
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "carbon://dq-rule-v1.json",
  "title": "DQ Rule Definition v1",
  "type": "object",
  "required": ["schema_version", "name", "level", "dimension", "type", "severity", "active"],
  "properties": {
    "schema_version": { "const": 1, "description": "Schema version (must be 1)" },
    "name": { "type": "string", "minLength": 1, "description": "Human-readable rule name" },
    "description": { "type": "string", "description": "What this rule checks and why" },
    "level": { "enum": ["field", "business"], "description": "Rule level" },
    "dimension": { "enum": ["completeness", "validity", "accuracy", "consistency", "timeliness", "uniqueness", "integrity", "reasonability"], "description": "DAMA DMBOK2 dimension" },
    "type": { "enum": ["not_null", "unique", "allowed_values", "range", "regex", "reference_integrity", "threshold", "nl_check", "anomaly_detect"], "description": "Rule type" },
    "severity": { "enum": ["info", "warn", "error"], "description": "Severity level" },
    "active": { "type": "boolean", "description": "Whether the rule is active" },
    "bindings": { "type": "array", "items": { "type": "object", "properties": { "table": { "type": "string" }, "field": { "type": "string" } } }, "description": "Optional table/field bindings" },
    "params": { "type": "object", "description": "Rule-type-specific parameters" },
    "enforcement": { "type": "object", "properties": { "on_write": { "type": "boolean" } }, "description": "Enforcement settings" }
  }
}
```

### Verification gate
```bash
cd carbon-frontend && npm run lint
cd carbon-frontend && npm run build
# Manual: open DQ Workspace → Create Rule → verify Monaco loads with highlighting
# Manual: type invalid JSON → verify squigglies appear
# Manual: hover field names → verify autocomplete descriptions
```

### Definition of Done (all phases)
- [ ] `rule_schema.py` accepts rule definitions without bindings
- [ ] Tests pass: standalone rule (no bindings) + rule with bindings
- [ ] `RuleJsonEditor` template omits bindings
- [ ] Client validation doesn't require non-empty bindings
- [ ] Monaco Editor replaces textarea with syntax highlighting + autocomplete
- [ ] JSON Schema v1 loaded into Monaco for inline docs
- [ ] `verify.sh full` passes
- [ ] ADR-0006 recorded

---

## Files Modified (summary)

| Phase | File | Change |
|-------|------|--------|
| A | `backend/dq/rule_schema.py` | `bindings` optional in `validate_definition()` |
| A | `backend/dq/tests/test_rule_schema.py` | Add test for standalone rule |
| B | `carbon-frontend/src/components/dq/RuleJsonEditor.jsx` | Remove bindings from template + client validation |
| C | `carbon-frontend/package.json` | Add `@monaco-editor/react` |
| C | `carbon-frontend/src/components/dq/RuleJsonEditor.jsx` | Replace textarea with Monaco Editor |
| C | `carbon-frontend/src/components/dq/dqRuleSchema.json` | NEW — JSON Schema v1 |
| — | `.ai-toolkit/decisions/0006-dq-rule-standalone.md` | ADR |
| — | `TASK-DQ-RULE-UNBIND.md` | This file |
