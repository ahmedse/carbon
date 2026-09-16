# Screen Spec — Nibras Loans (HR schedule + My loans)
# Canonical per `.ai-toolkit/shared/frontend-ready.md` (RULE_29).
# Phase: NSR-3B · Seat: Nibras · 2026-09-16

---

## Artifact 1 — User Story + Acceptance

**Stories:**
1. As an **employee**, I want to see my loans and their status on My Dashboard (QA B6), so I know what is active, draft, paid off, or cancelled.
2. As an **HR user**, I want the loan expander to show the installment schedule generated on approval, so I can verify repayment rows without inventing a schedule in the UI.

**Acceptance (Given/When/Then):**

- **My loans happy:** Given `GET people/me/loan/` returns loans, when My Dashboard loads, then a My Loans card lists type, principal, term, start date, and status (chip + label).
- **My loans empty:** Given zero loans, when the card loads, then the user sees “You have no loans yet” (not an error).
- **My loans error:** Given the fetch fails, when the card renders, then a friendly error + Retry appear.
- **HR installments loaded:** Given a loan with persisted installments, when HR expands the row, then installment_no / due_date / amount / portions / status appear.
- **HR installments empty:** Given no installments yet, when HR expands, then copy explains installments are generated when the loan is approved.
- **HR after status save:** Given HR saves a loan (including status change toward active), when save succeeds, then loans and installments reload so newly materialized rows appear.

---

## Artifact 2 — Journey Map

```
Employee → /my (Dashboard)
  └─ parallel fetch people/me/loan/
      ├─ loading → skeleton
      ├─ error → message + Retry
      ├─ empty → empty copy
      └─ loaded → table (type, principal, term, start, status chip)

HR → People → Loans
  └─ list loans → expand row
      ├─ loading installments → caption
      ├─ error → ErrorAlert + Retry
      ├─ empty → “generated on approval”
      └─ loaded → installments table
  └─ edit/save status → reload loans + installments
```

---

## Artifact 3 — IA Placement

- **My loans:** card on existing `/my` dashboard (`MyDashboard.jsx` + `MyLoansCard.jsx`) — no new route, no sidebar change.
- **HR schedule:** expander inside existing People Loans page (`LoansPage.jsx`) — no new route.

---

## Artifact 4 — Composition Spec

```
MyDashboard
 └─ MyLoansCard  ← GET people/me/loan/ via fetchMyLoans (api/my.js → apiFetch)
      states: loading | error | empty | loaded
      Chip status = color + label (never color alone)

LoansPage
 └─ Table + Collapse expander
      └─ installments from fetchLoanInstallments
      empty → loanInstallmentsEmpty i18n
      after save → Promise.all([loadData, loadInstallments])
 └─ SystemDialog for create/edit (unchanged)
```

**Reuse audit:**
- [x] apiFetch only (RULE_10)
- [x] PageContainer / PageHeader on LoansPage; dashboard already wrapped
- [x] SystemDialog for loan form
- [x] No page-local breadcrumbs (RULE_9)
- [x] Theme tokens / Chip semantic colors — no new hex

---

## Artifact 5 — State Matrix

| Surface | States |
|---------|--------|
| MyLoansCard | loading, error(+retry), empty, loaded |
| LoansPage list | loading, error, empty, loaded |
| LoansPage expander | loading, error(+retry), empty (approval copy), loaded |
| Loan form SystemDialog | idle, submitting (saving), error snackbar, success snackbar |

---

## Artifact 6 — Data Contract

- `GET /carbon-api/people/me/loan/` → array of `LoanSerializer`  
  `{ id, employee, loan_type, principal, interest_rate, term_months, start_date, status, notes }`  
  (also tolerant of paginated `{ results }` via `normalizeMyLoans`)
- `POST /carbon-api/people/me/loan/` → existing submit path (`submitLoanRequest`) — out of scope for this card
- `GET /carbon-api/people/loan-installments/` → installments with `loan` FK
- `PATCH /carbon-api/people/loans/{id}/` → may change status; FE reloads installments after save
- 403 → surface as card/page error with retry (no amounts leak beyond API)

---

## Artifact 7 — A11y

- [x] Status = Chip color + text label
- [x] Error alerts include Retry button
- [x] Loading skeletons carry `aria-label` from `t('loading')`
- [x] Amounts / dates `dir="ltr"` on My loans table
- [x] Icon-only expand uses Tooltip title

---

## Artifact 8 — Performance

- Single list fetch for my loans (no N+1)
- Dashboard cards fetch in parallel (independent state)
- HR installments: one list endpoint filtered client-side by loan id (existing pattern; volume small)
- No new route chunk required

---

## Artifact 9 — i18n / RTL

- [x] Keys in `en/my.json` + `ar/my.json` (loansTitle, loansEmpty, columns, status labels)
- [x] HR empty copy in `en/people.json` + `ar/people.json` (`loanInstallmentsEmpty`)
- [x] Numeric cells `dir="ltr"`
- [x] No hardcoded user-facing English in new components
