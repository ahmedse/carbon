# Pulse Admin Remake — Control Plane

**Status:** Phases 0–6 implemented (2026-09-17); Phase 7 harden ongoing  
**ADR:** [0036 — Pulse Control Plane IA](../../.ai-toolkit/decisions/0036-pulse-control-plane-ia.md)  
**Extends:** ADR-0031 D8 · ADR-0011 engage/observe split

---

## 1. Goal

Replace the ~29-item AI Admin panel farm with a **Pulse Control Plane**: six steward jobs that
define, secure, operate, evidence, and improve Pulse.

**Done when** a steward can, without stitching five screens:

1. See health + contain risk in under a minute  
2. Own domain processes end-to-end (define → version → scope → autonomy → publish → kill)  
3. Govern intelligence assets (knowledge, memory, skills, prompts) with provenance and revoke  
4. Reconstruct any decision/run on one evidence spine  
5. Run closed learning cycles (propose → judge → admit → measure)  
6. Enforce spend, roles, and fail-closed platform controls  

**Non-goals:** rewrite Pulse engine; rebuild chat UX; MCP admin UI; second policy stack beside PDP.

---

## 2. Target IA (six destinations)

| Dest | Path | Job |
|------|------|-----|
| Command Center | `/admin/ai` | Health, queues, containment shortcuts |
| Domain | `/admin/ai/domain` | Processes, capabilities, agents, policy |
| Assets | `/admin/ai/assets` | Knowledge, memory, graph, skills, prompts |
| Evidence | `/admin/ai/evidence` | Runs, audit, inbox, watches, logs, quality |
| Learning | `/admin/ai/learning` | Review queue, candidates, flywheel, evals |
| Platform | `/admin/ai/platform` | Spend, engine settings, roles |

**Engage (not Control Plane nav):** shell AI workspace; legacy routes `/admin/ai/workspace`,
`/admin/ai/conversations` remain during migration.

D8 modules → destinations: Registry/Policy/Conformance → Domain; Review/Evals → Learning;
Spend → Platform; Audit Explorer → Evidence.

---

## 3. Freeze (Phase 0 — enforced)

**Do not add** a new top-level `/admin/ai/<noun>` sidebar peer or route-as-product-page.

Allowed:

- Tab or object page under one of the six destinations  
- Legacy redirect entry in `pulseControlIa.js`  
- ADR exception referencing this document  

PR checklist: link ADR-0036; confirm no new peer nav item in `ShellSidebar` `case 'ai-admin'`.

---

## 4. Redirect matrix

Source of truth: `carbon-frontend/src/pages/admin/ai/control/pulseControlIa.js` (`LEGACY_REDIRECTS`).

| Legacy path | Target |
|-------------|--------|
| `/admin/ai/expertise` | `/admin/ai?tab=expertise` |
| `/admin/ai/monitoring` | `/admin/ai?tab=monitoring` |
| `/admin/ai/registry` | `/admin/ai/domain?tab=processes` |
| `/admin/ai/capabilities` | `/admin/ai/domain?tab=capabilities` |
| `/admin/ai/agents` | `/admin/ai/domain?tab=agents` |
| `/admin/ai/tools` | `/admin/ai/domain?tab=tools` |
| `/admin/ai/topology` | `/admin/ai/domain?tab=topology` |
| `/admin/ai/archetypes` | `/admin/ai/domain?tab=archetypes` |
| `/admin/ai/knowledge` | `/admin/ai/assets?tab=knowledge` |
| `/admin/ai/memory` | `/admin/ai/assets?tab=memory` |
| `/admin/ai/graph` | `/admin/ai/assets?tab=graph` |
| `/admin/ai/skills` | `/admin/ai/assets?tab=skills` |
| `/admin/ai/prompts` | `/admin/ai/assets?tab=prompts` |
| `/admin/ai/audit` | `/admin/ai/evidence?tab=audit` |
| `/admin/ai/runs` | `/admin/ai/evidence?tab=runs` |
| `/admin/ai/inbox` | `/admin/ai/evidence?tab=inbox` |
| `/admin/ai/watches` | `/admin/ai/evidence?tab=watches` |
| `/admin/ai/logs` | `/admin/ai/evidence?tab=logs` |
| `/admin/ai/output-quality` | `/admin/ai/evidence?tab=quality` |
| `/admin/ai/review-queue` | `/admin/ai/learning?tab=review` |
| `/admin/ai/feedback` | `/admin/ai/learning?tab=feedback` |
| `/admin/ai/learning-flywheel` | `/admin/ai/learning?tab=flywheel` |
| `/admin/ai/skill-learning` | `/admin/ai/learning?tab=skills` |
| `/admin/ai/budget-usage` | `/admin/ai/platform?tab=spend` |
| `/admin/ai/engine-settings` | `/admin/ai/platform?tab=engine` |

**Note:** `/admin/ai/learning` is now the Learning hub (default tab `review`). Legacy Learning Jobs
live at `/admin/ai/learning?tab=jobs` (redirect from nothing — old path was `/admin/ai/learning`
itself; e2e that expected Jobs-only must use `?tab=jobs`).

**Not redirected (engage):** `/admin/ai/workspace`, `/admin/ai/conversations`.

---

## 5. Cut map (summary)

| Current | Fate |
|---------|------|
| Overview / Expertise / Monitoring | Command tabs |
| Registry / Caps / Agents / Tools / Topology / Archetypes | Domain tabs |
| Knowledge / Memory / Graph / Skills / Prompts | Assets tabs |
| Audit / Runs / Inbox / Watches / Logs / Quality | Evidence tabs |
| Review / Feedback / Jobs / Flywheel / Skill Learning | Learning tabs |
| Budget / Engine Settings | Platform tabs |
| Workspace / Conversations | Out of Control nav |
| Thin `PulseDataPanel` peers | Demoted to tabs; deepen in Phase 4 |

---

## 6. Phases

| Phase | Theme | Exit gate |
|-------|--------|-----------|
| **0** | Freeze + ADR + redirect matrix | This doc + ADR-0036 + `pulseControlIa.js` |
| **1** | Six-nav skeleton; mount existing panels; redirects | Sidebar ≤ 6; all writes still work; CI paths updated |
| **2** | Command Center + Evidence spine | “Why was X allowed?” ≤3 clicks; graduated containment |
| **3** | Domain depth (object pages, scope editor, policy dry-run, persist reject) | Pilot process without raw JSON |
| **4** | Assets governance (revoke, version, provenance) | Memory revoke + skill admission evidenced |
| **5** | Learning Studio (unified candidates, eval gates) | One improvement lifecycle, zero authority widening |
| **6** | Platform (caps, writable knobs, roles UI); delete dead panels | Budget trip without deploy |
| **7** | Harden (steward e2e, audit completeness, perf) | Journey pack green |

### Phase status

- [x] **0** ADR-0036 + freeze + redirect matrix  
- [x] **1** Six destinations + hubs + engage split  
- [x] **2** Command Center (`control/command/`, containment) + Evidence Explorer (`control/evidence/`)  
- [x] **3** Process reject persisted + Policy dry-run tab (`control/pdp/dry-run/`)  
- [x] **4** Memory revoke (`POST …/facts/<id>/revoke/`) + Assets Memory governance UI  
- [x] **5** Learning candidates (`control/candidates/`) + learning freeze blocks skill promote  
- [x] **6** Budget override (`control/budget/`) wired into usage + LLM router  
- [x] **7** Control API tests green (6); e2e headings updated; remaining: full steward Playwright pack + delete unused thin panel files when redirects retire  

### APIs (mounted under `/carbon-api/ai/pulse/control/`)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `command/` | Health + queues + containment + spend |
| GET | `evidence/?run_id=` | Unified evidence spine |
| GET/POST | `containment/` | Graduated containment |
| GET | `candidates/` | Unified learning candidates |
| POST | `pdp/dry-run/` | PDP simulation |
| GET/PATCH | `budget/` | Daily USD budget override |

Also: `POST …/registry/processes/<id>/reject/`, `POST …/memory/facts/<id>/revoke/`.

### Shipped — process object + scope (Phase 3)

- Route: `/admin/ai/domain/processes/:processId` (`ProcessObjectPage`)
- Registry row click → object page (list stays list; create draft then navigates)
- Tabs: Overview · Steps & autonomy · Scope (structured) · Diff · Advanced JSON
- Scope editor fields: source, org unit, roles, approval validity + objective (draft-only write)

### Remaining gaps (honest)

- Prompt version activate/rollback UI  
- KnowledgeItem REST CRUD  
- Roles matrix UI (Django admin / groups still used)  
- Steward e2e journeys J1–J7 still thin  
- Delete unused thin PulseDataPanel wrappers when unused

---

## 7. Roles (unchanged contract)

`ai:view_console` · `ai:auditor` · `ai:process_owner` · `ai:publisher` · `ai:operator` ·
`ai:policy_owner` · `ai:manage_console` · platform admin.

View never implies publish.

---

## 8. Steward journeys (acceptance for later phases)

J1 Contain → J2 Publish SoD → J3 Reject persisted → J4 Evidence PDP → J5 Skill promote/reuse →
J6 Memory revoke → J7 Budget trip.

---

## 9. Four representations (UI must not merge)

Observed · Approved · Executable · Instance — see remediation plan §2.
