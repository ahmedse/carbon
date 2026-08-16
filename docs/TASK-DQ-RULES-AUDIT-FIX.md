# TASK-DQ-RULES-AUDIT-FIX
# Fix the DQ Rules create/edit defects from QA audit (QA Worker 1, 2026-08-16)

- **Master Architect:** carbon
- **Source:** `docs/TASK-QA-AI-WORKSPACE-SIMULATION.md` QA pass → DQ Rules audit (1×P0, 3×P1, 2×P2, 4×P3)
- **Root defect:** the definition-first write path is half-built. `DQRule.save()` derives
  `name`/`rule_type`/`rule_level`/`severity`/`dimension`/`is_active` from `definition` (ADR-0006),
  but the serializer + frontend still require flat fields on the write path.
- **Phases:** A1 (backend blockers) → A2 (frontend blockers) → B (filters + version) → C (polish).

---

## Architecture decisions (settled — do NOT re-litigate)

- **D1 Definition-first serializer:** when `definition` is present, the backend derives flat
  columns from it. The frontend never echoes `name`/`rule_type`/`rule_level`. (Kills F1, F6.)
- **D2 Bindings are not the definition editor's concern:** create/save of the definition do NOT
  send `field_assignments_write` when the definition carries no bindings. (Kills F3 client-side.)
- **D3 Empty bindings = valid standalone:** `resolveBindings([])` returns success. (Kills F2.)
- **D4 Backend drift guard:** a write that would silently DROP existing assignments is rejected
  unless explicitly confirmed. (Backend safety net for F3 regardless of D2.)

---

## Phase A1 — Backend blockers (Backend Worker)

File: `backend/dq/serializers.py` (primary), `backend/dq/models.py` (version only).

### T1. Make flat columns optional + derive from definition (F1, F6)
In `DQRuleSerializer`:
1. Add to `Meta.read_only_fields`? NO — leave them writable. Instead:
   - `name = serializers.CharField(required=False)`
   - `rule_type = serializers.CharField(required=False)`
2. Override `validate(self, data)`:
   ```python
   def validate(self, data):
       definition = data.get('definition')
       if definition:
           from .rule_schema import validate_definition
           derrors = validate_definition(definition)
           if derrors:
               raise serializers.ValidationError({'definition': derrors})
           # derive flat columns from definition (D1)
           data.setdefault('name', definition.get('name'))
           rt = definition.get('type')
           if rt not in self.ALLOWED_RULE_TYPES:
               raise serializers.ValidationError({'definition': f"type must be one of {self.ALLOWED_RULE_TYPES}"})
           data.setdefault('rule_type', rt)
           level = definition.get('level')
           if level in ('field', 'field_validation'):
               data.setdefault('rule_level', 'field_validation')
           elif level in ('business', 'business_rule'):
               data.setdefault('rule_level', 'business_rule')
           data.setdefault('severity', definition.get('severity', 'error'))
           data.setdefault('dimension', definition.get('dimension', 'validity'))
           if 'active' in definition:
               data.setdefault('is_active', bool(definition['active']))
       else:
           if not data.get('name'):
               raise serializers.ValidationError({'name': 'This field is required.'})
           if not data.get('rule_type'):
               raise serializers.ValidationError({'rule_type': 'This field is required.'})
       # keep existing threshold validation
       ...
       return data
   ```
3. Extract the existing threshold check into a helper or keep inline — do NOT lose it.
4. `validate_rule_type` currently whitelists 8 types (excludes `anomaly_detect`). Keep that
   whitelist; reuse it as `ALLOWED_RULE_TYPES` class attr so `validate()` and the field validator
   agree. `anomaly_detect` is intentionally NOT user-creatable (QA confirmed correct).

### T2. Drift guard — reject silent binding drop (F3, D4)
1. Add `replace_assignments = serializers.BooleanField(write_only=True, required=False, default=False)`.
2. In `update()`:
   ```python
   if field_assignments_data is not None:
       existing_count = instance.field_assignments.count()
       if not field_assignments_data and existing_count and not validated_data.get('replace_assignments', False):
           raise serializers.ValidationError({
               'field_assignments_write': (
                   f'Would drop {existing_count} existing binding(s). '
                   'Pass replace_assignments=true to confirm, or omit field_assignments_write.'
               )
           })
       instance.field_assignments.all().delete()
       ...
   ```
   NOTE: `field_assignments_data` is already popped in `update()`; read `replace_assignments` before
   popping or pop it explicitly.

### T3. Version bump (F7)
In `update()`, before `super().update(...)`:
```python
if 'definition' in validated_data and instance.definition != validated_data['definition']:
    instance.version += 1
```
The model `save()` must NOT overwrite `version`. Verify `DQRule.save()` doesn't touch `version`.

### Gates (run in order, paste output)
```bash
cd /home/ahmed/aast/carbon/backend
/home/ahmed/aast/carbon/.venv/bin/python -m pytest dq/ -q                     # 0 failures
/home/ahmed/aast/carbon/.venv/bin/python manage.py check                     # System check OK
```
Manual probe (admin token from `/tmp/carbon_admin_token.txt`):
```bash
# 1. create standalone rule — definition-only body, bindings:[], NO flat name/rule_type/rule_level → 201
# 2. create with definition.level:"business" → 201 AND response rule_level == "business_rule"
# 3. PATCH a bound rule with field_assignments_write:[] → 400 (drift guard) with the drop message
# 4. PATCH same rule with replace_assignments:true + [] → 200 (confirmed drop)
# 5. PATCH a rule changing definition → response version incremented by 1
```
Run `.ai-toolkit/scripts/verify.sh backend` and paste tail.

---

## Phase A2 — Frontend blockers (Frontend Worker)

Files: `carbon-frontend/src/pages/dq/tabs/RulesTab.jsx`,
`carbon-frontend/src/pages/dq/tabs/DefinitionTab.jsx`,
`carbon-frontend/src/pages/dq/bindings.js`.

### T4. Empty bindings are valid (F2, D3)
`bindings.js` — in `resolveBindings()` DELETE the block:
```js
if (bindings.length === 0) { errors.push({...code:'empty'...}); }
```
Empty input returns `{ assignments: [], errors: [] }`.

### T5. Create template → standalone (F2)
`RulesTab.jsx` `openCreate()` — change `bindings: [{ table: '', field: '' }]` → `bindings: []`.

### T6. Omit field_assignments_write when no bindings (F3, D2)
In BOTH `RulesTab.jsx` `handleCreate()` and `DefinitionTab.jsx` `handleSave()`, build the body so
`field_assignments_write` is included ONLY when `assignments.length > 0`:
```js
const body = { definition: parsed };
if (assignments.length > 0) body.field_assignments_write = assignments;
```
(`DefinitionTab` also keeps `name`/`description`/`tag_ids` in the body — name stays because it's
the explicit top-level name field on the detail page, NOT derived.)

### Gates
```bash
cd /home/ahmed/aast/carbon/carbon-frontend
npm run lint                                      # 0 new errors
npm run build                                     # clean build
```
Then browser smoke (admin): New Rule → validate → create with empty bindings → snackbar "Rule created",
no 400; open an existing bound rule → Save Definition → confirm bindings unchanged (detail still lists
them). Paste console output.

---

## Phase B — Filters + version end-to-end (Backend + Frontend)

### T7. Backend: enable declarative filters (F4 — understated in QA)
`backend/dq/views.py` `DQRuleViewSet`:
```python
from django_filters.rest_framework import DjangoFilterBackend
filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
```
`filterset_fields` is already `['rule_level','rule_type','severity','is_active','dimension','archived']`
— adding the backend makes `severity`/`dimension`/`is_active`/`archived` actually filter (they are
dead today). Keep the manual `tag`/`data_table`/`data_field`/`include_archived` handling in
`get_queryset()` as-is. `rule_level`/`rule_type` are handled by BOTH — harmless (same predicate).
Verify no double-filter regression with a combined query.
Gate: `pytest dq/ -q`; curl `?severity=error&is_active=true&dimension=validity` returns only matches.

### T8. Frontend: forward all filter params (F4)
`carbon-frontend/src/api/dq.js` `listDQRules()` — replace the two-line body with a loop that forwards
`search, rule_level, rule_type, dimension, severity, is_active, tag, data_table, data_field,
include_archived` (skip null/undefined/''). Note backend uses `search` (not `q`) — RulesTab already
sends `search`.
Gate: `npm run lint`; browser: type in Search box → only matching rules; severity dropdown filters.

---

## Phase C — Polish (Frontend + Backend)

### T9 (F5) — Grid resize in hidden tabs
`carbon-frontend/src/components/DataGrid/CarbonDataGrid.jsx` (and its `useResizeContainer`). Cause:
grids mount in hidden MUI tabs at 0px and never re-measure. Fix options (choose one, verify visually):
lazy-mount on tab activation, or `autoHeight` + measured container width, or a `ResizeObserver` that
re-measures on tab visibility. Do NOT globally change grid props without checking the other DQ tabs.
Gate: browser — Rules grid spans full width at 1440px AND 768px; all columns visible; no `useResizeContainer` console error.

### T10 (F8) — a11y names
`RulesTab.jsx`: add `aria-label` to the Deactivate/Activate and Delete `IconButton`s (currently
Tooltip-title-only). Gate: `npm run lint`; browser snapshot shows accessible names.

### T11 (F9) — Table profile metrics
Backend `dq/views.py` table-profile serializer/endpoint: populate `completeness_pct` (NULL%) and
distinctness from available profile data instead of `null`/`—`. If the data genuinely isn't profiled,
return an explicit `profiled:false` marker and leave UI to render `—` — do NOT fabricate values.
Gate: `pytest dq/ -q`; browser Monitoring tab shows real percentages where data exists.

### T12 (F10) — React Router v7 flags
`carbon-frontend/src/main.jsx` (or router setup): add the v7 future flags
(`v7_startTransition`, `v7_relativeSplatPath`) or pin the major to silence the upgrade warnings.
Gate: `npm run build`; console warnings gone.

### T13 (NEW — found during A1 review) — normalizeServerErrors ignores the `details` envelope
`carbon-frontend/src/components/dq/ruleJsonValidation.js` `normalizeServerErrors()` only reads
`payload.definition` and `payload.error`. But `catalog/exceptions.py::data_trust_exception_handler`
wraps validation errors as `{error, message, details: {...}}`. So:
- the drift-guard 400 (`details.field_assignments_write`) surfaces as opaque "ValidationError", and
- the serializer's `anomaly_detect` whitelist rejection (`details.definition`) is also swallowed.
Fix: unwrap `payload.details` first (`const raw = payload?.details?.definition ?? payload?.definition`),
and read the drift-guard key (`payload?.details?.field_assignments_write`) into an actionable error row.
Do NOT change the envelope shape server-side (other clients may depend on it).
Gate: `npm run lint`; browser — trigger the drift guard (PATCH a bound rule with `field_assignments_write:[]`
via curl) and confirm the UI shows "Would drop N existing binding(s)", not "ValidationError".

---

## DO NOT TOUCH
- `backend/dq/models.py` — EXCEPT confirming `save()` doesn't overwrite `version` (T3). Do not change
  the denormalization logic.
- `backend/dq/rule_schema.py` — bindings already optional; do not reintroduce a required check.
- `carbon-frontend/src/components/dq/ruleJsonValidation.js` — already ADR-0006-correct.
- `carbon-frontend/src/components/dq/RuleJsonEditor.jsx` — Monaco editor is working; no changes.
- `e2e/`, `e2e/fixtures/users.ts` — test artifacts only, do not modify existing specs.

## HARD RULES (from `project.config.md`)
- PostgreSQL only (localhost:5432). Never SQLite.
- No hardcoded secrets. Reuse `/tmp/carbon_admin_token.txt` or `PERSONAS`.
- Report real terminal output — no silent tail-pipes.
- Each phase ends with `.ai-toolkit/scripts/verify.sh <domain>` green + pasted output in
  `TASK-RESULTS-DQ-RULES-AUDIT-FIX.md`.

## Definition of Done (per phase)
- Correct (does exactly the task), verified (terminal proof), tested (regression test for each P0/P1:
  F1 → serializer test that definition-only body creates a rule; F3 → test that `[]` without flag is
  rejected; F2 → test that `resolveBindings([])` returns no errors), safe (no antipatterns), clean
  (no debug leftovers), captured (TASK-RESULTS file).

## Fix order & dependency
A1 → A2 (A2's create relies on A1's derive) → B → C. A1 and B are both backend but keep them as
separate worker sessions (single concern each). C is independent and may run in parallel with B.
