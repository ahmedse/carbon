# Screen spec — O1 quote honesty (Chairman and Coverage)

**ADR-0020 · ADR-0046 · frontend-ready 9 artifacts**  
**Routes:** `/carbon/chairman`, `/carbon/admin/inventory-coverage`  
**Owner:** carbon-inventory-lead  
**Locked:** 2026-09-29  
**Limit:** These pages may show numbers that are in their GET payload. They
must not call those numbers the O1 Smart Village footprint. This spec does
not hide a legal chairman payload. It does not POST a period. It does not
write the Rank 5 evidence file.

Companion: `docs/carbon/O1-ONBOARDING-SPEC.md` Complete system,
`docs/carbon/O1-READINESS-AUDIT.md`.

---

## 1. Story

As board and as inventory lead, I see platform-wide tonnes and coverage
labeled as not O1, so that staff do not publish a Smart Village footprint
from `ChairmanService`.

Acceptance:

- Chairman already states platform-wide in the Total Footprint subtitle
  (`all periods, all campuses`). Keep that. Add Alert severity warning
  (not error) with `chairman.notO1Footprint` when the page has rendered
  a headline tonne or a coverage percent.
- English: "These figures are platform-wide. They are not the O1 Smart
  Village footprint. Quote a kilogram only from this period's calculation
  summary."
- Alert action: one Button, color inherit, size small, navigates to
  `/carbon/onboarding`. Label `chairman.openOnboarding` / "Inventory
  onboarding". It does not POST.
- Do not change `footprint_tonnes` or invent a second total.
- Tooltip on Inventory Coverage must not say "Goal: 100%". That default
  is forbidden during O1 (CR-COV-01).
- Coverage goal form does not prefill `target_coverage_pct` with 100.
  Empty stays empty. The model still requires a percent when a goal is
  saved; the lead types it after both O1 sources exist.
- EN and AR keys live in `emissions` namespace.
- No hex. No new MUI Table. No rewrite of the KPI grid in this slice.

## 2. Journey

```
GET chairman payload
        │
        ├─ loading     existing spinner in PageContainer
        ├─ error       existing Alert
        └─ loaded      warning Alert (not O1) + existing headline
                │
                └─ Inventory onboarding  → /carbon/onboarding
```

Coverage page: period selector stays. After `PageHeader`, when `coverage`
has loaded, show the same warning Alert (`chairman.notO1Footprint`) and
the same onboarding Button. Goal dialog does not default 100.
New-goal `scope` is `1+2` (CR-COV-01). It is not `1+2+3`.
`target_coverage_pct` initial value stays `''`.

## 3. IA

| Surface | Value |
|---------|--------|
| Chairman | `/carbon/chairman` · existing page `ChairmanDashboard.jsx` |
| Coverage | `/carbon/admin/inventory-coverage` · `InventoryCoveragePage.jsx` |
| Onboarding | `/carbon/onboarding` · not this page |

## 4. Composition

Chairman: existing layout. Insert one MUI `Alert` severity `warning` after
the page header `Box`, before Headline Metrics. Action is one `Button`.

Coverage: after `PageHeader`, one warning Alert and one Button to
`/carbon/onboarding`. Goal `target_coverage_pct` initial value `''`.
New-goal `scope` initial value `1+2`.

## 5. State matrix

| Phase | Render |
|-------|--------|
| Chairman loaded with a payload | Warning Alert + existing KPIs |
| Chairman loading or error | No extra warning |
| Coverage loaded | Warning Alert + existing period selector and stats |
| Coverage goal create | `target_coverage_pct` is blank. `scope` is `1+2` |

## 6. Data contract

Chairman GET is unchanged. This spec does not add fields. It does not
call `evaluate_o1`.

## 7. Accessibility

Alert has an action control. Color is not the only meaning: the sentence
says platform-wide and not O1.

## 8. Performance

No extra GET. No poll.

## 9. i18n / RTL

| Key | EN | AR |
|-----|----|----|
| `chairman.notO1Footprint` | These figures are platform-wide. They are not the O1 Smart Village footprint. Quote a kilogram only from this period's calculation summary. | هذه الأرقام على مستوى المنصة. ليست بصمة القرية الذكية لـ O1. اقتبس الكيلوغرام فقط من ملخص حساب هذه الفترة. |
| `chairman.openOnboarding` | Inventory onboarding | تهيئة المخزون |
