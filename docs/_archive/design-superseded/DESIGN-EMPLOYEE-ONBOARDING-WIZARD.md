# DESIGN — Employee Onboarding Wizard (Nibras People & Payroll)

**Status:** Proposed (awaiting approval before implementation)
**Author:** Master Architect
**Scope:** `carbon-frontend/src/apps/people/EmployeesPage.jsx` (create/edit), `backend/people/{serializers,validation,views}.py`, `backend/dq/templates.py`
**ADR:** none yet — supersedes the flat `SystemDialog` form introduced for P3.

---

## 1. Problem statement

The employee create/edit surface in `EmployeesPage.jsx` is a single flat
`<Stack spacing={2}>` of ~16 raw `<TextField>`s inside a `SystemDialog`. The
user calls it (correctly) "ugly and an anti-pattern":

1. **No progressive disclosure** — identity, employment, compensation, and org
   assignment all dump into one scroll.
2. **Free-text for governed enums** — `nationality` and `nationality_code` are
   plain text fields even though `nationality` is a governed `mdm.ReferenceSet`
   enum; the user must hand-type "Kuwaiti" and "KWT". Same for
   `employment_type_code` / `contract_type_code` (free text, not dropdowns).
3. **No inline help** — `civil_id` ("12-digit Kuwait Civil ID"), `employee_no`
   (format), `basic_salary`, `rotation` ("config label, not calculation") carry
   zero guidance, format hints, or examples.
4. **No field-level DQ** — the model help_text for `civil_id` literally reads
   *"plain text, no validation of checksum"*; `employee_no` is only DB-unique
   (500 on dup, no friendly message); `gender` is free text ("NOT a governed
   enum") despite a seeded `gender` ReferenceSet.
5. **Thin validation** — client only checks 4 required fields (`org_unit`,
   `employee_no`, `full_name`, `join_date`); everything else is optional
   free-text that reaches the serializer unvalidated.

---

## 2. Audit findings (evidence)

### 2.1 Backend model — `backend/people/models.py`

| Field | Type | Current validation | Gap |
|---|---|---|---|
| `civil_id` | `CharField(32)` | none — "plain text, no validation of checksum" | No 12-digit format, no check-digit |
| `employee_no` | `CharField(64, unique=True)` | DB unique only | No format rule; dup → raw IntegrityError/500 |
| `nationality` | `CharField(100)` | free text | Duplicated by `nationality_code`; free text |
| `nationality_code` | `CharField(40)` | `_validate_reference_code('nationality')` | Validated but not offered as dropdown |
| `employment_type_code` | `CharField(40)` | `_validate_reference_code('employment_type')` | Same |
| `contract_type_code` | `CharField(40)` | `_validate_reference_code('contract_type')` | Same |
| `gender` | `CharField(16)` | none — "Free text … NOT a governed enum" | A `gender` ReferenceSet IS seeded; not validated |
| `date_of_birth` | `DateField(null)` | none | No age sanity, no dob↔civil_id cross-check |
| `rotation` | `CharField(32)` | none — "Config label only" | `rotation_pattern` ReferenceSet seeded; not offered as dropdown |
| `basic_salary` | `DecimalField(14,3)` | none (comp-gated in UI) | No non-negative/min check |

### 2.2 Serializer — `backend/people/serializers.py`

- `EmployeeSerializer` validates `nationality_code` / `employment_type_code` /
  `contract_type_code` via `_validate_reference_code` (lenient: empty OK,
  missing set OK per RULE_16). **`gender` and `civil_id` have no validator.**
- `nationality` (free text) is never reconciled against `nationality_code`.
- `employee_no` uniqueness surfaces as a 400 field error from DRF's
  `UniqueValidator` (acceptable), but the client does not pre-validate format.

### 2.3 Write gate — `backend/people/views.py` + `validation.py`

- `EmployeeListCreateView.post` runs the Tier-1 gate via
  `validate_write(instance)` → `dq.typed_gate.check_instances` (ADR 0025).
  The gate only fires for **bound** `ModelRuleAssignment` rows with
  `definition.enforcement.on_write: true`.
- **Today there are no gate-eligible DQ rules bound to `people.Employee`** in
  seed data — so `civil_id` / `employee_no` / `gender` are never gated at write.

### 2.4 DQ rule vocabulary — `backend/dq/catalog.py` + `templates.py`

- Gate-eligible types: `not_null`, `unique`, `allowed_values`, `range`, `regex`,
  `reference_integrity`, `threshold`.
- `templates.py` already ships an `employee_no` regex template
  (`^\d{4,5}$`, severity warn) — **uninstantiated**. No `civil_id` template, no
  `gender` template, no `nationality` template.

### 2.5 Frontend — `EmployeesPage.jsx`

- Flat `Stack` of `TextField`s; no `Stepper`, no `Autocomplete`, no
  `helperText`, no `MicroHelp` (the component exists in
  `src/components/MicroHelp.jsx` and is **unused** here).
- `nationality` and `nationality_code` are free text; `gender` is a hardcoded
  `<MenuItem>` list (only `male`/`female`) — no `gender` ReferenceSet fetch.
- `filterDefs` derives `nationalityOptions` from *existing rows* rather than the
  governed enum (filter can never show a nationality until it's been used once).

### 2.6 Governed enum source — `mdm`

- `ReferenceSet` → `get_current_values(as_of)`; `ReferenceValue` = code/label.
- `ReferenceSetSerializer` nests `values` (all of them). No name/slug filter on
  `ReferenceValueViewSet.get_queryset` (filters by `reference_set` id only).
- Seed (`seed_gofsco.py`) creates `nationality`, `employment_type`,
  `contract_type`, `job_family`, `gender`, `rotation_pattern` sets — so the
  data to power dropdowns **already exists**.

---

## 3. Research — how top systems do it, and the flaws to avoid

### 3.1 Patterns top systems share (Workday, SAP SuccessFactors, BambooHR, Rippling, Oracle HCM)

- **Wizard with semantically-grouped steps**, not one form: Identity →
  Employment → Compensation → Review. Each step has ≤ ~6 fields (cognitive
  load ≈ 7±2).
- **Typeahead/combobox for enums** (nationality, employment type, contract) —
  never free text. Autocomplete with localized labels + search.
- **Inline helper text + tooltips + format masks** (e.g. masked Civil ID input,
  `NNNNNNNNNNNN`); placeholder shows a realistic example.
- **Field-level validation with near-field feedback** (error under the field,
  red border, aria-describedby), not a single toast.
- **Idempotent employee number** — auto-suggested, uniqueness checked server-side
  with a friendly "already taken" message (never a raw 500).
- **Bilingual capture** (en/ar names) with explicit "name as on ID" guidance.
- **Progressive disclosure of sensitive data** — salary/compensation behind
  permission and visually separated.
- **Draft/autosave + review step** so a long wizard is never lost on refresh.

### 3.2 Known flaws to deliberately avoid

| Flaw (observed in real systems) | Our countermeasure |
|---|---|
| Everything on one screen → abandonment | 4-step wizard, ≤6 fields/step |
| Free-text nationality → "Kwt/KUWAIT/كويتي" soup | `Autocomplete` over ReferenceSet; store `code`, show localized `label` |
| Civil ID silently truncated or checksum ignored | 12-digit mask + check-digit DQ rule + serializer validator |
| Dup employee number → ugly 500 | Server unique + friendly 400; client pre-checks |
| No bilingual names → compliance rework later | en/ar given/family fields in step 1 |
| Salary visible to all → PII leak | Keep `useCompensationAccess` gating; compensation last, visually separated |
| No age/dob sanity | `date_of_birth` range + civil-id birth-date cross-check |
| "rotation" free text → inconsistent labels | `rotation_pattern` ReferenceSet dropdown |
| Gender free text → "M/male/ذكر" soup | `gender` ReferenceSet dropdown |
| Validation only on submit | Per-field inline errors + step-level gate before Next |

---

## 4. Proposed design

### 4.1 Wizard structure (4 steps)

```
┌─────────────────────────────────────────────────────────────┐
│  Add Employee                                    [Cancel]   │
│  ● Identity  ○ Employment  ○ Compensation  ○ Review         │
├─────────────────────────────────────────────────────────────┤
│  Step 1 — Identity                                          │
│   Full name*          [____________________]  (i)           │
│   English given       [____]  English family [____]         │
│   Arabic given        [____]  Arabic family  [____]  (i)    │
│   Civil ID (12)       [____-____-____]  (i)                 │
│   Date of birth       [date]  (i)                           │
│   Gender              [▾ male/female]  (i)                  │
│   Nationality         [▾ KWT — Kuwaiti]  (i)                │
│   Kuwaitization       [switch]  (i)                         │
│                                             [Back] [Next →] │
└─────────────────────────────────────────────────────────────┘

Step 2 — Employment
  Employee No*     [________]  (i)  format: 4–5 digits / GF-NNN
  Org unit*        [▾ …]       (i)
  Position         [▾ …]       (i)
  Manager          [▾ …]       (i)
  Employment type  [▾ …]       (i)
  Contract type    [▾ …]       (i)
  Join date*       [date]      (i)
  Rotation         [▾ …]       (i)

Step 3 — Compensation (visible only if canViewCompensation)
  Basic salary*    [0.000]     (i)  KWD, monthly
  (sensitive notice + RevealAmount-style disclosure)

Step 4 — Review
  Read-only summary grouped by section + inline DQ result badges
  (civil_id ✓ / employee_no ⚠ format / …)  → [Submit]
```

- `(i)` = `MicroHelp` tooltip; `(i)` next to a masked/date field shows format +
  example.
- Progress via MUI `Stepper` (non-linear disabled — must complete prior steps).
- State is a single `form` object (today's `EMPTY_FORM` + en/ar name fields);
  per-step validation gates `Next`.

### 4.2 Component inventory (reuse before create — design-system RULE 2)

| Need | Reuse | Notes |
|---|---|---|
| Dialog | `SystemDialog` | keep (drag/resize/modal) |
| Stepper | MUI `Stepper` (as in `BulkImportWizard.jsx`) | no new primitive |
| Enum dropdown | MUI `Autocomplete` (used in `MDMPage`, `ScheduleDialog`) | freeSolo off, localized label |
| Help tooltip | `MicroHelp` (`src/components/MicroHelp.jsx`) | add help keys to `helpTexts.js` |
| Field wrapper | `FormField` (`src/components/Form/FormField.jsx`) | label + helper + error |
| Action bar | `SaveBar` if needed, else `DialogActions` | |
| Review badges | MUI `Chip` (status = color + label, RULE 5) | |
| Date/amount formatting | `people/utils.js` (`formatDate`, `formatAmount`) | already exists |

**New files (one source of truth each):**
- `carbon-frontend/src/apps/people/EmployeeWizard.jsx` — the 4-step wizard
  (owns step state, per-step validation, review).
- `carbon-frontend/src/apps/people/useReferenceOptions.js` — hook that fetches
  ReferenceSet values by name/slug and returns `{value: code, label}` options
  (with localized label fallback to `code`), plus loading/error/empty states
  (design-system RULE 4).
- `backend/people/civil_id.py` — pure Kuwait Civil ID validation (format mask +
  check-digit). **Sourced from PACI / GOSI spec** — a `checksum` comment
  carrying the authoritative source URL, NOT a law value guessed in code
  (RULE_16 no-fabrication).
- `backend/people/dq_seed.py` (management command or migration data) — seed the
  gate-eligible DQ rules + `ModelRuleAssignment` bindings (below).

### 4.3 Backend changes

**`people/serializers.py` — `EmployeeSerializer`**
- Add `validate_civil_id` → `civil_id.validate()` (format + check-digit), empty
  allowed (field stays optional for bulk ERP imports; see §6).
- Add `validate_gender` → `_validate_reference_code(value, 'gender')`.
- Add `validate_rotation` → `_validate_reference_code(value, 'rotation_pattern')`
  (keeps legacy free-text rows lenient — only rejects when the set exists).
- Add cross-field `validate()`:
  - `nationality_code` set ⇒ reconcile `nationality` to the ReferenceValue
    label (or error if both set and inconsistent).
  - `kuwaitization=True` ⇒ `nationality_code` must be `KWT` (warn, not block —
    expats can be counted in some programs; configurable).
  - `date_of_birth` must be ≤ 16..100 years ago (configurable range), and
    `date_of_birth` < `join_date`.

**`people/views.py`**
- `EmployeeListCreateView.post` already gates via `validate_write`. No change
  needed except: catch `IntegrityError` on `employee_no` unique and return a
  friendly 400 `{employee_no: "already taken"}` instead of 500.

**`dq/templates.py`** — add three templates:
- `civil_id` — regex `^\d{12}$` (validity, severity error).
- `civil_id_check_digit` — a new `range`-adjacent **custom** validator is NOT in
  the vocabulary; instead implement check-digit in the serializer (§4.3) and
  expose the *format* rule as DQ `regex` (the checksum stays code-level since
  `regex` can't compute mod-11).
- `gender` — `allowed_values` over `['male','female']`.
- `nationality` — `allowed_values` over seeded nationality codes (kept in sync
  with the set; empty = skip per RULE_16).

**`dq` bindings** — seed `ModelRuleAssignment` rows bound to `people.Employee`:

| rule | field | type | severity | enforcement.on_write |
|---|---|---|---|---|
| civil-id-format | `civil_id` | `regex` `^\d{12}$` | error | true |
| employee-no-format | `employee_no` | `regex` `^\d{4,5}$` | warn | true |
| gender-allowed | `gender` | `allowed_values` | error | true |
| nationality-allowed | `nationality_code` | `allowed_values` | warn | true |

*(`civil_id` check-digit is enforced in the serializer because the DQ
vocabulary has no checksum type; see ADR 0025 for the typed gate.)*

### 4.4 DQ validation rules (the full set)

| # | Rule | Layer | Severity | Purpose |
|---|---|---|---|---|
| 1 | `civil_id` is 12 digits | serializer + DQ regex | error | format |
| 2 | `civil_id` mod-11 check digit | serializer (`civil_id.py`) | error | integrity |
| 3 | `employee_no` format 4–5 digits (or `GF-\d{3}`) | serializer + DQ regex | warn | consistency |
| 4 | `employee_no` unique | DB + serializer | error | idempotency |
| 5 | `gender` ∈ governed set | serializer + DQ allowed_values | error | enum |
| 6 | `nationality_code` ∈ governed set | serializer (exists) + DQ | warn | enum |
| 7 | `nationality` label == `nationality_code` label | serializer cross-field | warn | consistency |
| 8 | `employment_type_code` / `contract_type_code` ∈ set | serializer (exists) | error | enum |
| 9 | `date_of_birth` age ∈ [16, 100] | serializer | warn | sanity |
| 10 | `date_of_birth` < `join_date` | serializer | error | sanity |
| 11 | `kuwaitization` ⇒ `nationality_code == 'KWT'` | serializer | warn | compliance |
| 12 | `basic_salary` ≥ 0 | serializer + DQ range | error | financial |

### 4.5 Frontend changes

- Replace the flat `Stack` in `EmployeesPage.jsx` with `<EmployeeWizard>`.
- `useReferenceOptions('nationality' | 'employment_type' | 'contract_type' |
  'gender' | 'rotation_pattern')` fetches `mdm/reference-sets/`, finds the set
  by slug, maps nested `values` → options.
- `Autocomplete` for `nationality_code` stores `code`, displays localized
  `label`; selecting auto-fills `nationality` (display) and toggles
  `kuwaitization` hint when `KWT`.
- Masked input for `civil_id` (12 digits, `#### #### ####`); placeholder
  `e.g. 289 121 300 456`; helperText shows a valid example; error under field.
- `employee_no` gets helperText `format: 4–5 digits (e.g. 1024)` and a
  "check availability" affordance (or rely on server 400 → inline error).
- Per-step `Next` disabled until the step validates; `Review` shows DQ badges
  and the final `Submit`.
- Keep `handleChange` checkbox branch (CB-32) and the `basic_salary`
  `useCompensationAccess` gate.
- i18n: add all new keys to `people.json` (en + ar, key-parity via
  `node scripts/check-i18n-keys.js`); help text keys to `helpTexts.js` (en/ar).
- `MicroHelp` `lang` follows active `i18n.language`.

---

## 5. Phased rollout

| Phase | Scope | Exit gate |
|---|---|---|
| **P1 — Enums + help** | `useReferenceOptions`, Autocomplete for nationality/employment/contract/gender/rotation, MicroHelp + helperText + masks, i18n keys | create/edit via wizard step 1–2, no more free-text enums |
| **P2 — DQ + serializer hardening** | `civil_id.py`, serializer validators, DQ templates + seed bindings, friendly unique error | `civil_id`/`employee_no`/`gender`/`nationality` validated at write; tests green |
| **P3 — Wizard + review** | `EmployeeWizard` 4-step + review + compensation disclosure | full wizard replaces flat form |
| **P4 — Polish** | autosuggest employee_no, draft persistence, bulk-import compatibility | optional; user-visible parity |

Recommended: ship **P1+P2+P3 together** as one cohesive form (they're
interdependent), with P4 as a fast-follow.

---

## 6. Risks & decisions to confirm

1. **Strict vs lenient `civil_id`** — existing seeded rows (`seed_gofsco.py`)
   use 12-digit strings that *may not* pass a mod-11 check (they look synthetic).
   Proposal: enforce **format** (12 digits) as error, enforce **check-digit** as
   *warning* until real PACI data is backfilled, then escalate to error.
   → *Needs sign-off.*
2. **`employee_no` format** — template says `^\d{4,5}$` but seed data uses
   `GF-001`. Proposal: accept `\d{4,5}` OR `[A-Z]{2}-\d{3}`. → *Confirm the
   canonical pattern.*
3. **`nationality` free-text field** — keep for display/back-compat, drive from
   `nationality_code` on new writes. Do NOT delete the column (migration risk).
4. **`gender`** — currently free text with a seeded set. Promotion to governed
   enum is backwards-compatible (existing `male`/`female` rows already match).
5. **Check-digit source** — Kuwait Civil ID check digit must be implemented from
   the PACI spec (sourced), not guessed. If no authoritative source is
   available in-repo, ship format-only and flag the checksum as a follow-up
   (RULE_16).

---

## 7. Test plan

**Backend (`python -m pytest -p no:cacheprovider backend/people`)**
- `civil_id` format (valid 12, invalid length, non-digit, check-digit pass/fail).
- `employee_no` unique → friendly 400; format warn.
- `gender` / `nationality_code` / `rotation` invalid code → 400; valid → 201.
- cross-field: dob<join_date, kuwaitization↔KWT, nationality↔code reconcile.
- Tier-1 gate: bound DQ rules block write (422) and do not persist (extend
  `test_api.py` pattern).

**Frontend (`npx vitest run`)**
- `useReferenceOptions` loading/error/empty/loaded (4 states).
- `EmployeeWizard` per-step validation gates Next; review summary renders.
- Autocomplete sets `code` + display label; civil_id mask rejects non-digit.

**i18n** — `node scripts/check-i18n-keys.js` (en == ar parity).

---

## 8. Out of scope (deferred)

- Photo upload in wizard (keep in 360 Profile tab).
- Bulk-import validation UI (separate `BulkImportWizard`).
- `nationality` column removal / full enum migration.
