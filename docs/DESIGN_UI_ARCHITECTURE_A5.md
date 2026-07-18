# A5 Design Decision — UI Architecture: One Unified App, Role-Adaptive Perspectives

> **Type:** Architecture Decision Record (ADR)
> **Status:** DECIDED — Approved direction for RUN A5 implementation
> **Inspired by:** Ataccama ONE perspective model, adapted lightweight
> **Pairs with:** DESIGN_ORG_ACCESS_MODEL.md §5, STRATEGY_DATA_TRUST_PLATFORM.md §2

---

## 1. The Question

**One unified UI — or User Mode vs Admin Mode as separate experiences?**

This was triggered by asking: *"get inspired from Ataccama ONE — should we have one unified UI or user mode and admin mode?"*

---

## 2. Ataccama ONE Reference Analysis

Ataccama ONE is the benchmark. It does NOT split into two applications. Instead it uses **one unified app with role-adaptive "perspectives"**:

| Ataccama Perspective | Who Sees It | What It Exposes |
|---|---|---|
| **Catalog** | All authenticated users | Browse data assets, view quality status, descriptions, tags |
| **Data Quality** | Data stewards, DQ engineers | Rules, profiling, DQ jobs, scores |
| **Governance** | Governance officers, stewards | Policies, ownership, lineage, glossary |
| **MDM** | Master data stewards | Golden records, matching, survivorship |
| **Operations / Platform** | Admins only | User management, connection setup, platform config |

**Key insight:** The perspective switcher in the top nav lets a user with multiple roles fluidly move between views. A data steward who is ALSO a governance officer sees BOTH perspectives. A data consumer only sees Catalog.

**What Ataccama does NOT do:**
- Separate login portal for admins
- Separate URL/deployment for admin vs user
- Force users to log out and log back in with a different context

---

## 3. Decision

### ✅ ONE unified React app — with **Role-Adaptive Perspective Switching**

**Not:** Two separate apps.
**Not:** A hidden `/admin` sub-app with a different login.
**Yes:** One app, one URL, one auth. Different roles reveal different **sections/perspectives** in the sidebar and header.

This is explicitly confirmed in our own design doc:
> *"One role-adaptive portal — NOT a separate admin console. Admin/steward capabilities are role-gated sections of the same app."* — DESIGN_ORG_ACCESS_MODEL.md §5

---

## 4. The Three Perspectives (Carbon's Ataccama-inspired model)

### Perspective 1: **Data Entry** (Operator View)
**Shown to:** Any authenticated user with a `dataowners_group` or `auditors_group` role

| Section | What the user sees |
|---|---|
| **My Dashboard** | Scoped emissions summary for their org unit — their branch, dept, campus only |
| **My Data** | Sidebar tree of Scope 1/2/3 → their assigned modules → their tables → data entry grid |
| **Help / Feedback** | Platform-wide |

UX behavior:
- Sidebar is **lean** — only what they own, nothing else
- Dashboard numbers are **automatically org-scoped** (no data leakage)
- No schema management visible
- No user management visible
- They cannot navigate to another user's data (server enforces this too)

---

### Perspective 2: **Administration** (Steward / Admin View)
**Shown to:** Users with `admins_group` role (global OR org-scoped)

| Section | Global Admin sees | Org-scoped Steward sees |
|---|---|---|
| **Org Structure** | Full AASTMT tree editor | Read-only tree + their subtree management |
| **Schema Manager** | All DataTables / DataFields across all orgs | Their org's tables only |
| **Access Control** | All ScopedRoles for all orgs | ScopedRoles within their org subtree only |
| **Users** | All users | Users in their subtree only (Phase D) |
| **Data Quality** | Platform-wide DQ dashboard | Subtree DQ dashboard |
| **Catalog / Governance** | Full catalog, MDM, DQ rules (CRUD) | Read-only catalog/MDM/DQ |

UX behavior:
- Admin sidebar shows **all** org modules (not just their own)
- Schema Manager is always visible
- Data Quality and Catalog sections appear
- A global admin gets the "platform" tier: full org tree, all schemas

---

### Perspective 3: **Executive / Reporting** (Decision-Maker View)
**Shown to:** Any authenticated user (the dashboards section)

| Section | What they see |
|---|---|
| **Executive Summary** | Scoped emissions KPIs (auto-scoped by role) |
| **Analytics** | Trend analysis, date range, breakdown |
| **Targets & Progress** | SBTi / net-zero tracking |
| **Data Quality Dashboard** | Quality scores, completeness |
| **Reporting** | GHG framework compliance reports |

UX behavior:
- All dashboard numbers **automatically org-scoped** (global admin sees all; data-owner sees their unit)
- This perspective is always visible — no role gate on dashboards (data is just scoped)

---

## 5. UI Pattern: Perspective Switcher (Header)

Instead of one mega-sidebar that tries to show everything, the **header carries a perspective switcher** — similar to how Ataccama ONE uses its top navigation:

```
┌─────────────────────────────────────────────────────────────┐
│ 🌿 AASTMT Carbon  │  [Data Entry]  [Dashboards]  [Admin]   │ 👤 Ahmed ▼
└─────────────────────────────────────────────────────────────┘
```

- **[Data Entry]** — always visible (your modules + tables)
- **[Dashboards]** — always visible (scoped view)
- **[Admin]** — only visible if user has `admins_group` role
- Each perspective swap changes the entire sidebar context

**For users with only one role:** No switcher is needed — the default perspective is set automatically based on their role.

**For users with multiple roles (e.g., a steward who also enters data):** The switcher appears. They can flip between "entering data for their department" and "managing their department's users/schema".

---

## 6. Sidebar Structure (per perspective)

### Sidebar: Data Entry Mode
```
📊 Dashboards (collapsed header)
   └── Executive Summary
   └── Analytics
   └── Targets
   └── Data Quality
   └── Reporting

─────────────────
🌿 Scope 1 — Direct
   └── [Module: Fleet Fuel]
      └── Gas Bills
      └── Vehicle Inventory
🔵 Scope 2 — Energy
   └── [Module: Electricity]
      └── Monthly Bills
🚛 Scope 3 — Value Chain
   (empty for this user)

─────────────────
❓ Help
💬 Feedback
```

### Sidebar: Admin Mode (Global Admin)
```
🏛️ Organization
   └── Org Unit Tree
   └── Users
   └── Access Control

─────────────────
🗄️ Schema Management
   └── Table Manager (all orgs)
   └── Field Manager

─────────────────
📚 Data Trust (future A5 work)
   └── Catalog
   └── MDM / Reference Data
   └── Data Quality Rules

─────────────────
⚙️ Platform
   └── Emission Factors
   └── Reporting Periods
   └── GWP / Standards
```

### Sidebar: Admin Mode (Org-Scoped Steward)
Same as above, BUT:
- Org Unit Tree = read-only + their subtree
- Table Manager = filtered to their org's modules
- Access Control = only their subtree roles
- Data Trust = read-only (no write per A2 permission model)

---

## 7. What Already Exists vs What Needs Building

### ✅ Already Implemented (correct foundation)
| What | Status |
|---|---|
| Single React app | ✅ Done |
| `AdminRoute` component gating admin routes | ✅ Done |
| Sidebar shows/hides Schema Manager based on `canSchemaAdmin()` | ✅ Done |
| Server-side org scoping (modules, tables, data rows) | ✅ Done (A3) |
| Admin pages: OrgUnits, Access Control, Users | ✅ Done |
| Dashboards section with 5 views | ✅ Done |
| Data entry grid | ✅ Done |

### ❌ Gaps — What A5 Needs to Build

| Gap | Priority | Effort |
|---|---|---|
| **Perspective switcher in header** — Data Entry / Dashboards / Admin tabs | HIGH | Medium |
| **Scoped dashboard numbers** — emissions aggregates must filter by `get_visible_module_ids(user)` | HIGH (critical data leak fix) | Small backend |
| **Admin sidebar reorganized** — Admin mode sidebar (Org / Schema / Data Trust / Platform) | HIGH | Medium |
| **Data-owner sidebar cleaned** — operator sidebar should NOT show schema manager or admin links | HIGH | Small |
| **Role-aware welcome screen** — data-owner lands on their data entry; admin lands on org dashboard | MEDIUM | Small |
| **Steward-scoped admin pages** — org-scoped steward sees only their subtree in Users/Access pages | MEDIUM | Medium backend+frontend |
| **"My Scope" info banner** — tell the data-owner clearly "you are viewing: Transportation / Fleet" | LOW | Small |

---

## 8. What NOT to Build (Non-Goals)

- ❌ Separate `/admin` deployment or different domain
- ❌ Separate login page for admins
- ❌ Role-based redirect on login to different apps
- ❌ Duplicate components (one for admin, one for user) — use the same components with props
- ❌ AI/Pulse/LLM features — still frozen, owned by Pulse externally
- ❌ Reports generator backend — missing feature but not in this phase

---

## 9. Backend Work Required for A5

### Critical: Fix Dashboard Data Scoping Leak
The #1 priority — per DESIGN_ORG_ACCESS_MODEL.md §4.6:

```python
# emissions/views.py — EVERY aggregate endpoint must apply:
def _scope(user, qs):
    allowed = get_visible_module_ids(user)
    return qs if allowed is None else qs.filter(module_id__in=allowed)
```

Apply to: `DashboardAPIView`, `YearlyComparisonAPIView`, `ReportAPIView`, `CalculationViewSet`

This gives every user a correctly-scoped dashboard automatically — org-owned subtree for stewards, everything for global admins.

### New API: `/api/me/context/`
Return the current user's "context card" — what org units they can see, what modules they own, their roles, their effective scope. The frontend uses this to decide which perspective to show and what to display in the "You are viewing:" banner.

---

## 10. Implementation Plan (A5 Sprint)

### Phase A5-1: Backend Scope Fixes (2–3 hours)
1. Apply `_scope()` to all emissions read endpoints
2. Add `/api/me/context/` endpoint
3. Write test: data-owner's dashboard numbers ≠ global admin's dashboard numbers

### Phase A5-2: Frontend Perspective Architecture (4–6 hours)
1. Add perspective context to `AuthContext` (`currentPerspective`, `setPerspective`)
2. Add perspective switcher tabs to `Header` component (visible only when user has admin role)
3. Refactor `SidebarMenu` to render different item sets based on `currentPerspective`
4. Clean data-entry sidebar: remove admin links from operator view
5. Reorganize admin sidebar: Org / Schema / Data Trust / Platform sections

### Phase A5-3: Role-Aware Defaults (1–2 hours)
1. On login: data-only users land on their data entry page (first module)
2. On login: admin users land on Executive Summary dashboard
3. "My Scope" banner in Layout for non-admin users

### Phase A5-4: Polish (1–2 hours)
1. Breadcrumb showing current org context
2. Avatar/header shows org name for scoped users
3. Empty state for data-owner with no assigned modules

---

## 11. Summary Decision

```
ONE app. ONE login. Role-adaptive perspectives.

Data Owner  → [Data Entry mode]    Lean sidebar, their modules/tables, scoped dashboard
Steward     → [Admin mode]         Org management (their subtree), schema (their tables), read-only governance
Global Admin → [Admin mode + full] Everything: full org tree, all schemas, full governance

No separate admin console.
No separate URL.
No "mode" that requires re-login.
Progressive disclosure through the perspective switcher.
```

This is the Ataccama ONE pattern, lighter. One trust surface, one product, one deployment.

---

*Decided: 2026-07-18*
*Implements: RUN A5 — Data Trust Surfacing Decision*
