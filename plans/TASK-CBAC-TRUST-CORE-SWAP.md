# TASK — CBAC TRUST-CORE SWAP (Backend RBAC → Capability-Based Access Control)
# =================================================================
# Status: OPEN — ready for worker dispatch
# Date: 2026-08-11
# Worker role: backend-worker (see .ai-toolkit/roles/backend-worker.md)
# Owner: Master Architect
#
# ── PROBLEM ─────────────────────────────────────────────────────────
# Docs claim CBAC ("Carbon does NOT use RBAC" — docs/CARBON_ENTERPRISE_PHASED_PLAN.md),
# and the FRONTEND enforces CBAC (src/authz.js can(), AdminRoute requiredCapability,
# ShellSidebar capability filtering). But the BACKEND trust-core apps still enforce
# **RBAC**:
#   - catalog/, dq/, mdm/, evidence/, importexport/, connections/, dataschema/
#     use ReadAnyWriteGlobalAdmin / AdminOrSuperuserOnly / HasScopedRole
#     (group-membership checks — ZERO capability declarations; verified by grep:
#     no `required_capability` / `required_write_capability` / `domain_lead_groups`
#     anywhere in those apps).
#   - /carbon-api/me/ hands the frontend `capabilities[]`, but the API never
#     validates them. Frontend gates on capabilities; backend gates on groups.
#   - Split-brain: a user stripped of a capability in the registry can still
#     call the API if their group passes the RBAC check (and vice-versa).
#
# ── REFERENCE IMPLEMENTATION (already CBAC) ─────────────────────────
# backend/emissions/views.py is the pattern to copy:
#   class ReportingPeriodViewSet:   permission_classes=[ReadAnyWriteAdmin]
#                                  required_write_capability='carbon:manage_reporting_periods'
#   class EmissionFactorViewSet:   permission_classes=[AdminOrSuperuserOnly]
#                                  required_capability='carbon:manage_emission_factors'
# The supporting machinery already exists:
#   - backend/accounts/capabilities.py  (registry, GROUP_CAPABILITIES, get_user_capabilities,
#                                        has_capability, IMPLIES expansion)
#   - backend/accounts/permissions.py   (ReadAnyWriteAdmin, AdminOrSuperuserOnly →
#                                        _check_write_capability(): superuser/global-admin
#                                        short-circuit → required_capability →
#                                        domain_lead_groups fallback)
#   - carbon-frontend/src/capabilities.js (mirror, already synced)
#
# ── TWO DESIGN DECISIONS REQUIRED BEFORE CODING (flag to MA) ────────
#
# DD-1 (PREREQUISITE — BLOCKS EVERYTHING): org-scoped admins must stay READ-ONLY.
#   Today `ReadAnyWriteGlobalAdmin` write = global admin only; org-scoped
#   admins_group members are read-only (documented design, TRUST reports).
#   BUT `get_user_capabilities()` (capabilities.py:628) collects group names
#   from ScopedRole **ignoring org_unit** — so `alamein.admin` (admins_group on
#   Alamein Transport org) currently resolves to `{"*"}` → would become a writer
#   EVERYWHERE after the swap. Fix: wildcard/`*` groups grant full caps ONLY when
#   org_unit IS NULL; org-scoped admins_group → view_* read capabilities only.
#   → Small, surgical change in capabilities.py (filter ScopedRole by org_unit).
#
# DD-2 (PREREQUISITE): GROUP_CAPABILITIES is missing trust-core VIEW caps for
#   data groups. dataowners_group / analysts_group / viewers_group / auditors_group
#   do NOT currently receive `catalog:view`, `dq:view`, `mdm:view`,
#   `connections:view`, `importexport:view`, `dataschema:view`, evidence-view.
#   If we gate reads on view caps, data owners LOSE trust-core read access
#   (regression vs today's scoped reads). Fix: add view_* caps to those four
#   groups in GROUP_CAPABILITIES. Leads (catalog_lead/dq_lead/mdm_lead) already
#   inherit their app's view cap via IMPLIES (manage → view).
#
# ── FULL INVENTORY (every view → current permission → target capability) ──
# Line numbers verified 2026-08-11. Target class: RW = ReadAnyWriteAdmin
# (read: any auth; write: capability), AO = AdminOrSuperuserOnly
# (all access: capability). Keep [IsAuthenticated] prefix where currently present.
# =============================================================================

## CATALOG  (app: catalog)
| # | Class                      | File:Line      | Current perm                          | Target perm | required_write_capability / required_capability |
|---|----------------------------|----------------|---------------------------------------|-------------|--------------------------------------------------|
| 1 | DataDomainViewSet          | catalog/views.py:34  | ReadAnyWriteGlobalAdmin         | RW          | required_write_capability='catalog:manage_metadata' |
| 2 | GlossaryTermViewSet        | catalog/views.py:53  | ReadAnyWriteGlobalAdmin         | RW          | required_write_capability='catalog:manage_metadata' |
| 3 | TagViewSet                 | catalog/views.py:127 | ReadAnyWriteGlobalAdmin         | RW          | required_write_capability='catalog:manage_metadata' |
| 4 | AssetProfileViewSet        | catalog/views.py:146 | ReadAnyWriteGlobalAdmin         | RW          | required_write_capability='catalog:manage_products' |
| 5 | GovernanceEventViewSet     | catalog/views.py:262 | ReadAnyWriteGlobalAdmin (RO)    | RW          | required_write_capability='catalog:view_governance' (read-only view; no writes) |
| 6 | GovernanceComplianceView   | catalog/views.py:273 | ReadAnyWriteGlobalAdmin (RO)    | RW          | required_write_capability='catalog:view_governance' |
| 7 | GovernancePolicyViewSet    | catalog/views.py:296 | ReadAnyWriteGlobalAdmin         | RW          | required_write_capability='catalog:manage_policies' |
| 8 | CatalogSearchView          | catalog/views.py:336 | IsAuthenticated                 | RW          | required_write_capability='catalog:view' (GET-only; safe) |

## DQ  (app: dq)
| # | Class                      | File:Line      | Current perm                          | Target perm | capability |
|---|----------------------------|----------------|---------------------------------------|-------------|------------|
| 9  | FieldProfileViewSet        | dq/views.py:71     | IsAuthenticated (RO)             | RW          | required_write_capability='dq:view' |
| 10 | TableProfileViewSet        | dq/views.py:102    | IsAuthenticated (RO)             | RW          | required_write_capability='dq:view' |
| 11 | DQRuleViewSet              | dq/views.py:134    | IsAuthenticated, ReadAnyWriteGlobalAdmin | RW    | required_write_capability='dq:manage_rules' |
| 12 | DQResultViewSet            | dq/views.py:379    | IsAuthenticated (RO)             | RW          | required_write_capability='dq:view' |
| 13 | ProfileTriggerView         | dq/views.py:473    | AdminOrSuperuserOnly             | AO          | required_capability='dq:manage_rules' |
| 14 | BulkProfileView            | dq/views.py:627    | AdminOrSuperuserOnly             | AO          | required_capability='dq:manage_rules' |
| 15 | DQRunView (legacy)         | dq/views.py:672    | AdminOrSuperuserOnly             | AO          | required_capability='dq:manage_rules' |
| 16 | DQMetricsView              | dq/views.py:734    | IsAuthenticated (RO)             | RW          | required_write_capability='dq:view' |
| 17 | TableDQMetricsView         | dq/views.py:823    | IsAuthenticated (RO)             | RW          | required_write_capability='dq:view' |
| 18 | FieldDQMetricsView         | dq/views.py:888    | IsAuthenticated (RO)             | RW          | required_write_capability='dq:view' |
| 19 | RunDQValidationView        | dq/views.py:925    | AdminOrSuperuserOnly             | AO          | required_capability='dq:manage_rules' |
| 20 | DQSuggestView              | dq/views.py:968    | AdminOrSuperuserOnly             | AO          | required_capability='dq:manage_rules' |
| 21 | FreshnessCheckViewSet      | dq/views.py:1037   | IsAuthenticated (RO)             | RW          | required_write_capability='dq:view' |
| 22 | SchemaSnapshotViewSet      | dq/views.py:1064   | IsAuthenticated (RO)             | RW          | required_write_capability='dq:view' |
| 23 | SchemaChangeViewSet        | dq/views.py:1089   | IsAuthenticated (RO)             | RW          | required_write_capability='dq:view' |
| 24 | RuleTagViewSet             | dq/views.py:1118   | IsAuthenticated, ReadAnyWriteGlobalAdmin | RW    | required_write_capability='dq:manage_rules' |
| 25 | RuleFieldAssignmentViewSet | dq/views.py:1128   | IsAuthenticated, ReadAnyWriteGlobalAdmin | RW    | required_write_capability='dq:manage_rules' |
| 26 | GateCheckView              | dq/views.py:1154   | IsAuthenticated, ReadAnyWriteGlobalAdmin | RW    | required_write_capability='dq:manage_rules' |
| 27 | DQJobViewSet               | dq/views.py:1234   | IsAuthenticated, ReadAnyWriteGlobalAdmin | RW    | required_write_capability='dq:manage_rules' |
| 28 | DQSuggestionViewSet        | dq/views.py:1352   | IsAuthenticated, ReadAnyWriteGlobalAdmin | RW    | required_write_capability='dq:view' |
| 29 | DQAnomalyViewSet           | dq/views.py:1494   | IsAuthenticated (RO)             | RW          | required_write_capability='dq:view' |

## MDM  (app: mdm)
| # | Class                      | File:Line      | Current perm                          | Target perm | capability |
|---|----------------------------|----------------|---------------------------------------|-------------|------------|
| 30 | ReferenceSetViewSet        | mdm/views.py:26     | IsAuthenticated (+steward obj check) | RW       | required_write_capability='mdm:manage' (keep steward object check) |
| 31 | ReferenceValueViewSet      | mdm/views.py:269    | CanManageReferenceValues (steward)   | RW        | required_write_capability='mdm:manage' (keep steward object check) |
| 32 | BindFieldView              | mdm/views.py:375    | ReadAnyWriteGlobalAdmin          | RW          | required_write_capability='mdm:manage' |
| 33 | FieldOptionsView           | mdm/views.py:442    | IsAuthenticated (RO)             | RW          | required_write_capability='mdm:view' |
| 34 | OrgUnitViewSet             | mdm/views.py:465    | ReadAnyWriteGlobalAdmin          | RW          | required_write_capability='platform:manage_org_units' (NOTE: DD-1 applies) |

## EVIDENCE  (app: evidence — NO capability in registry yet; see notes)
| # | Class                      | File:Line      | Current perm                          | Target perm | capability |
|---|----------------------------|----------------|---------------------------------------|-------------|------------|
| 35 | EvidenceViewSet            | evidence/views.py:16 | IsAuthenticated, IsEvidenceOwnerOrAdmin | RW       | required_write_capability='evidence:manage' **OR** keep IsEvidenceOwnerOrAdmin (object-level owner check is ALREADY capability-like). DECISION NEEDED: add `evidence:manage` + `evidence:view` to registry (DD-3), or keep owner-based. Recommend: add caps; keep owner check for object-level. |

## CONNECTIONS  (app: connections)
| # | Class                      | File:Line      | Current perm                          | Target perm | capability |
|---|----------------------------|----------------|---------------------------------------|-------------|------------|
| 36 | DataSourceViewSet          | connections/views.py:16 | AdminOrSuperuserOnly           | AO          | required_capability='connections:manage' |
| 37 | ConsumingConnectionViewSet | connections/views.py:48 | AdminOrSuperuserOnly           | AO          | required_capability='connections:manage' |

## IMPORTEXPORT  (app: importexport)
| # | Class                      | File:Line      | Current perm                          | Target perm | capability |
|---|----------------------------|----------------|---------------------------------------|-------------|------------|
| 38 | ExportProjectViewSet       | importexport/views.py:20  | AdminOrSuperuserOnly        | AO          | required_capability='importexport:manage' |
| 39 | ImportJobViewSet           | importexport/views.py:68  | AdminOrSuperuserOnly        | AO          | required_capability='importexport:manage' |
| 40 | ExportJobViewSet           | importexport/views.py:137 | IsAuthenticated (RO)        | RW          | required_write_capability='importexport:view' |

## DATASCHEMA  (app: dataschema)
| # | Class                      | File:Line      | Current perm                          | Target perm | capability |
|---|----------------------------|----------------|---------------------------------------|-------------|------------|
| 41 | ScopedViewSet (base)       | dataschema/views.py:48   | IsAuthenticated, HasScopedRole  | RW          | required_write_capability='dataschema:view' (base for reads) |
| 42 | DataTableViewSet           | dataschema/views.py:71   | IsAuthenticated, ReadScopedWriteAdmin | RW    | required_write_capability='dataschema:manage' |
| 43 | DataFieldViewSet           | dataschema/views.py:187  | IsAuthenticated, ReadScopedWriteAdmin | RW    | required_write_capability='dataschema:manage' |
| 44 | DataRowViewSet             | dataschema/views.py:271  | (inherits ScopedViewSet)       | RW          | required_write_capability='dataschema:view' (reads; writes data → carbon:enter_data for row writes) |
| 45 | SchemaChangeLogViewSet     | dataschema/views.py:606  | (inherits ScopedViewSet)       | RW          | required_write_capability='dataschema:view' |
| 46 | TableRelationViewSet       | dataschema/views.py:626  | IsAuthenticated, ReadScopedWriteAdmin | RW    | required_write_capability='dataschema:manage' |

## ACCOUNTS + CORE + CONFIG  (platform app)
| # | Class                      | File:Line      | Current perm                          | Target perm | capability |
|---|----------------------------|----------------|---------------------------------------|-------------|------------|
| 47 | UserViewSet                | accounts/views.py:226   | HasScopedRole (required_role="admin") | AO        | required_capability='platform:manage_users' |
| 48 | GroupViewSet               | accounts/views.py:235   | HasScopedRole (required_role="admin") | AO        | required_capability='platform:manage_groups' |
| 49 | ScopedRoleViewSet          | accounts/views.py:306   | CanManageScopedRoles            | AO          | required_capability='platform:manage_access' |
| 50 | RoleAssignmentAuditLogViewSet | accounts/views.py:396 | HasScopedRole (required_role="audit") | AO    | required_capability='platform:view_audit' |
| 51 | ModuleViewSet              | core/views.py:13        | HasScopedRole (required_role=admin,admins_group) | AO | required_capability='platform:manage_apps' |
| 52 | NotificationViewSet        | core/views.py:109       | IsAuthenticated                | keep        | no gating needed (own notifications) |
| 53 | config_views (AppConfig)   | accounts/config_views.py:17 | IsAuthenticated, AdminOrSuperuserOnly | AO   | required_capability='platform:manage_apps' |
| 54 | config/log_api             | config/log_api.py:26    | IsAuthenticated, AdminOrSuperuserOnly | AO   | required_capability='platform:view_audit' |
| 55 | dq/config_views            | dq/config_views.py:12   | AdminOrSuperuserOnly             | AO          | required_capability='platform:admin' |

# ── WORK ITEMS (ordered; RULE_11: every change ships a regression test) ──
#
# W0  DD-1 + DD-2 in capabilities.py (BLOCKING prereq):
#     - get_user_capabilities: org-aware wildcard (org_unit IS NULL → full; else read caps)
#     - GROUP_CAPABILITIES: add view_* caps for dataowners/analysts/viewers/auditors
#       (catalog:view, dq:view, mdm:view, connections:view, importexport:view,
#        dataschema:view, evidence:view if DD-3 adds it)
#     - Regression tests: test_capability_rbac_extensive.py + new org-scoped-admin test
#       (alamein.admin on org → NO manage_* caps; ahmed → "*").
# W1  Catalog swap (rows 1-8): ReadAnyWriteGlobalAdmin → ReadAnyWriteAdmin +
#     required_write_capability. Keep get_queryset() org-scoping untouched.
#     Tests: existing test_scoped_access.py must still pass + add per-capability test.
# W2  DQ swap (rows 9-29): RW/AO + caps. Legacy DQRunView keeps dq:manage_rules.
#     Tests: dq test module (249) + new capability-denied tests for scoped user.
# W3  MDM swap (rows 30-34): RW + caps; PRESERVE steward object checks.
#     Tests: mdm tests (23) + steward/capability matrix test.
# W4  Evidence (row 35): DECISION on DD-3 (add evidence caps to registry OR keep
#     owner-based). Default: add `evidence:view`/`evidence:manage` caps + keep owner
#     object check. Tests: evidence API tests.
# W5  Connections + Importexport (rows 36-40): AO/RW + caps.
#     Tests: per-app tests + capability-denied test.
# W6  Dataschema (rows 41-46): RW + caps; DataRowViewSet write → carbon:enter_data
#     (DECISION: keep org scoping from HasScopedRole/ReadScopedWriteAdmin).
# W7  Accounts/core/config (rows 47-55): AO + platform caps.
#     Tests: accounts tests (CBAC/RBAC suites) + platform-manage capability tests.
# W8  Full regression: pytest (must stay ≥ 1012 + 11 subtests), Django runner (274),
#     frontend build + cbac.test.jsx, verify.sh full → GATE.
#
# ── DEFINITION OF DONE ──────────────────────────────────────────────
# 1. Zero `ReadAnyWriteGlobalAdmin` / bare `AdminOrSuperuserOnly` /
#    bare `HasScopedRole` usages remain in catalog/dq/mdm/evidence/importexport/
#    connections/dataschema (grep must only match emissions' intentional + new caps).
# 2. Every touched view declares required_capability or required_write_capability.
# 3. Org scoping in get_queryset() preserved 1:1 (no behavior change for reads).
# 4. org-scoped admins_group still READ-ONLY on governance resources (DD-1 test green).
# 5. Data-owner reads on trust-core still work (DD-2 test green: scoped user GET 200).
# 6. RULE_11: regression test per W-item; all suites green (see W8).
# 7. verify.sh full: GATE PASS (pre-existing debt list unchanged — do NOT fix
#    unrelated lint/UI debt in this task; report it, don't touch it).
#
# ── POST-TASK (out of scope, log only) ──────────────────────────────
# - Update docs/CARBON_ENTERPRISE_PHASED_PLAN.md claim to "backend now enforces CBAC".
# - Optional: add capability column to /admin UI group matrix (already exists:
#   get_capability_matrix()).
