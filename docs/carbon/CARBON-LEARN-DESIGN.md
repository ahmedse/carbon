# Carbon learning design (microlearning by role)

**Subject:** `carbon.journey.learn` (not registered on the ladder)  
**Product:** Carbon on AASTMT.  
**Status:** Draft, 30 Sep 2026. Nothing here is built.  
**Limit:** This file designs a teaching layer. It does not score onboarding,
does not close O1, and does not store a kilogram. `/carbon/onboarding` stays
the inventory gate. Lessons only link to it.

Companion files: `docs/carbon/O1-ONBOARDING-SPEC.md`,
`docs/carbon/O1-ROLLOUT-PLAN.md`, `domain_packs/carbon/processes/inventory.onboarding.lifecycle.yaml`,
`.ai-toolkit/decisions/0046-pulse-chat-no-host-mutation-stage.md`.

Visual mockups: canvas `carbon-learn-design.canvas.tsx`.

---

## Problem

The carbon app has one onboarding surface, and it answers "is the inventory
ready". It does not teach the person who just signed in what their job is,
what they may not do, or why a screen looks the way it does. Five kinds of
people use Carbon and each needs about a dozen minutes, not a manual.

## Players (read from code, 30 Sep 2026)

| Player | Group | Can | Cannot |
|--------|-------|-----|--------|
| Data owner | `dataowners_group`, scoped by `ScopedRole` (org unit, optional module) | Enter data. View calculations, verification, console, dashboard. | Calculate, lock, submit, verify, manage factors. |
| Carbon lead | `carbon_lead`, or `admins_group` | Factors, rules, targets, periods, coverage. Trigger calculations. Enter data. Submit, verify, reject. | Nothing carbon-specific. |
| Analyst | `analysts_group` | Cross-org read. Analytics. Reports. | Enter data. Admin work. |
| Auditor | `auditors_group` | Read calculations, verification, console, dashboard, data. | Verify or reject (no `carbon:verify_data`). |
| Viewer | `viewers_group` | Read console, dashboard, calculations. | Everything else. |
| Chairman | Not a role | Opens `/carbon/chairman` (nav role `*`). Figures follow the org units the viewer can see. | |

`verifiers_group` is seeded for `verifier1` in `seed_aastmt_showcase.py` but has
no entry in `GROUP_CAPABILITIES`. That user has no carbon capability.

## Gaps found while reading (teach honestly, fix separately)

1. The auditor cannot verify. Only `carbon_lead` and platform admins hold `carbon:verify_data`. Decision needed: is auditor independence intended.
2. One person can submit and verify. `submit` needs `carbon:manage_reporting_periods`; `verify` needs `carbon:verify_data`; `carbon_lead` holds both. Two distinct people are declared only for `cover_or_exclude` in the process YAML.
3. `VerificationPage.jsx` shows Approve and Reject with no capability check. A non-verifier gets 403 after the click.
4. `EMISSIONS_AUTO_CALC` defaults to false and `CalculateAPIView` needs `carbon:trigger_calculations`. A data owner enters a row and no total moves until a lead calculates.
5. `PeriodLockService.set_period_tables_locked` locks every table with an active calculation rule, not only the tables of one org unit.
6. `ChairmanService` sums all calculations across all periods. The header period is a label. The page already warns that its figure is not O1.

Lessons D3, D5, L6, U4, and H1 exist because of these six lines.

---

## Principles

1. **Scoped to the person.** The catalog is computed from the caller's capabilities and org scope, not from a title. Someone who holds two org units sees both.
2. **One screen, one decision.** A lesson is 90 to 180 seconds and teaches one thing on the real screen.
3. **A live object, never a sample.** Each lesson names something the user can reach: the open period, one of their sources. No demo data. No sample tonne.
4. **Proof from the host.** Done means the host shows it (a row the user created, a correct answer computed from their own sources). A click on Next is not proof.
5. **Teach the refusal.** Every lesson has one "do not" line taken from a rule (`Close from Open is 409`; a missing month is a gap, not zero).
6. **No writes from the lesson.** The lesson links to the host screen. Chat stays a reader (ADR-0046).
7. **English and Arabic from day one.** The user model has `language` (en/ar). The coach must render RTL.

---

## Track selection

Tracks are computed on the server from capabilities. A person can hold several.

| Track | Available when | Recommended when |
|-------|----------------|------------------|
| C Common | Always (carbon brand) | Always first |
| D Data owner | `carbon:enter_data` | Has `enter_data` and no admin capability |
| L Carbon lead | Any of `manage_reporting_periods`, `trigger_calculations`, `verify_data`, `manage_inventory_coverage`, `manage_emission_factors` | Has any of them |
| A Analyst | `generate_reports` or `view_analytics` | Has either, and is not D or L |
| U Auditor | `view_verification` and `view_calculations` | Has both, and none of `enter_data`, `generate_reports`, admin caps |
| H Reader (chairman) | `view_dashboard` or `view_console` | Has no other recommended track |

"Next up" order when several apply: **D, L, A, U, H** (data gathering first). Inside L, lessons are ordered by `order`, not by id: the gathering side (L2 open period, L3 sources, L5 cover or exclude) comes before the calculate-and-close side (L1, L4, L6, L7). Platform superusers (`ahmed`) get every track, and D is recommended, then L.

Hub grouping: each track shows a **Gathering** group (lessons with `phase: gather`) above an **Analysis and close** group. Lesson ids stay stable; only `order` and `phase` in the pack decide placement.

---

## Lesson catalog (28)

Priority: filling and gathering data comes first. The gathering lessons are D1 to D7, C2, C3, L2, L3 and L5. They ship before any lesson about calculating, closing, reporting or auditing. There is no lesson about the menu or roles.

Minutes are targets, not measurements.

### C Common

| Id | Lesson | Min | Live object | Done when |
|----|--------|-----|-------------|-----------|
| C2 | Read a period's status | 2 | The current period | Answer: what the status allows |
| C3 | Tiers and "not assured" | 2 | One source status | Answer: which tier may leave the organisation (3 or better) |

### D Data owner

| Id | Lesson | Min | Live object | Done when |
|----|--------|-----|-------------|-----------|
| D1 | What I owe this period | 2 | Your source modules, empty ones first | Answer: which source has no rows |
| D2 | Enter one activity row | 3 | One source: scope, unit, factor unit | Host: a row you created exists in your source since you started |
| D3 | Why my total didn't move | 2 | Your last row, and the period | Answer: who runs the calculation |
| D4 | Read my quality status | 2 | One asset: passing, warning, failing | Answer: what to fix first |
| D5 | Locked or rejected: what now | 2 | Period status, rejection notes | Answer: can I edit, and who unlocks |
| D6 | Hand-off to the lead | 2 | Your source and its coverage status | Answer: who covers or excludes |
| D7 | Bring many rows: bulk import | 3 | Your table and its fields | Answer: the wizard's three steps in order (upload, map, validate), one file up to 10 MB |

### L Carbon lead

| Id | Lesson | Min | Live object | Done when |
|----|--------|-----|-------------|-----------|
| L1 | Boundary first | 2 | The open period's boundary | Host: period has an approach of the three |
| L2 | One open period | 3 | The open periods (count 0, 1, or more) | Host: exactly one status open |
| L3 | Declare sources and bind a factor | 3 | Declared sources, matching factors | Host: source has an active factor by scope and unit |
| L4 | Run a calculation | 3 | A rule, and the audit row it writes | Host: a `CalculationAudit` row by you |
| L5 | Cover or exclude, with a reason | 3 | One source status | Host: status is covered, or excluded with a reason |
| L6 | Lock, submit, verify or reject | 3 | Period state machine position | Answer: next legal transition |
| L7 | Check the quote | 2 | Calculation summary vs chairman figure | Answer: which figure is the linked-table summary |

### A Analyst

| Id | Lesson | Min | Live object | Done when |
|----|--------|-----|-------------|-----------|
| A1 | Compare periods | 2 | Two periods you may read | Answer: which is verified |
| A2 | Generate a report and label it | 3 | A saved report config | Answer: what the footer must say |
| A3 | Mine versus everyone's | 2 | Your org scope | Answer: what changes across org units |

### U Auditor

| Id | Lesson | Min | Live object | Done when |
|----|--------|-----|-------------|-----------|
| U1 | Trace a figure to its row | 3 | One calculation and its rule, factor, row | Answer: who entered it and when |
| U2 | Read the period trail | 2 | Governance events on a period | Answer: who moved it to submitted |
| U3 | Export audit | 2 | Export audit rows in your scope | Answer: what an export row records |
| U4 | What you see but do not decide | 2 | Verification page | Answer: who may approve |

### H Reader (chairman)

| Id | Lesson | Min | Live object | Done when |
|----|--------|-----|-------------|-----------|
| H1 | Read the headline | 2 | Chairman headline, header period | Answer: what the number sums |
| H2 | Coverage by campus | 2 | Campus coverage rows | Answer: which campus is not covered |
| H3 | Priority actions and owners | 2 | Coverage actions | Answer: which action is blocked |
| H4 | When the number is not O1 | 1 | The onboarding link | Answer: where the O1 figure lives |

---

## Lesson anatomy

Four cards, one screen each.

1. **Know.** One sentence on what this screen decides, plus the live object chip.
2. **Do or look.** The single action, with the real element highlighted.
3. **Check.** One question built from the live object. Wrong answers explain, they do not fail the user.
4. **Next.** What happens after this step, and the next lesson.

Every lesson carries one **do not** line. It is shown on card 2 and is copied
from a rule id where one exists (CR-DQ-01, CR-PER-01, CR-EXC-01, CR-PULSE-01).

Practice is real. There is no sandbox database. D2 is a real entry on the real
screen, behind the same locks and the same 401/403 gates. A user who is not ready
presses "Later" and the lesson stays offered.

## Surfaces

| Surface | Where | Behaviour |
|---------|-------|-----------|
| Hub | `/carbon/learn`, sidebar "My learning" under Onboarding, role `*` | Header shows role chips and org units. One "Next up" lesson. Tracks with progress. Blocked lessons show the reason. |
| Coach | Docked panel on the real page, 360 px, `end` edge (left in Arabic) | Four cards. Highlights `data-learn` targets. Never covers the target. |
| Nudge | Slim banner at the top of My Data, Calculations, Verification, Chairman | "New here? 2-minute lesson." Dismissible. Snooze 7 days. |
| Help hook | `MicroHelp` `?` on a field | Adds "Open lesson" when a lesson covers that field. |
| Blocked | Hub and Coach | Reads host reason (`open_period_count`, no source, no factor). Links to the fixing screen. |

Nothing opens by itself after the first login nudge.

---

## Data and API

### Content

- `domain_packs/carbon/learn/lessons.yaml`: id, track, minutes, `requires` (capabilities), `live` (object kind), `done` (signal kind), `screen` path, `rule` id, step keys.
- `carbon-frontend/src/i18n/locales/{en,ar}/learn.json`: all copy. A key-parity test fails if the two files differ.

### Storage

`emissions.LearnProgress`

| Field | Meaning |
|-------|---------|
| `user` | FK, PROTECT |
| `lesson_id` | e.g. `D2` |
| `lesson_version` | int; content bump re-offers only when the pack sets `reoffer: true` |
| `state` | `offered`, `started`, `done`, `snoozed` |
| `started_at`, `done_at`, `snoozed_until` | timestamps |
| `signal` | `host_row`, `answer`, `host_state` |

Unique on `(user, lesson_id)`. The table stores no kilogram and no answer text.

### Endpoints (brand gate `CarbonBrandPermission`, Nibras 403)

| Method | Path | Returns / does |
|--------|------|-----------------|
| GET | `/carbon-api/carbon/learn/` | Tracks, lessons with `state`, `unlocked`, `blocker`, `next_id`. One call. |
| GET | `/carbon-api/carbon/learn/<id>/` | Steps, live object, question with options. |
| POST | `/carbon-api/carbon/learn/<id>/progress/` | `event` in `started`, `answered`, `snooze`. Writes `LearnProgress` only. |

### Code

`backend/emissions/learn.py`: `evaluate_lessons(caps, org_ids, host_snapshot)` is pure,
like `evaluate_o1`. It imports nothing from `people` or `ai.engine`. Reads happen in
one loader. Live objects come from `org_scope_for_capability(user, CARBON_READ)`,
so a lesson cannot name another org unit's source.

`kg`, `tonnes`, and `factor_value` never appear in any learn payload.

---

## Frontend

| File | Role |
|------|------|
| `pages/carbon/LearnHubPage.jsx` | Hub |
| `components/learn/LessonCoach.jsx` | Docked panel, four cards |
| `components/learn/LearnNudge.jsx` | Page banner |
| `hooks/useLearn.js` | Fetch, progress events |
| `apps/carbon/manifest.js` | Item "My learning", role `*` |
| Carbon pages | `data-learn="<page>.<target>"` attributes only |

- Route `/carbon/learn` under `AppEnabledRoute appId="carbon"`.
- No `MENU_ITEM_CAPABILITIES` entry for the new label (same reason as Inventory onboarding).
- Colours only from theme palette. Spacing and type from `themeTokens`.
- Coach anchors on the logical end edge so RTL flips it.
- A missing `data-learn` target (permission, empty table) drops the highlight and keeps the text.

---

## Capabilities and roles

| Gate | Who | Allows |
|------|-----|--------|
| Authenticated + `CarbonBrandPermission` | Any user on a brand with carbon | The three endpoints |
| Each lesson's `requires` | Server-side `has_capability` | Lesson appears unlocked |
| Pulse Chat | Read only | May name a lesson id. Never sets `done`. |
| Team view (later phase) | Carbon lead | Completion counts for org units they manage. No answers. |

## Failure modes

| Condition | Result | What does not happen |
|-----------|--------|----------------------|
| Zero open periods | Lessons needing a period show `open_period_count` and link to Reporting Periods | No invented period |
| Two open periods | Lists both, sends the lead to Lock | Lesson does not choose which |
| Lesson needs a capability the user lacks | Hidden from the list; a "why" line on the hub | No 403 page |
| User has no source in scope | D lessons show "no source assigned" | No cross-unit example |
| `data-learn` target missing | Card 2 becomes text-only | No blocked lesson |
| Verification page shows Approve to a non-verifier | U4 and L6 say who may approve | Lesson does not fix the button |
| GET fails | Alert + Retry | No cached progress claim |
| Nibras brand | 403, route redirects home | Not a bug |
| Content bumped, `reoffer` false | Done stays done | No re-quiz |
| Arabic key missing | Test fails at build | Silent English fallback in production copy |

## Budget

- Hub: one GET. Lesson: one GET. No polling.
- Query count is asserted in `LRN-PRF-QUERIES`. The number is set when measured. No millisecond SLO is declared.

## Test plan

Planned. A row is not a plan until the named test fails when the rule breaks.

| Id | Suite | Proves |
|----|--------|--------|
| LRN-COR-TRACKS | `backend/emissions/tests/test_learn_tracks.py` | Each seeded group maps to the track table. Auditor gets no L lesson. `verifiers_group` gets C only. |
| LRN-COR-SCOPE | Same | Live object lists only sources in the caller's org scope. |
| LRN-COR-NOKG | Same | No `kg`, `tonnes`, or `factor_value` key in any payload. |
| LRN-COR-STOP | Same | Two open periods block D2 and L2 with `open_period_count`. |
| LRN-COR-DONE | Same | `host_row` counts only rows created by the caller, in scope, after `started_at`. |
| LRN-SEC-BRAND | `test_learn_api.py` | 401 unauthenticated. Nibras 403. |
| LRN-SEC-WRITE | Same | POST progress changes only `LearnProgress`. Period and `DataRow` counts unchanged. |
| LRN-USE-HUB | `LearnHubPage.test.jsx` | Skeleton, empty, blocked reason, Alert + Retry. |
| LRN-USE-COACH | `LessonCoach.test.jsx` | Four cards. Missing target still readable. |
| LRN-USE-RTL | Same | Arabic sets `dir="rtl"` and the panel anchors to the start edge. |
| LRN-I18N | `learn-i18n.test.js` | `en` and `ar` keys match. |
| LRN-E2E-AR | `e2e/journeys/journey-learn-data-owner-ar.spec.ts` | Data owner completes D1 to D3 in Arabic. |

## Module boundary

| May write | Must not write |
|-----------|----------------|
| `backend/emissions/learn*.py`, model, migration, `urls.py` route | `backend/ai/engine/**` |
| `domain_packs/carbon/learn/**` | `backend/people/**` |
| `carbon-frontend/src/pages/carbon/Learn*`, `components/learn/**` | `carbon-frontend/src/apps/{people,my,team}/**` |
| `learn.json` en and ar | Pulse tools (REQUEST to the Pulse seat) |
| Manifest item, `data-learn` attributes | `docs/carbon/evidence/O1-smart-village.json` |

## Phases

| Phase | Ships |
|-------|-------|
| P0 | Model, `GET /learn/`, hub, coach, nudge. Data-entry core: D1, D2, D3 in English and Arabic. |
| P1 | Rest of gathering: D4, D5, D6, D7, C2, C3, and the lead's gathering side L2, L3, L5. Blocked-state reasons from `evaluate_o1` codes. `MicroHelp` "Open lesson" on the data-entry page. |
| P2 | Calculate and close: L1, L4, L6, L7. |
| P3 | Analyst, auditor, reader tracks (A, U, H). Lead team view (counts only). A Pulse pointer to a lesson id, by REQUEST. |

Data owner path is complete at the end of P1: `D1 → D2 → D3 → D4 → D5 → D6 → D7`.

## Decisions needed

1. Should the auditor be able to verify, so U4 can teach approving instead of refusing.
2. Should submit and verify be two distinct people, as `cover_or_exclude` already is.
3. Is "chairman" a plain reader, or does the board want its own group.
