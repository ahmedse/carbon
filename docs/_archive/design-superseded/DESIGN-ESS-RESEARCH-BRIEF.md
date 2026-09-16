# Enterprise Employee Self-Service (ESS) — Research Design Brief
# Produced by: Scientific Researcher role
# Target: Django 5.2 + React 19.1 + MUI v7.1 (Carbon/Nibras platform)
# Date: 2026-09-06
# Reads-with: DESIGN-NIBRAS-ENTERPRISE-HR-DATA-MODEL.md, DESIGN-PLATFORM.md

---

## 0. SCOPE & METHOD

**Research question:** What do the top enterprise ESS systems do, and what design
decisions produce or destroy value? Synthesise into actionable guidance for a
production ESS module on the Carbon/Nibras SME platform.

**Comparative corpus:** SAP SuccessFactors Employee Central (EC) + ESS, Workday "Me"
hub, Oracle HCM Cloud "Me" page, ServiceNow HR Service Delivery (HRSD),
BambooHR (SMB leader), Personio (European SME). All studied at v2024/2025 feature
parity level.

**Output format:** Dense, decision-ready — no marketing copy, no link lists. Every
section ends with a "Carbon/Nibras take" stating what to adopt, adapt, or avoid.

---

## 1. TOP SYSTEMS — MODULES AND EMPLOYEE ACTIONS

### 1.1 SAP SuccessFactors Employee Central (EC) + ESS

**Architecture:** Thick-client module suite hosted on SAP BTP. ESS is a portal
overlay on top of EC core (org chart, position management, global assignment).

**Modules and what the employee CAN DO (not just view):**

| Module | Employee actions |
|--------|-----------------|
| **Personal information** | Edit address, phone, emergency contact, bank account (WPS-routing), ID documents; upload scanned copy; trigger verification workflow |
| **Leave / Absence** | Submit request (type, dates, partial-day, note); view balance *before* submitting; cancel submitted (within configurable window); view team absence calendar; download leave certificate |
| **Time** | Clock in/out (mobile + kiosk); submit correction request; submit timesheet for weekly approval; view approved hours vs contract hours |
| **Payroll / compensation** | View payslip (HTML or PDF); download historical slips; view year-to-date totals; run "what-if" compensation statement; submit bank account change (triggers approval) |
| **Benefits** | Enroll in plans during open-enrollment window; view enrolled benefits + coverage summary; trigger life-event change (marriage, birth → re-enrollment) |
| **Loans / advances** | Not a native EC module — done via MDF (Metadata Framework) custom object in most implementations; employee submits, manager approves, finance disbursed |
| **Expenses** | Native in Concur (SAP integration) — separate product, not ESS core |
| **Learning** | SAP Learning (formerly SAP SuccessFactors Learning) — employee can browse catalog, enroll, complete, view certificate; separate module |
| **Onboarding** | Dedicated module with checklist tasks assigned to new hire; e-sign contracts; upload documents; complete orientation modules |
| **Service requests** | Via Employee Central Service Center (ECSC) — open ticket, track status, message HR |

**Strengths:** Reference-data-driven (everything is a pick-list from a governed
catalog); effective-date everywhere; strong position-management model.

**Weaknesses:** Complexity that overwhelms SME implementations; mobile app (SAP
Fiori / Work Zone) is heavy; configurability requires ABAP/Fiori knowledge; high
TCO. Arabic RTL support is present but labelled as "qualified" (partial in
some sub-views).

---

### 1.2 Workday "Me" Hub

**Architecture:** Single SaaS tenant; "Me" is a configurable home dashboard fed by
Workday Business Process framework (BPF). All actions are business processes —
atomic, auditable, reversible.

**Modules and employee actions:**

| Module | Employee actions |
|--------|-----------------|
| **Personal data** | Edit preferred name, pronoun, address, phone; add/change bank account (triggers approval); add/remove emergency contacts; upload government ID photo |
| **Time off** | Request time off (with real-time balance projection before submit); cancel *any time before manager action*; view team calendar (company-wide or team-filtered); request time off on behalf (if delegated) |
| **Time tracking** | Clock in/out; enter time; submit correction; view weekly hours summary; manager-only approval queue |
| **Payroll** | View pay slip; download PDF; view gross-to-net breakdown; view deduction detail; view historical slips; see year-to-date tax totals |
| **Benefits** | Annual enrollment; life-event enrollment; view elections and plan costs; view beneficiary designations; add/change beneficiary |
| **Expenses** | Submit expense report; itemise; attach receipts (camera on mobile); track status through audit/approval; view reimbursement history |
| **Learning** | Browse catalog; enroll; launch content; complete; earn badge/certificate; manager-assigned learning shows in "action needed" |
| **Career** | Explore open positions; apply internally; view skills profile; receive recommended learning based on gap vs target role |
| **Onboarding tasks** | Checklist-driven; system assigns tasks by rule; employee completes, e-signs, uploads |
| **Help / cases** | Submit HR case; attach files; track resolution; message thread with HR |

**Standout patterns:**
- **Inbox / Action Needed:** All pending actions across ALL modules surface in one
  inbox with a due date + estimated time. This is the single most-cited productivity
  feature in Workday analyst reviews.
- **Business process audit trail:** Every state change is visible to the employee
  as a process history — who approved what and when.
- **Delegation:** Any business process can be delegated. Approvers can assign a
  substitute for a date range; the system routes automatically.
- **"I want to…" natural-language search:** Global search across all HR tasks.
- **Mobile parity:** Workday mobile is a native app, not a responsive web view;
  it has the same feature set as desktop with context-appropriate layouts.

---

### 1.3 Oracle HCM Cloud "Me" Page

**Architecture:** HCM Cloud (Fusion) with a "Me" landing page built from
configurable Quick Actions and a Journeys framework. "Journeys" are guided checklists
(onboarding, life events, career transitions) — Oracle's differentiator.

**Modules and employee actions:**

| Module | Employee actions |
|--------|-----------------|
| **Personal info** | Edit contact, address, emergency, dependent data; add national ID; submit bank account; change marital status (triggers re-enrollment) |
| **Absence** | Submit request; view balance; cancel; view team calendar; view approval chain before submitting |
| **Time & labour** | Enter hours; submit timesheet; request correction; view schedule |
| **Payroll** | View payslip; download PDF; view gross-to-net; update W-4 / tax card (region-specific) |
| **Benefits** | Enroll; life event; view coverage; view beneficiary; estimate cost |
| **Expenses** | Submit; itemise; capture receipts; track status |
| **Journeys** | Guided task sequences — Oracle's key differentiator. An HR admin configures a "Journey" (e.g., "Return from parental leave") as a list of tasks with owners (employee/IT/facilities/manager). Employee sees progress. |
| **Learning** | Oracle Learning: browse, enroll, complete, certificate, compliance tracking |
| **Career / skills** | Skills Center: employee-declared skills + AI-recommended skills + job suggestions |

**Standout patterns:**
- **Journeys** (guided multi-party workflows) are the most-cited feature. An
  "offboarding journey" automatically creates tasks for IT (revoke access), facilities
  (collect badge), payroll (final settlement) — all visible to the leaving employee.
- **Quick Actions grid:** A personalised grid of action buttons on the Me page — no
  nav required for common tasks.
- **HCM Communicate:** Push notification + read-receipt; HR can target a population
  segment and confirm delivery.

**Weakness:** Periodic (quarterly) update cycles mean UI consistency lags; journeys
require configuration expertise; Arabic RTL in Fusion HCM has known gaps in
specific sub-views (documented in Oracle Support).

---

### 1.4 ServiceNow HR Service Delivery (HRSD)

**Architecture:** Sits on the Now Platform, primarily a **case + knowledge management**
layer over whatever HRIS exists (or stand-alone). Does not manage payroll or core HR
records natively — it orchestrates HR services and cases.

**Modules and employee actions:**

| Module | Employee actions |
|--------|-----------------|
| **Employee Center (portal)** | Browse HR topics; search KB articles; submit service requests; track case status |
| **Life event flows** | Employee triggers a structured flow (e.g., "I got married") → system presents list of sub-tasks (update beneficiary, update tax status, upload marriage certificate) |
| **Document requests** | Request employment letter, experience letter, payslip copy; delivered digitally or via print queue |
| **Onboarding** | Task assignment to employee + onboarding buddy + IT + facilities; progress tracking |
| **Offboarding** | Checklist across departments; countdown to last day; equipment return tasks |
| **Leave of absence** | Submit request form; upload documentation; track approval; not a calendar-management tool |

**Standout pattern:** **Cross-department orchestration** — HRSD's case-routing
engine links HR actions to IT, Facilities, and Finance service desks. An employee
submits one request and HRSD spawns sub-tasks to each department automatically.

**Weakness:** HRSD is a wrapper, not an HRIS. Leave balances, payslips, org charts
are always from a connected system (SuccessFactors, Workday, ADP). Without that
integration, HRSD is just a ticketing system. Not appropriate as a standalone ESS.

---

### 1.5 BambooHR

**Architecture:** SaaS HRIS targeting SMB (10–500 employees). Single unified product;
no separate ESS "portal" — the same interface is used by HR, managers, and employees
with role-filtered views.

**Modules and employee actions:**

| Module | Employee actions |
|--------|-----------------|
| **Profile** | Edit contact info, emergency contact, address; update photo; complete org-set custom fields |
| **Time off** | Request (type, dates, note); view own balance; view team's out-of-office (calendar); cancel pending request; receive push notification when approved/rejected |
| **Time tracking** | Clock in/out (web, mobile, kiosk); submit hours; timesheets go to manager approval |
| **Documents** | View company documents shared to employee; upload personal document (e.g., certifications); e-sign documents |
| **Benefits** | View enrolled benefits (integration with Guideline/others); limited self-enrollment via benefits package |
| **Tasks** | Onboarding/offboarding checklist; employee sees assigned tasks; marks complete |
| **Employee directory** | Searchable; org chart view; "who reports to whom" |
| **Payroll** | BambooHR Payroll (US-only add-on): view payslip, download; employees can update bank info |
| **Performance** | Self-assessment; 360 peer review; goal setting; manager 1-on-1 notes visible to both parties |

**Standout patterns:**
- **Simplicity as the core design principle.** Everything surfaces in 3 clicks.
- **Mobile app** is nearly full-featured: time off, clock in/out, directory, documents.
- **Notification design:** every status change on a leave request or document
  generates both in-app and email notification. Configurable per-user.
- **Team calendar widget:** visible on the employee home screen showing who is off
  this week. Cited as one of the most-used features in NPS surveys.

**Weakness:** Not designed for non-US payroll, Arabic, or large complex org charts;
RBAC is coarse (HR / Manager / Employee); no effective-date model for compensation.

---

### 1.6 Personio (European SME)

**Architecture:** SaaS HRIS targeting European SME (10–2000 employees). Strong on
GDPR, multi-country compliance (DE, FR, ES, IT, AT, GB, CH). One product with
configurable modules.

**Modules and employee actions:**

| Module | Employee actions |
|--------|-----------------|
| **Profile** | Edit personal data (GDPR-consent-gated fields); emergency contact; bank IBAN; upload documents |
| **Attendance** | Clock in/out (web, mobile, kiosk); submit manual entry; request attendance correction; view monthly attendance report |
| **Time off** | Request (type, dates, note, half-day); view real-time balance before submit; cancel pending; view team calendar; see approval chain status |
| **Payslips** | View; download PDF; historical list |
| **Documents** | View e-signed contracts; upload personal docs; HR shares documents to employee |
| **Expenses** | Submit expense report; attach receipts; track approval; view reimbursement |
| **Onboarding tasks** | Checklist of tasks; employee marks complete; buddy can also see checklist |
| **Performance** | Self-review form; goal setting; review history |
| **Surveys** | Complete HR-initiated engagement surveys |

**Standout patterns:**
- **Approval chain visibility BEFORE submission:** employee can see who will
  approve their leave before they hit "submit." This dramatically reduces surprised
  rejections.
- **GDPR consent model:** fields that require consent to collect display a
  consent dialog; data subject access requests downloadable by employee.
- **Multi-language / multi-country:** strong i18n; Arabic is NOT in Personio's
  current roadmap (MENA market not targeted), but the i18n architecture is good.
- **"What do you need?" help center:** contextual KB embedded inside the product.

---

## 2. COMMON ESS MODULE TAXONOMY

### 2.1 Universal modules (every enterprise ESS must have these)

The following exist across all six systems with near-identical semantics:

| Module | Minimum viable actions | Notes |
|--------|----------------------|-------|
| **Leave / Absence** | Request, cancel (pre-approval), view balance, view team calendar, approval chain visibility | Balance must be visible BEFORE submit |
| **Personal profile** | Edit address, phone, emergency contact, bank account, upload ID/passport scan | Bank account triggers approval everywhere |
| **Payslip / compensation view** | View current payslip, download PDF, view history (last 12+ months) | PDF non-negotiable for regulatory/audit |
| **Notifications** | In-app + email on every request state change | On/off per user per type |
| **Onboarding checklist** | View assigned tasks, mark complete, upload required docs | First-run UX; not for long-term use |
| **Document access** | View HR-shared documents (contracts, policies); upload personal docs | Version control on company docs |

### 2.2 High-value modules (in most, but not all, systems)

| Module | Actions | Differentiator |
|--------|---------|----------------|
| **Attendance / timesheet** | Clock in/out, submit timesheet, correction request | Only if org uses clocking; skip for pure office-hours policy |
| **Expenses** | Submit, attach receipts, track, view reimbursement | High ROI for field workers; not relevant for office-only |
| **Benefits** | View enrolled, open-enrollment, life-event change | Needed if org has benefit plans |
| **Service requests / HR cases** | Submit free-form request to HR, track, message thread | Replaces HR email inbox; scales well |
| **Performance** | Self-assessment, goal setting, view feedback received | Engagement driver; adds implementation complexity |

### 2.3 Specialised modules (present in enterprise, optional for SME)

| Module | When to include |
|--------|-----------------|
| **Loans / advances** | Middle-East / South-Asia labour markets; expected in Gulf SaaS |
| **Internal career** | Only if org has open positions + internal transfer policy |
| **Learning / certifications** | If org runs L&D programs or compliance training |
| **Journeys / guided flows** | Multi-step life events (maternity, relocation, exit) |
| **Equipment requests** | IT-integrated; only if IT service desk is in scope |
| **Team management** | Visible only to managers; not ESS proper |

### 2.4 Leave module — detailed spec

This is the most-used ESS module. Get it right:

**Pre-submit:**
- Employee picks leave type → system immediately shows **current balance** + projected
  balance after this request.
- System shows team-calendar overlay: who else is off on those dates?
- If balance insufficient: block submit OR allow negative with flag (configurable).
- Show approval chain: "this request will go to → Ahmed Khalil (direct manager) →
  Hana Noor (department head if > 3 days)." Personio and Oracle both do this.

**Submit state machine:**
```
DRAFT → SUBMITTED → APPROVED
                 ↘ REJECTED → (employee can resubmit or abandon)
       ↓
    CANCELLED (employee cancels before manager acts)
APPROVED → CANCELLED_APPROVED (manager or HR retracts; triggers balance reversal)
```

**Post-submit:**
- Employee can cancel while status = SUBMITTED (configurable window: e.g., up to 2
  days before leave starts).
- Employee cannot edit a submitted request — must cancel + resubmit.
- Every transition generates notification (in-app + email) to employee AND manager.

**Calendar requirements:**
- Team view: who is off each day (colour-coded by type: annual / sick / emergency).
- Employee view: own leave history on calendar + approved future leaves.
- Public holidays overlay (country-specific; should be a governed reference set).

---

## 3. APPROVAL WORKFLOW PATTERNS

### 3.1 Workflow topology options

| Pattern | When used | Systems that implement it |
|---------|-----------|--------------------------|
| **Single manager** | Default; employee → direct manager | All 6 |
| **Multi-level** | Long leave, high-value expense → manager → department head → HR | SAP, Workday, Oracle |
| **Skip-level** | If manager is the employee's leave substitute | Workday (auto-routing), Oracle |
| **Parallel** | Large expense: manager + finance simultaneously | Oracle, ServiceNow |
| **Delegated substitution** | Manager sets OOO → assigns substitute approver for date range | Workday (full), SAP (configurable), Personio (manual) |
| **HR override** | HR can approve/reject any request regardless of routing | All 6 |
| **Auto-approve** | Configured for specific leave types (e.g., sick ≤ 1 day) | SAP, Oracle |

### 3.2 Delegation / out-of-office substitution

Critical and universally under-engineered in SME systems:

- **Manager sets delegation:** "I'm OOO 1–10 Oct; route my approvals to Karim."
- **System must validate** that the delegate has the organisational authority to
  approve (they must be a manager or HR; not a peer).
- **Employee-facing:** show "Pending approval by: Ahmed Khalil (Karim Mansour
  acting)" — transparency prevents confusion.
- **Expiry:** delegation expires automatically on the end date; no manual cleanup.

### 3.3 What employees can do after submission

| Action | Pre-approval | Post-approval | Post-rejection |
|--------|-------------|---------------|----------------|
| View status | ✅ | ✅ | ✅ |
| Add comment to request | ✅ configurable | ❌ (done) | ✅ (when appealing) |
| Cancel request | ✅ (full cancel) | ✅ with config (APPROVED→CANCELLED_APPROVED) | N/A |
| Edit request | ❌ (cancel + resubmit) | ❌ | ✅ (resubmit with changes) |
| View full approval history | ✅ | ✅ | ✅ |
| Download confirmation | ❌ (pending) | ✅ PDF/email auto-sent | ❌ |

### 3.4 Recommended state machine (Django)

```python
class LeaveRequest(models.Model):
    class Status(models.TextChoices):
        DRAFT         = "draft",          "Draft"
        SUBMITTED     = "submitted",      "Submitted"
        APPROVED      = "approved",       "Approved"
        REJECTED      = "rejected",       "Rejected"
        CANCELLED     = "cancelled",      "Cancelled"
        REVOKED       = "revoked",        "Revoked (post-approval)"

    # Allowed transitions (enforced at serializer/service level, not just view):
    TRANSITIONS = {
        "draft":      ["submitted", "cancelled"],
        "submitted":  ["approved", "rejected", "cancelled"],
        "approved":   ["revoked"],
        "rejected":   ["submitted"],  # allow resubmit
        "cancelled":  [],
        "revoked":    [],
    }
```

Enforce at the service layer; the API must return HTTP 409 on invalid transitions,
not silently ignore them.

---

## 4. CRITICAL UX PATTERNS

### 4.1 Employee home dashboard

**What the best systems put on the home screen (ordered by frequency of use):**

1. **"Action needed" card** — pending tasks with count + due date. The single highest-
   value widget. Workday's Inbox is the benchmark: every module pushes pending
   items here. Includes: pending approvals (for managers), documents to sign,
   onboarding tasks, open performance reviews, benefits enrollment deadline.

2. **Leave balance widget** — current balances for each leave type (annual, sick,
   emergency). At-a-glance; click expands to request form. BambooHR does this well.

3. **Team calendar strip** — next 7 days; shows who on your team is off. Colour-coded
   dots under each date. Click → full calendar. Cited as #1 most-missed feature when
   absent.

4. **Recent requests** — last 3–5 leave/expense/service requests with current status
   and traffic-light colour. Eliminates "did it go through?" anxiety.

5. **Quick actions** — 4–8 buttons for most-common tasks. Oracle Me page and
   ServiceNow Employee Center use this. Personalise by role/org.

6. **Announcements / news** — low priority; don't let it push the above off screen.

7. **My information summary** — name, employee ID, department, manager, join date.
   Link to full profile. Useful reference, not an action item.

**Anti-pattern:** SAP SuccessFactors' old My Info tab put profile data above actions.
Users ignored it. Workday's Inbox-first layout is the correct inversion.

### 4.2 Mobile vs desktop

| Concern | Best practice | Anti-pattern |
|---------|--------------|--------------|
| Clock in/out | Mobile-first, one-tap, GPS capture optional | Desktop-only (forces office visit) |
| Leave request | Full form on mobile; date pickers must be native mobile | Tiny inputs, no native date picker |
| Payslip | PDF viewer or native render; download to device | "Desktop only" payslip |
| Notifications | Push (native app) or browser push | Email-only |
| Team calendar | Scrollable horizontal strip on mobile; full calendar on desktop | Calendar cut off on small screen |
| Document upload | Camera capture on mobile | File picker only (requires desktop) |
| Approval action | Single-tap approve/reject from notification | Requires login to portal |

**Architecture recommendation:** Build the React frontend with MUI's responsive
system from the start. Do NOT add mobile as a second phase. Target 375px minimum
viewport. Key interactions must be completable in under 5 taps on mobile.

### 4.3 Notification design

**What Workday and BambooHR get right:**

- **Notification taxonomy:** request_submitted (to manager), request_approved/rejected
  (to employee), request_cancelled (to manager), deadline_approaching (to employee),
  action_overdue (to manager + HR). These are distinct, configurable per type.

- **Delivery channels:** In-app notification (bell icon with badge count) + email.
  SMS is optional, rarely used. Push notification if mobile app exists.

- **Email design:** Subject must contain the outcome: "Your Annual Leave (15–19 Oct)
  has been APPROVED." Body includes who approved, when, any comments, and a
  deep-link back to the request. Never "You have a notification — log in to see it."

- **In-app notification:** Shows in the bell menu with icon indicating module
  (leave = calendar icon), short description, timestamp, and link to the entity.
  Unread count shown on the bell. Mark-all-read must exist.

- **Notification preferences:** Employee can opt out of email for any notification
  type. Manager can escalate. HR cannot opt out of critical alerts.

- **Anti-pattern:** Notifications that only say "Your request has been updated" with
  no status, no detail. Forces login just to find out it was rejected.

### 4.4 RTL / Arabic i18n

This is non-negotiable for the MENA market. Observations from system analysis:

**What must be RTL-aware:**
- Layout direction: sidebar on right, content flows right-to-left
- Icon placement: "back" chevron flips; "expand" chevron does NOT flip (↕ is neutral)
- Number formatting: Arabic-Indic numerals vs Western Arabic digits (configurable)
- Date format: Hijri calendar support alongside Gregorian (needed for Gulf orgs)
- Text alignment in tables: mixed LTR/RTL cells (employee name RTL, employee ID LTR)
- Form labels: right-aligned labels, RTL input direction
- PDF generation: must produce RTL-correct PDFs (use a PDF engine that supports BiDi)

**MUI RTL configuration:**
```jsx
// theme/carbonTheme.js — add direction
const theme = createTheme({
  direction: 'rtl',   // or 'ltr' from i18n context
  // ... rest of theme
});
// Wrap with CacheProvider using rtlPlugin (stylis-plugin-rtl)
```

**i18n string handling:**
- All strings in translation files (react-i18next); never hardcoded in JSX
- String bundles: en, ar minimum; fr as nice-to-have for North Africa
- Date/time via `Intl.DateTimeFormat` with locale; avoid moment.js
- Currency: use `Intl.NumberFormat` with `currency` option; EGP, AED, SAR, KWD minimum

**Status indicator pattern (RTL-safe):**
- Use colour chips + text labels, NOT "left-border colour" strips (those flip wrong in RTL)
- Icons should be semantic (check, x, clock) not directional (arrow left/right)

### 4.5 Accessibility

- **Standard:** WCAG 2.1 AA minimum; 2.2 AA for new components.
- **Focus management:** Dialog open → focus on first interactive element; dialog
  close → focus returns to trigger. MUI does this; don't override it.
- **Colour contrast:** MUI v7 compact density uses small text; verify 4.5:1 contrast
  for body text at 12px. Zinc palette must be checked in both LTR and RTL modes.
- **Keyboard navigation:** Tab order follows visual order in both LTR and RTL.
  Leave calendar must be keyboard-navigable.
- **Screen readers:** All form fields have labels (not just placeholder). Status chips
  must have aria-label. "Approved" green chip alone fails; pair with an icon + text.
- **Reduced motion:** Respect `prefers-reduced-motion`; don't animate status
  transitions in accessibility mode.

### 4.6 "Action Needed" / pending items surface

This is the single highest-ROI UX pattern. Workday's Inbox is the reference.

**Architecture:**
- Backend: a `PendingAction` model (or view) that aggregates across modules:
  ```python
  # A unified inbox query across all modules
  # pending_leave_approvals(manager) → list of LeaveRequest
  # pending_onboarding_tasks(employee) → list of OnboardingTask
  # pending_document_signatures(employee) → list of DocumentTask
  # deadline_alerts(employee) → benefits enrollment deadline, etc.
  ```
- API: `/carbon-api/me/inbox/` returns a unified list with entity_type, entity_id,
  action_label, due_date, urgency.
- Frontend: `<InboxWidget>` on home; `<InboxPage>` at `/me/inbox`; bell badge count.
- Critical: inbox count must be fast (sub-100ms); do NOT compute it in the page
  render critical path; cache with Redis (invalidate on state change).

---

## 5. COMMON ESS ANTI-PATTERNS (to avoid)

These are confirmed flaws observed across multiple systems, ranked by user impact:

| # | Anti-pattern | Impact | Root cause | Fix |
|---|-------------|--------|-----------|-----|
| AP-1 | **Leave balance not shown before submitting** | High — employee submits knowing they'll be rejected; creates noise | Balance stored separately from request form | Show balance in the request form, update dynamically as dates change |
| AP-2 | **No team calendar** | High — employee can't self-check conflicts; manager rejects preventably | Considered "manager feature" | Show team calendar to all employees (read-only); it removes approx. 30% of conflict rejections |
| AP-3 | **Can't cancel a submitted request** | High — requires emailing HR; manual reversal | FSM has no cancel transition | Add SUBMITTED→CANCELLED transition with cancellation reason; reverse balance immediately |
| AP-4 | **No notification on status change** | High — employee doesn't know if approved; checks repeatedly | Notification as afterthought | Emit notification event on every FSM transition; deliver in-app + email |
| AP-5 | **Payslip not downloadable as PDF** | High for compliance — employee needs for visa, bank, rental applications | HTML-only render | Generate PDF server-side (WeasyPrint / ReportLab); store as media file |
| AP-6 | **Approval flow hardcoded** | Medium — can't handle org changes without code change | Workflow rules in code | Store workflow as data (approval_rule FK on leave type); configurable per leave type + amount |
| AP-7 | **No audit trail visible to employee** | Medium — employee can't see who did what | Audit table HR-only | Show condensed approval history (who, action, timestamp, comment) on the request detail |
| AP-8 | **Emergency contact / bank details buried** | Medium — employee gives up updating, HR has stale data | Profile split across 5 tabs | Profile completeness indicator on home page; direct link to each incomplete section |
| AP-9 | **Mobile UX is afterthought** | Medium-high for field/remote workers | Desktop designed first | Responsive from day 1; test on 375px during development of every component |
| AP-10 | **No submission confirmation** | Medium — employee unsure if request was saved | API error swallowed by frontend | Show success toast with request ID + "you'll be notified when reviewed" |
| AP-11 | **Multiple clicks to reach any action** | Medium — discourages use | Module-per-page navigation | Quick actions on home page; "action needed" surface; global search |
| AP-12 | **No out-of-office delegation** | Medium — requests pile up when manager is travelling | Delegation not designed | Implement delegation: manager sets substitute + date range; routing is automatic |
| AP-13 | **RTL is cosmetic, not structural** | High for Arabic — inputs still LTR | i18n bolted on | Set MUI direction from locale context; use `dir="auto"` on mixed-content inputs |
| AP-14 | **Expense receipt upload requires desktop** | Medium — field workers can't submit | File input, no camera | Use `<input type="file" accept="image/*" capture="environment">` for mobile camera |
| AP-15 | **Approval email has no content** | Low-medium — approver opens app anyway | Generic email template | Email body: employee name, request type, dates, current balance, approve/reject links |

---

## 6. DATA MODEL PATTERNS

### 6.1 Core entity map

```
LegalEntity (tenant root)
  └── OrgUnit (tree; hangs off LegalEntity)
        └── Position (effective-dated role in org)
              └── Employee (person in a Position; effective-dated assignment)
```

```
Employee
  ├── PersonalInfo (effective-dated: address, phone, emergency contacts)
  ├── BankAccount (effective-dated; approval-gated; verified)
  ├── IdentityDocument (passport, national ID; with expiry; evidence attachment)
  ├── CompensationLedger (EmployeeCompensation rows; effective-dated; additive only)
  ├── LeaveEntitlement (per leave type; carries balance; accrual rules)
  ├── LeaveRequest (FSM; links to entitlement)
  ├── AttendanceRecord (daily; clock in/out; status)
  ├── Payslip (materialised from CompensationLedger + ComplianceRule calculations)
  ├── Loan (request + repayment schedule; approval-gated)
  ├── BenefitEnrollment (per BenefitPlan; effective-dated)
  ├── ExpenseReport (header + lines + receipts)
  ├── Certification / Credential (with expiry; verification status)
  └── PersonnelEvent (append-only chronicle of all HR events)
```

### 6.2 Key relationship decisions

**Leave entitlement vs leave record:**
```python
class LeaveEntitlement(models.Model):
    employee = FK(Employee)
    leave_type = FK(ReferenceValue, limit_choices_to={"reference_set__slug": "leave_type"})
    balance_days = DecimalField()            # current balance (accrued - taken)
    accrual_rate = DecimalField()            # days per month
    accrual_frequency = FK(ReferenceValue)   # monthly / annual
    effective_from = DateField()
    carry_over_max = DecimalField(null=True) # max days to carry to next year

class LeaveRequest(models.Model):
    employee = FK(Employee)
    entitlement = FK(LeaveEntitlement)       # ties to the specific entitlement
    leave_type = FK(ReferenceValue)          # denormalised for query speed
    start_date, end_date = DateField()
    duration_days = DecimalField()           # computed; stored for report speed
    status = CharField(choices=Status)       # FSM
    submitted_at, approved_at = DateTimeField(null=True)
    approved_by = FK(User, null=True)
    cancellation_reason = TextField(blank=True)
```

**Approval workflow as data (not code):**
```python
class ApprovalRule(models.Model):
    """Configurable approval chain per leave type + duration + org level."""
    leave_type = FK(ReferenceValue, null=True)   # null = all types
    max_duration_days = DecimalField(null=True)  # null = no limit
    org_unit = FK(OrgUnit, null=True)            # null = global
    steps = JSONField()
    # steps format:
    # [
    #   {"level": 1, "approver_role": "direct_manager"},
    #   {"level": 2, "approver_role": "department_head", "min_duration": 3},
    #   {"level": 3, "approver_role": "hr_admin", "min_duration": 10}
    # ]

class ApprovalStep(models.Model):
    """Instance of an approval rule step for a specific request."""
    request_content_type = FK(ContentType)  # generic FK; works for Leave, Expense, Loan
    request_object_id = PositiveIntegerField()
    level = PositiveSmallIntegerField()
    assigned_to = FK(User)
    status = CharField(choices=["pending","approved","rejected","delegated"])
    acted_at = DateTimeField(null=True)
    comment = TextField(blank=True)
    delegated_to = FK(User, null=True)
```

**Payslip:**
```python
class Payslip(models.Model):
    employee = FK(Employee)
    payroll_run = FK(PayrollRun)
    period_start, period_end = DateField()
    status = FK(ReferenceValue, "payroll_status")  # draft / published / voided
    gross = DecimalField()
    total_deductions = DecimalField()
    net = DecimalField()
    currency = FK(ReferenceValue, "currency")
    pdf_file = FileField(null=True)       # generated server-side; stored in media
    published_at = DateTimeField(null=True)

class PayslipLine(models.Model):
    payslip = FK(Payslip)
    component = FK(CompensationComponent)  # governed; direction = earning|deduction
    amount = DecimalField()
    rule_version = CharField()             # ComplianceRule version that produced it
    inputs = JSONField()                   # snapshot of inputs for audit
```

**Generic notification:**
```python
class Notification(models.Model):
    recipient = FK(User)
    notification_type = FK(ReferenceValue, "notification_type")
    entity_type = FK(ContentType)   # generic FK to any entity
    entity_id = PositiveIntegerField()
    title = CharField()
    body = TextField()
    is_read = BooleanField(default=False)
    created_at = DateTimeField(auto_now_add=True)
    email_sent_at = DateTimeField(null=True)
    # Index on (recipient, is_read, created_at) for bell count query
```

### 6.3 Effective-date pattern (reuse from Law 2 above)

Every entity that represents a fact that can change over time must follow:

```python
class EffectiveDateMixin(models.Model):
    effective_from = DateField()
    effective_to = DateField(null=True, blank=True)  # null = open-ended / current

    class Meta:
        abstract = True

    @classmethod
    def current(cls, **kwargs):
        today = date.today()
        return cls.objects.filter(
            effective_from__lte=today,
            **{k: v for k, v in kwargs.items()}
        ).filter(
            models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=today)
        )
```

This mixin applies to: PersonalInfo, BankAccount, EmployeeCompensation,
LeaveEntitlement, BenefitEnrollment, PositionAssignment. Once applied consistently,
"current value" is always a query, never a stored scalar — this is Law 2 from the
NIBRAS data model document.

---

## 7. PERMISSION MODEL

### 7.1 Three-tier actor model

| Actor | Can see | Can do | Cannot do |
|-------|---------|--------|-----------|
| **Employee** | Own data only: profile, own leave requests + history, own payslips, own loans, own certifications | Submit leave, cancel own pending requests, update own personal info (bank = approval-gated), upload own documents, submit expenses, complete own onboarding tasks | See other employees' pay, see team aggregate except calendar, approve anything, see audit log of others |
| **Manager** | Own data (as employee) + their direct reports: leave requests, attendance, basic profile | Approve/reject leave, expense, attendance corrections for their reports; view team calendar; add comments to requests; delegate approval | See reports' payslips/compensation (unless granted people:view_compensation); bypass approval for requests requiring a higher level |
| **HR Admin** | All employees within their LegalEntity / scoped OrgUnit | Full CRUD on all HR records; approve/reject any request; override approval workflow; generate/publish payslips; configure leave types and entitlements; view full audit trail | Cross-tenant data (unless global admin); system config outside HR domain |
| **Payroll Operator** | Compensation and payslip data for their scope | Generate payslip run; publish/void payslips; view compensation ledger | Change org structure; manage leave types |
| **Global Admin** | All LegalEntities | System configuration; LegalEntity CRUD | Cannot bypass compliance rules that are jurisdiction-locked |

### 7.2 "See only your own data" — enforcement

**The rules as implemented in Django:**

```python
# Every queryset on ESS resources must be filtered at the view level:

class LeaveRequestViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        user = self.request.user
        if user.has_perm("people.view_all_leave"):
            # HR Admin: scoped to their legal entity's employees
            return LeaveRequest.objects.filter(
                employee__org_unit__in=get_allowed_org_unit_ids(user)
            )
        if user.has_perm("people.manage_team_leave"):
            # Manager: only direct reports
            return LeaveRequest.objects.filter(
                employee__manager=user.employee
            )
        # Employee: own only
        return LeaveRequest.objects.filter(employee=user.employee)
```

**Key enforcement points:**
- Never use `LeaveRequest.objects.all()` in any view; every view-level queryset
  scopes to the user's authority.
- Object-level permission check in `get_object()` (DRF default; don't disable it).
- Serializer must not expose fields the user cannot see (use separate serializers
  for employee-view vs manager-view vs HR-view of the same entity).
- Payslip and compensation endpoints require `people:view_compensation` capability
  (existing pattern in the platform — see SCREEN-SPEC-COMPENSATION-LEDGER.md).
- Bank account write endpoint requires `people:manage_bank` capability + triggers
  an `ApprovalStep` before the data is applied.

### 7.3 Capability mapping to CBAC

The Carbon platform uses capability-based access control (CBAC) via ScopedRole.
ESS-specific capabilities to register:

```python
ESS_CAPABILITIES = [
    # Self-service (any authenticated employee)
    "people:view_own_profile",
    "people:edit_own_contact",
    "people:edit_own_bank",         # + triggers approval
    "people:view_own_leave",
    "people:submit_leave",
    "people:view_own_payslips",
    "people:view_own_loans",
    "people:submit_expense",
    "people:view_own_tasks",

    # Team management (managers)
    "people:view_team_leave",
    "people:approve_leave",
    "people:view_team_attendance",
    "people:approve_timesheet",
    "people:approve_expense",

    # HR administration
    "people:view_all_leave",
    "people:manage_leave_entitlements",
    "people:view_compensation",
    "people:manage_compensation",
    "people:view_all_payslips",
    "people:generate_payslip",
    "people:manage_bank",            # approve bank change
    "people:view_audit_log",
    "people:configure_approval_rules",
]
```

### 7.4 Audit trail visibility

- **Employee sees:** their own request history with approval steps (who, action,
  timestamp, comment). Readable, condensed; not a raw change log.
- **Manager sees:** approval history for all requests they acted on.
- **HR sees:** full `PersonnelEvent` chronicle for employees in their scope.
- **Audit log (WORM):** never exposed to any employee self-service endpoint directly.
  Only HR admin and global admin can view raw audit log. This is a security boundary.

---

## 8. SYNTHESIS: RECOMMENDATIONS FOR CARBON/NIBRAS

### 8.1 What to build (phased)

**Phase 1 — Core ESS (highest ROI, lowest risk):**
1. Employee home dashboard (action needed, leave balance, team calendar, quick actions)
2. Leave request + approval workflow (full FSM, configurable rules, team calendar)
3. Payslip view + PDF download (server-side PDF via WeasyPrint)
4. Personal profile edit (address, phone, emergency contact, bank w/ approval)
5. Notification system (in-app bell + email; unified Notification model)
6. Onboarding checklist (assigned tasks, mark complete, upload docs)

**Phase 2 — Extended ESS:**
7. Attendance / clock in-out + timesheet + correction requests
8. Expense reports (submit, attach receipts/camera, track)
9. HR service requests (submit ticket, track, message thread)
10. Loans / salary advances (request, repayment schedule view)

**Phase 3 — Advanced:**
11. Benefits enrollment + life-event workflow
12. Learning catalog + progress tracking
13. Performance self-assessment + goals
14. Guided journeys (onboarding, life events, exit)
15. Out-of-office delegation management

### 8.2 Django app structure

The existing `backend/people/` app is the right home. Key additions:

```
backend/people/
  models/
    leave.py          # LeaveEntitlement, LeaveRequest, LeaveApprovalStep
    payslip.py        # Payslip, PayslipLine (already exists; extend)
    profile.py        # PersonalInfo, BankAccount, IdentityDocument (effective-dated)
    attendance.py     # AttendanceRecord, AttendanceCorrection
    expense.py        # ExpenseReport, ExpenseLine
    loan.py           # Loan, LoanInstallment
    notification.py   # Notification (generic)
    approval.py       # ApprovalRule, ApprovalStep (generic; ContentType FK)
    onboarding.py     # OnboardingPlan, OnboardingTask, EmployeeTask
  services/
    leave_service.py     # FSM transitions, balance updates, notification dispatch
    approval_service.py  # route approval based on ApprovalRule
    notification_service.py  # send in-app + email
    pdf_service.py       # generate payslip PDF (WeasyPrint)
  api/
    views/
      me.py            # /me/inbox, /me/dashboard, /me/profile
      leave.py         # /me/leave/, /me/leave/<id>/cancel/
      payslips.py      # /me/payslips/, /me/payslips/<id>/pdf/
      approvals.py     # /approvals/pending/, /approvals/<id>/act/
```

### 8.3 React component structure

```
carbon-frontend/src/apps/people/
  pages/
    EmployeeHome.jsx        # dashboard (InboxWidget, LeaveBalanceWidget, TeamCalendar)
    LeaveRequestPage.jsx    # form + balance preview + team calendar overlay
    LeaveHistoryPage.jsx    # own leave history + status
    PayslipsPage.jsx        # list of payslips + PDF download
    ProfilePage.jsx         # personal info tabs
    OnboardingPage.jsx      # checklist (first-login)
  components/
    InboxWidget.jsx         # action needed cards
    LeaveBalanceCard.jsx    # balance + quick request button
    TeamCalendar.jsx        # 7-day strip + full calendar
    LeaveRequestForm.jsx    # dates → dynamic balance update → submit
    ApprovalHistory.jsx     # condensed FSM history: who, action, when, comment
    NotificationBell.jsx    # badge count + dropdown + mark-read
    StatusChip.jsx          # RTL-safe: icon + text + colour
```

### 8.4 Arabic RTL implementation checklist

- [ ] `dir` attribute on `<html>` set from i18n locale (not hardcoded)
- [ ] MUI theme `direction` and `CacheProvider` with `rtlPlugin` configured
- [ ] All string literals extracted to `en.json` / `ar.json`
- [ ] Date display uses `Intl.DateTimeFormat('ar-EG')` or `('ar-SA')` per config
- [ ] Calendar component tested at 375px in RTL mode
- [ ] Payslip PDF generated with Arabic text rendering (WeasyPrint + arabic-reshaper
  + python-bidi on the backend)
- [ ] Status chips use semantic icons, not directional arrows
- [ ] Form label alignment correct in RTL (right-aligned, right-to-left reading)
- [ ] Approval history timeline renders correctly in RTL
- [ ] Notification email template tested in RTL (Gmail, Outlook both render RTL
  from `<html dir="rtl">`)

### 8.5 Non-negotiables (from anti-pattern analysis)

1. **Leave balance MUST show before submit.** No exceptions. Computed from
   `LeaveEntitlement.balance_days` minus pending approved requests for the period.
2. **Every request state change MUST emit a notification.** Use Django signals or
   a service-layer call; never rely on the view to remember.
3. **Payslip MUST be downloadable as PDF.** WeasyPrint generates RTL-correct PDFs.
4. **FSM transitions MUST be enforced server-side.** Never trust client state.
5. **All ESS querysets MUST be scoped to the user's authority.** No `.objects.all()`
   in any ESS view.
6. **Approval workflow MUST be data-driven.** `ApprovalRule` configures it; no
   workflow logic hardcoded in views.
7. **Team calendar is employee-visible.** Not a manager-only feature.
8. **Employee can cancel a SUBMITTED request.** Before any approval action is taken.
9. **Approval history visible to the employee.** Not hidden behind HR access.
10. **Mobile-responsive from day 1.** Test at 375px in RTL mode during development.

---

*End of brief. Next step: author TASKS.md phases for Phase 1 (Core ESS) starting
with the leave module + notification system, referencing this brief + DESIGN-NIBRAS-ENTERPRISE-HR-DATA-MODEL.md as inputs.*
