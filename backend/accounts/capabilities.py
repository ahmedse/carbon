"""
Capability-Based Access Control (CBAC) — Single Source of Truth.

Every permission check in the platform flows from this file.
No other file hardcodes group names or permission strings.

Architecture:
  Group → Capabilities → Permission Classes → Views
                                   ↘ me_context → Frontend

A Capability is a namespaced action: "{domain}:{action}"
  - "platform:*"          — full platform administration
  - "carbon:manage_factors" — manage emission factors
  - "carbon:enter_data"   — enter emission data for assigned org

Adding a new app:
  1. Add capabilities to CAPABILITY_REGISTRY
  2. Map groups in GROUP_CAPABILITIES
  3. Use has_capability() in permission classes
  4. Mirror CAPABILITIES in frontend src/capabilities.js
"""

from __future__ import annotations

from typing import Set, Dict, FrozenSet, Optional
from dataclasses import dataclass, field


# ═══════════════════════════════════════════════════════════════════
# CAPABILITY REGISTRY
# ═══════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Capability:
    """A single capability — the atomic unit of authorization."""
    key: str                              # "carbon:manage_emission_factors"
    domain: str                           # "carbon"
    action: str                           # "manage_emission_factors"
    label: str                            # "Manage Emission Factors"
    description: str                      # "Create, update, delete emission factors"
    category: str = "general"             # "admin" | "data" | "reporting" | "platform"
    default_roles: FrozenSet[str] = field(default_factory=frozenset)


# ── Platform capabilities ──────────────────────────────────────────
PLATFORM_ADMIN = Capability(
    key="platform:admin",
    domain="platform",
    action="admin",
    label="Platform Administration",
    description="Full platform administration: manage users, groups, org units, access control",
    category="platform",
)

PLATFORM_MANAGE_USERS = Capability(
    key="platform:manage_users",
    domain="platform",
    action="manage_users",
    label="Manage Users",
    description="Create, update, deactivate platform users",
    category="platform",
)

PLATFORM_MANAGE_GROUPS = Capability(
    key="platform:manage_groups",
    domain="platform",
    action="manage_groups",
    label="Manage Groups & Roles",
    description="Create, update, delete groups and manage role assignments",
    category="platform",
)

PLATFORM_MANAGE_ORG_UNITS = Capability(
    key="platform:manage_org_units",
    domain="platform",
    action="manage_org_units",
    label="Manage Org Units",
    description="Create, update organizational units",
    category="platform",
)

PLATFORM_MANAGE_ACCESS = Capability(
    key="platform:manage_access",
    domain="platform",
    action="manage_access",
    label="Manage Access Control",
    description="Grant, revoke, and audit ScopedRole assignments",
    category="platform",
)

PLATFORM_VIEW_AUDIT = Capability(
    key="platform:view_audit",
    domain="platform",
    action="view_audit",
    label="View Audit Log",
    description="View platform audit trail",
    category="platform",
)

PLATFORM_MANAGE_APPS = Capability(
    key="platform:manage_apps",
    domain="platform",
    action="manage_apps",
    label="Manage Apps",
    description="Enable, disable, configure platform apps",
    category="platform",
)

# ── Carbon domain capabilities ─────────────────────────────────────

CARBON_VIEW_CONSOLE = Capability(
    key="carbon:view_console",
    domain="carbon",
    action="view_console",
    label="View Carbon Console",
    description="View the Carbon overview dashboard",
    category="general",
)

CARBON_VIEW_DASHBOARD = Capability(
    key="carbon:view_dashboard",
    domain="carbon",
    action="view_dashboard",
    label="View Emissions Dashboard",
    description="View emissions data and charts",
    category="general",
)

CARBON_VIEW_ANALYTICS = Capability(
    key="carbon:view_analytics",
    domain="carbon",
    action="view_analytics",
    label="View Analytics & Trends",
    description="View cross-org emission trends and analytics",
    category="reporting",
)

CARBON_ENTER_DATA = Capability(
    key="carbon:enter_data",
    domain="carbon",
    action="enter_data",
    label="Enter Emission Data",
    description="Create, update, delete emission data for assigned org units",
    category="data",
)

CARBON_VIEW_MY_DATA = Capability(
    key="carbon:view_my_data",
    domain="carbon",
    action="view_my_data",
    label="View My Data",
    description="View emission data for assigned org units",
    category="data",
)

CARBON_MANAGE_EMISSION_FACTORS = Capability(
    key="carbon:manage_emission_factors",
    domain="carbon",
    action="manage_emission_factors",
    label="Manage Emission Factors",
    description="Create, update, delete emission factors",
    category="admin",
)

CARBON_MANAGE_CALCULATION_RULES = Capability(
    key="carbon:manage_calculation_rules",
    domain="carbon",
    action="manage_calculation_rules",
    label="Manage Calculation Rules",
    description="Create, update, delete calculation rules",
    category="admin",
)

CARBON_MANAGE_GWP = Capability(
    key="carbon:manage_gwp",
    domain="carbon",
    action="manage_gwp",
    label="Manage GWP Reference",
    description="Create, update, delete global warming potential values",
    category="admin",
)

CARBON_MANAGE_SBTI_TARGETS = Capability(
    key="carbon:manage_sbti_targets",
    domain="carbon",
    action="manage_sbti_targets",
    label="Manage SBTi Targets",
    description="Create, update, delete science-based targets",
    category="admin",
)

CARBON_MANAGE_REPORTING_PERIODS = Capability(
    key="carbon:manage_reporting_periods",
    domain="carbon",
    action="manage_reporting_periods",
    label="Manage Reporting Periods",
    description="Create, update, delete reporting periods",
    category="admin",
)

CARBON_MANAGE_INVENTORY_COVERAGE = Capability(
    key="carbon:manage_inventory_coverage",
    domain="carbon",
    action="manage_inventory_coverage",
    label="Manage Inventory Coverage",
    description="Declare emission sources, track coverage, set coverage goals",
    category="admin",
)

CARBON_TRIGGER_CALCULATIONS = Capability(
    key="carbon:trigger_calculations",
    domain="carbon",
    action="trigger_calculations",
    label="Trigger Calculations",
    description="Run emission calculations for data tables",
    category="admin",
)

CARBON_VERIFY_DATA = Capability(
    key="carbon:verify_data",
    domain="carbon",
    action="verify_data",
    label="Verify & Reject Data",
    description="Verify or reject submitted reporting periods",
    category="admin",
)

CARBON_GENERATE_REPORTS = Capability(
    key="carbon:generate_reports",
    domain="carbon",
    action="generate_reports",
    label="Generate Reports",
    description="Generate emission reports",
    category="reporting",
)

CARBON_VIEW_CALCULATIONS = Capability(
    key="carbon:view_calculations",
    domain="carbon",
    action="view_calculations",
    label="View Calculations",
    description="View emission calculation results",
    category="data",
)

CARBON_VIEW_VERIFICATION = Capability(
    key="carbon:view_verification",
    domain="carbon",
    action="view_verification",
    label="View Verification",
    description="View verification records",
    category="data",
)

CARBON_VIEW_REPORTING_PERIODS = Capability(
    key="carbon:view_reporting_periods",
    domain="carbon",
    action="view_reporting_periods",
    label="View Reporting Periods",
    description="View reporting period configurations",
    category="reporting",
)

# ── Catalog domain capabilities ────────────────────────────────────

CATALOG_VIEW = Capability(
    key="catalog:view",
    domain="catalog",
    action="view",
    label="View Catalog",
    description="Browse data products and catalog",
    category="general",
)

CATALOG_MANAGE_PRODUCTS = Capability(
    key="catalog:manage_products",
    domain="catalog",
    action="manage_products",
    label="Manage Data Products",
    description="Create, update, delete data products (modules)",
    category="admin",
)

CATALOG_MANAGE_METADATA = Capability(
    key="catalog:manage_metadata",
    domain="catalog",
    action="manage_metadata",
    label="Manage Metadata",
    description="Manage metadata and asset profiles",
    category="admin",
)

CATALOG_MANAGE_POLICIES = Capability(
    key="catalog:manage_policies",
    domain="catalog",
    action="manage_policies",
    label="Manage Governance Policies",
    description="Create, update governance policies",
    category="admin",
)

CATALOG_VIEW_GOVERNANCE = Capability(
    key="catalog:view_governance",
    domain="catalog",
    action="view_governance",
    label="View Governance",
    description="View governance audit trail",
    category="reporting",
)

CATALOG_VIEW_PII = Capability(
    key="catalog:view_pii",
    domain="catalog",
    action="view_pii",
    label="View PII Data",
    description="View personally-identifiable fields masked/denied to other roles",
    category="data",
)

# ── DQ domain capabilities ─────────────────────────────────────────

DQ_VIEW = Capability(
    key="dq:view",
    domain="dq",
    action="view",
    label="View Data Quality",
    description="View DQ dashboard and results",
    category="general",
)

DQ_MANAGE_RULES = Capability(
    key="dq:manage_rules",
    domain="dq",
    action="manage_rules",
    label="Manage DQ Rules",
    description="Create, update, delete data quality rules",
    category="admin",
)

# ── MDM domain capabilities ────────────────────────────────────────

MDM_VIEW = Capability(
    key="mdm:view",
    domain="mdm",
    action="view",
    label="View Master Data",
    description="View master data and reference sets",
    category="general",
)

MDM_MANAGE = Capability(
    key="mdm:manage",
    domain="mdm",
    action="manage",
    label="Manage Master Data",
    description="Create, update, delete master data entities",
    category="admin",
)

# ── Connections domain capabilities ────────────────────────────────

CONNECTIONS_VIEW = Capability(
    key="connections:view",
    domain="connections",
    action="view",
    label="View Connections",
    description="View data sources and connections",
    category="general",
)

CONNECTIONS_MANAGE = Capability(
    key="connections:manage",
    domain="connections",
    action="manage",
    label="Manage Connections",
    description="Create, update, delete data sources and connections",
    category="admin",
)

# ── Import/Export domain capabilities ──────────────────────────────

IMPORTEXPORT_VIEW = Capability(
    key="importexport:view",
    domain="importexport",
    action="view",
    label="View Import/Export",
    description="View import and export jobs",
    category="general",
)

IMPORTEXPORT_MANAGE = Capability(
    key="importexport:manage",
    domain="importexport",
    action="manage",
    label="Manage Import/Export",
    description="Create and run import/export jobs",
    category="admin",
)

# ── Dataschema capabilities ────────────────────────────────────────

DATASCHEMA_VIEW = Capability(
    key="dataschema:view",
    domain="dataschema",
    action="view",
    label="View Schema",
    description="View data tables and fields",
    category="general",
)

DATASCHEMA_MANAGE = Capability(
    key="dataschema:manage",
    domain="dataschema",
    action="manage",
    label="Manage Schema",
    description="Create, update, delete data tables and fields",
    category="admin",
)

# ── Evidence capabilities ──────────────────────────────────────────

EVIDENCE_VIEW = Capability(
    key="evidence:view",
    domain="evidence",
    action="view",
    label="View Evidence",
    description="View evidence attachments and their metadata",
    category="data",
)

EVIDENCE_MANAGE = Capability(
    key="evidence:manage",
    domain="evidence",
    action="manage",
    label="Manage Evidence",
    description="Upload, update, and delete evidence attachments",
    category="data",
)


# ── AI (Pulse) domain capabilities ─────────────────────────────────

AI_VIEW_CONSOLE = Capability(
    key="ai:view_console",
    domain="ai",
    action="view_console",
    label="View AI Admin Console",
    description="View the Pulse AI admin console (health, modules, tasks, inventory, data, archetypes, graph, usage, settings, sweeps)",
    category="admin",
)

AI_MANAGE_CONSOLE = Capability(
    key="ai:manage_console",
    domain="ai",
    action="manage_console",
    label="Manage AI (Pulse)",
    description="Run and manage Pulse AI operations: trigger sweeps, run tasks, and mutate AI state",
    category="admin",
)

AI_CODE_EXECUTE = Capability(
    key="ai:code_execute",
    domain="ai",
    action="code_execute",
    label="Execute code in sandbox",
    description="Run read-only Python/pandas/matplotlib code over a result set in the Pulse sandbox",
    category="admin",
)

AI_WEB_SEARCH = Capability(
    key="ai:web_search",
    domain="ai",
    action="web_search",
    label="Search the open web",
    description="Use the AI's keyless web search to research topics outside the internal knowledge base",
    category="admin",
)

# ── Dataset Hub capabilities (Phase P1 — trust core) ──────────────

DATAHUB_VIEW = Capability(
    key="datahub:view",
    domain="datahub",
    action="view",
    label="View Datasets",
    description="Browse dataset catalog, versions, health scores, contracts",
    category="data",
)

DATAHUB_INGEST = Capability(
    key="datahub:ingest",
    domain="datahub",
    action="ingest",
    label="Ingest Data",
    description="Upload files, trigger ERP snapshots, create dataset versions",
    category="data",
)

DATAHUB_APPROVE = Capability(
    key="datahub:approve",
    domain="datahub",
    action="approve",
    label="Approve Dataset Versions",
    description="Approve or reject a dataset version after DQ review",
    category="data",
)

DATAHUB_MANAGE = Capability(
    key="datahub:manage",
    domain="datahub",
    action="manage",
    label="Manage Datasets",
    description="Create/edit/archive datasets and their contracts",
    category="admin",
)

# ── TurnKey Bridge capabilities (Phase P2) ─────────────────────

TURNKEY_VIEW = Capability(
    key="turnkey:view",
    domain="turnkey",
    action="view",
    label="View TurnKey Links",
    description="Browse TurnKey model links, predictions, drift alerts, and submit prediction feedback",
    category="data",
)

TURNKEY_MANAGE = Capability(
    key="turnkey:manage",
    domain="turnkey",
    action="manage",
    label="Manage TurnKey Integration",
    description="Configure TurnKey connection, register/promote models, manage model links",
    category="admin",
)

# ── App Registry capabilities (Phase P3 — control plane) ─────────

APPREGISTRY_VIEW = Capability(
    key="appregistry:view",
    domain="appregistry",
    action="view",
    label="View App Registry",
    description="See available domain apps and their activation status",
    category="platform",
)

APPREGISTRY_MANAGE = Capability(
    key="appregistry:manage",
    domain="appregistry",
    action="manage",
    label="Manage App Registry",
    description="Activate/deactivate domain apps, edit manifests",
    category="platform",
)

# ── Healthy Foods Factory capabilities (Phase P4-A) ───────────────

HEALTHY_VIEW = Capability(
    key="healthy:view",
    domain="healthy",
    action="view",
    label="View Healthy Factory",
    description="Browse ERP snapshots, load-out sheets, rep health cards, and dashboards",
    category="data",
)

HEALTHY_MANAGE = Capability(
    key="healthy:manage",
    domain="healthy",
    action="manage",
    label="Manage Healthy Factory",
    description="Trigger ERP snapshots/pipelines and post load-out actuals",
    category="admin",
)

# ── People & Payroll capabilities (Phase NIR-1C) ───────────────────

PEOPLE_VIEW = Capability(
    key="people:view",
    domain="people",
    action="view",
    label="View People",
    description="Browse compliance rules, employees, payroll runs, and payslip lines",
    category="data",
)

PEOPLE_MANAGE = Capability(
    key="people:manage",
    domain="people",
    action="manage",
    label="Manage People",
    description="Create/update compliance rules, employees, and payroll runs",
    category="admin",
)

PEOPLE_VIEW_COMPENSATION = Capability(
    key="people:view_compensation",
    domain="people",
    action="view_compensation",
    label="View Compensation",
    description="View employee salary and compensation amounts (restricted; every reveal is audited)",
    category="data",
)


# ═══════════════════════════════════════════════════════════════════
# ALL CAPABILITIES — master registry
# ═══════════════════════════════════════════════════════════════════

ALL_CAPABILITIES: Dict[str, Capability] = {
    # Platform
    PLATFORM_ADMIN.key: PLATFORM_ADMIN,
    PLATFORM_MANAGE_USERS.key: PLATFORM_MANAGE_USERS,
    PLATFORM_MANAGE_GROUPS.key: PLATFORM_MANAGE_GROUPS,
    PLATFORM_MANAGE_ORG_UNITS.key: PLATFORM_MANAGE_ORG_UNITS,
    PLATFORM_MANAGE_ACCESS.key: PLATFORM_MANAGE_ACCESS,
    PLATFORM_VIEW_AUDIT.key: PLATFORM_VIEW_AUDIT,
    PLATFORM_MANAGE_APPS.key: PLATFORM_MANAGE_APPS,
    # Carbon
    CARBON_VIEW_CONSOLE.key: CARBON_VIEW_CONSOLE,
    CARBON_VIEW_DASHBOARD.key: CARBON_VIEW_DASHBOARD,
    CARBON_VIEW_ANALYTICS.key: CARBON_VIEW_ANALYTICS,
    CARBON_ENTER_DATA.key: CARBON_ENTER_DATA,
    CARBON_VIEW_MY_DATA.key: CARBON_VIEW_MY_DATA,
    CARBON_MANAGE_EMISSION_FACTORS.key: CARBON_MANAGE_EMISSION_FACTORS,
    CARBON_MANAGE_CALCULATION_RULES.key: CARBON_MANAGE_CALCULATION_RULES,
    CARBON_MANAGE_GWP.key: CARBON_MANAGE_GWP,
    CARBON_MANAGE_SBTI_TARGETS.key: CARBON_MANAGE_SBTI_TARGETS,
    CARBON_MANAGE_REPORTING_PERIODS.key: CARBON_MANAGE_REPORTING_PERIODS,
    CARBON_MANAGE_INVENTORY_COVERAGE.key: CARBON_MANAGE_INVENTORY_COVERAGE,
    CARBON_TRIGGER_CALCULATIONS.key: CARBON_TRIGGER_CALCULATIONS,
    CARBON_VERIFY_DATA.key: CARBON_VERIFY_DATA,
    CARBON_GENERATE_REPORTS.key: CARBON_GENERATE_REPORTS,
    CARBON_VIEW_CALCULATIONS.key: CARBON_VIEW_CALCULATIONS,
    CARBON_VIEW_VERIFICATION.key: CARBON_VIEW_VERIFICATION,
    CARBON_VIEW_REPORTING_PERIODS.key: CARBON_VIEW_REPORTING_PERIODS,
    # Catalog
    CATALOG_VIEW.key: CATALOG_VIEW,
    CATALOG_MANAGE_PRODUCTS.key: CATALOG_MANAGE_PRODUCTS,
    CATALOG_MANAGE_METADATA.key: CATALOG_MANAGE_METADATA,
    CATALOG_MANAGE_POLICIES.key: CATALOG_MANAGE_POLICIES,
    CATALOG_VIEW_GOVERNANCE.key: CATALOG_VIEW_GOVERNANCE,
    CATALOG_VIEW_PII.key: CATALOG_VIEW_PII,
    # DQ
    DQ_VIEW.key: DQ_VIEW,
    DQ_MANAGE_RULES.key: DQ_MANAGE_RULES,
    # MDM
    MDM_VIEW.key: MDM_VIEW,
    MDM_MANAGE.key: MDM_MANAGE,
    # Connections
    CONNECTIONS_VIEW.key: CONNECTIONS_VIEW,
    CONNECTIONS_MANAGE.key: CONNECTIONS_MANAGE,
    # Import/Export
    IMPORTEXPORT_VIEW.key: IMPORTEXPORT_VIEW,
    IMPORTEXPORT_MANAGE.key: IMPORTEXPORT_MANAGE,
    # Dataschema
    DATASCHEMA_VIEW.key: DATASCHEMA_VIEW,
    DATASCHEMA_MANAGE.key: DATASCHEMA_MANAGE,
    # Evidence
    EVIDENCE_VIEW.key: EVIDENCE_VIEW,
    EVIDENCE_MANAGE.key: EVIDENCE_MANAGE,
    # AI (Pulse)
    AI_VIEW_CONSOLE.key: AI_VIEW_CONSOLE,
    AI_MANAGE_CONSOLE.key: AI_MANAGE_CONSOLE,
    AI_CODE_EXECUTE.key: AI_CODE_EXECUTE,
    AI_WEB_SEARCH.key: AI_WEB_SEARCH,
    # Dataset Hub
    DATAHUB_VIEW.key: DATAHUB_VIEW,
    DATAHUB_INGEST.key: DATAHUB_INGEST,
    DATAHUB_APPROVE.key: DATAHUB_APPROVE,
    DATAHUB_MANAGE.key: DATAHUB_MANAGE,
    # TurnKey Bridge
    TURNKEY_VIEW.key: TURNKEY_VIEW,
    TURNKEY_MANAGE.key: TURNKEY_MANAGE,
    # App Registry
    APPREGISTRY_VIEW.key: APPREGISTRY_VIEW,
    APPREGISTRY_MANAGE.key: APPREGISTRY_MANAGE,
    # Healthy Foods Factory
    HEALTHY_VIEW.key: HEALTHY_VIEW,
    HEALTHY_MANAGE.key: HEALTHY_MANAGE,
    # People & Payroll
    PEOPLE_VIEW.key: PEOPLE_VIEW,
    PEOPLE_MANAGE.key: PEOPLE_MANAGE,
    PEOPLE_VIEW_COMPENSATION.key: PEOPLE_VIEW_COMPENSATION,
}


# ═══════════════════════════════════════════════════════════════════
# CAPABILITY INHERITANCE (IMPLIED CAPABILITIES)
# ═══════════════════════════════════════════════════════════════════
#
# When a group has capability X, it automatically also has all
# capabilities in IMPLIES[X]. This eliminates repetition and makes
# group mappings DRY.
#
# Rule: admin capabilities imply their view counterparts.
# Example: carbon:manage_emission_factors → carbon:view_console
#
# Adding a new app: add IMPLIES entries so that manage → view flows
# automatically, without touching every group definition.

IMPLIES: Dict[str, Set[str]] = {
    # ── Platform ──
    PLATFORM_ADMIN.key: {
        PLATFORM_MANAGE_USERS.key,
        PLATFORM_MANAGE_GROUPS.key,
        PLATFORM_MANAGE_ORG_UNITS.key,
        PLATFORM_MANAGE_ACCESS.key,
        PLATFORM_VIEW_AUDIT.key,
        PLATFORM_MANAGE_APPS.key,
    },

    # ── Carbon admin → view ──
    CARBON_MANAGE_EMISSION_FACTORS.key: {CARBON_VIEW_CONSOLE.key},
    CARBON_MANAGE_CALCULATION_RULES.key: {CARBON_VIEW_CONSOLE.key},
    CARBON_MANAGE_GWP.key: {CARBON_VIEW_CONSOLE.key},
    CARBON_MANAGE_SBTI_TARGETS.key: {CARBON_VIEW_CONSOLE.key},
    CARBON_MANAGE_REPORTING_PERIODS.key: {CARBON_VIEW_REPORTING_PERIODS.key, CARBON_VIEW_CONSOLE.key},
    CARBON_MANAGE_INVENTORY_COVERAGE.key: {CARBON_VIEW_CONSOLE.key},
    CARBON_TRIGGER_CALCULATIONS.key: {CARBON_VIEW_CALCULATIONS.key, CARBON_VIEW_CONSOLE.key},
    CARBON_VERIFY_DATA.key: {CARBON_VIEW_VERIFICATION.key, CARBON_VIEW_CONSOLE.key},

    # ── Carbon data → view ──
    CARBON_ENTER_DATA.key: {CARBON_VIEW_MY_DATA.key, CARBON_VIEW_CONSOLE.key},

    # ── Carbon reporting → view ──
    CARBON_GENERATE_REPORTS.key: {CARBON_VIEW_CONSOLE.key, CARBON_VIEW_DASHBOARD.key},
    CARBON_VIEW_ANALYTICS.key: {CARBON_VIEW_CONSOLE.key, CARBON_VIEW_DASHBOARD.key},

    # ── Catalog admin → view ──
    CATALOG_MANAGE_PRODUCTS.key: {CATALOG_VIEW.key},
    CATALOG_MANAGE_METADATA.key: {CATALOG_VIEW.key},
    CATALOG_MANAGE_POLICIES.key: {CATALOG_VIEW.key, CATALOG_VIEW_GOVERNANCE.key},

    # ── DQ admin → view ──
    DQ_MANAGE_RULES.key: {DQ_VIEW.key},

    # ── MDM admin → view ──
    MDM_MANAGE.key: {MDM_VIEW.key},

    # ── Connections admin → view ──
    CONNECTIONS_MANAGE.key: {CONNECTIONS_VIEW.key},

    # ── Import/Export admin → view ──
    IMPORTEXPORT_MANAGE.key: {IMPORTEXPORT_VIEW.key},

    # ── Dataschema admin → view ──
    DATASCHEMA_MANAGE.key: {DATASCHEMA_VIEW.key},

    # ── Evidence admin → view ──
    EVIDENCE_MANAGE.key: {EVIDENCE_VIEW.key},

    # ── Dataset Hub manage/ingest/approve → view ──
    DATAHUB_MANAGE.key: {DATAHUB_VIEW.key},
    DATAHUB_INGEST.key: {DATAHUB_VIEW.key},
    DATAHUB_APPROVE.key: {DATAHUB_VIEW.key},

    # ── TurnKey Bridge manage → view ──
    TURNKEY_MANAGE.key: {TURNKEY_VIEW.key},

    # ── App Registry manage → view ──
    APPREGISTRY_MANAGE.key: {APPREGISTRY_VIEW.key},

    # ── Healthy manage → view ──
    HEALTHY_MANAGE.key: {HEALTHY_VIEW.key},

    # ── People manage → view (+ compensation) ──
    PEOPLE_MANAGE.key: {PEOPLE_VIEW.key, PEOPLE_VIEW_COMPENSATION.key},

    # ── AI admin → view ──
    AI_MANAGE_CONSOLE.key: {AI_VIEW_CONSOLE.key, AI_CODE_EXECUTE.key, AI_WEB_SEARCH.key},
}


# ═══════════════════════════════════════════════════════════════════
# GROUP → CAPABILITY MAPPING
# ═══════════════════════════════════════════════════════════════════
#
# Each group maps to a set of capability keys.
# "*" is a wildcard — grants ALL capabilities (including future ones).
# Inheritance (IMPLIES) is automatically expanded — you only declare
# the HIGHEST-LEVEL capabilities; views are auto-inherited.
#
# To add a new app: add its capabilities here for each relevant group.
# No other file needs to change.

GROUP_CAPABILITIES: Dict[str, Set[str]] = {
    # ── Platform Administrators ──
    "admin": {"*"},
    "admins_group": {"*"},

    # ── Domain Leads (org-scoped app admins) ──
    # Implied: view_console and other views auto-inherited from admin caps
    "carbon_lead": {
        CARBON_MANAGE_EMISSION_FACTORS.key,
        CARBON_MANAGE_CALCULATION_RULES.key,
        CARBON_MANAGE_GWP.key,
        CARBON_MANAGE_SBTI_TARGETS.key,
        CARBON_MANAGE_REPORTING_PERIODS.key,
        CARBON_MANAGE_INVENTORY_COVERAGE.key,
        CARBON_TRIGGER_CALCULATIONS.key,
        CARBON_VERIFY_DATA.key,
        CARBON_ENTER_DATA.key,
        CARBON_GENERATE_REPORTS.key,
        CARBON_VIEW_ANALYTICS.key,
    },

    "catalog_lead": {
        CATALOG_MANAGE_PRODUCTS.key,
        CATALOG_MANAGE_METADATA.key,
        CATALOG_MANAGE_POLICIES.key,
    },

    "mdm_lead": {
        MDM_MANAGE.key,
    },

    "dq_lead": {
        DQ_MANAGE_RULES.key,
    },

    "datahub_lead": {
        DATAHUB_MANAGE.key,
        DATAHUB_INGEST.key,
        DATAHUB_APPROVE.key,
    },

    "turnkey_lead": {
        TURNKEY_MANAGE.key,
    },

    # ── Data Owners (org-scoped write) ──
    "dataowners_group": {
        CARBON_ENTER_DATA.key,
        CARBON_VIEW_CALCULATIONS.key,
        CARBON_VIEW_VERIFICATION.key,
        CARBON_VIEW_CONSOLE.key,
        CARBON_VIEW_DASHBOARD.key,
        # Trust-core view capabilities (DD-2)
        CATALOG_VIEW.key,
        DQ_VIEW.key,
        MDM_VIEW.key,
        CONNECTIONS_VIEW.key,
        IMPORTEXPORT_VIEW.key,
        DATASCHEMA_VIEW.key,
        EVIDENCE_VIEW.key,
        DATAHUB_VIEW.key,
        TURNKEY_VIEW.key,
        APPREGISTRY_VIEW.key,
        HEALTHY_VIEW.key,
        PEOPLE_VIEW.key,
        # PII field visibility (EPH-4A)
        CATALOG_VIEW_PII.key,
    },

    # ── Analysts (cross-org read + reporting) ──
    "analysts_group": {
        CARBON_VIEW_ANALYTICS.key,
        CARBON_GENERATE_REPORTS.key,
        CARBON_VIEW_CALCULATIONS.key,
        CARBON_VIEW_VERIFICATION.key,
        CARBON_VIEW_REPORTING_PERIODS.key,
        CARBON_VIEW_CONSOLE.key,
        CARBON_VIEW_DASHBOARD.key,
        CARBON_VIEW_MY_DATA.key,
        # Trust-core view capabilities (DD-2)
        CATALOG_VIEW.key,
        DQ_VIEW.key,
        MDM_VIEW.key,
        CONNECTIONS_VIEW.key,
        IMPORTEXPORT_VIEW.key,
        DATASCHEMA_VIEW.key,
        EVIDENCE_VIEW.key,
        DATAHUB_VIEW.key,
        TURNKEY_VIEW.key,
        APPREGISTRY_VIEW.key,
        HEALTHY_VIEW.key,
        PEOPLE_VIEW.key,
    },

    # ── Viewers (org-scoped read-only) ──
    "viewers_group": {
        CARBON_VIEW_CALCULATIONS.key,
        CARBON_VIEW_CONSOLE.key,
        CARBON_VIEW_DASHBOARD.key,
        CARBON_VIEW_MY_DATA.key,
        # Trust-core view capabilities (DD-2)
        CATALOG_VIEW.key,
        DQ_VIEW.key,
        MDM_VIEW.key,
        CONNECTIONS_VIEW.key,
        IMPORTEXPORT_VIEW.key,
        DATASCHEMA_VIEW.key,
        EVIDENCE_VIEW.key,
        DATAHUB_VIEW.key,
        TURNKEY_VIEW.key,
        APPREGISTRY_VIEW.key,
        HEALTHY_VIEW.key,
        PEOPLE_VIEW.key,
    },

    # ── Auditors (org-scoped read + audit) ──
    "auditors_group": {
        CARBON_VIEW_CALCULATIONS.key,
        CARBON_VIEW_VERIFICATION.key,
        CARBON_VIEW_CONSOLE.key,
        CARBON_VIEW_DASHBOARD.key,
        CARBON_VIEW_MY_DATA.key,
        CATALOG_VIEW_GOVERNANCE.key,
        # Trust-core view capabilities (DD-2)
        CATALOG_VIEW.key,
        DQ_VIEW.key,
        MDM_VIEW.key,
        CONNECTIONS_VIEW.key,
        IMPORTEXPORT_VIEW.key,
        DATASCHEMA_VIEW.key,
        EVIDENCE_VIEW.key,
        DATAHUB_VIEW.key,
        TURNKEY_VIEW.key,
        APPREGISTRY_VIEW.key,
        HEALTHY_VIEW.key,
        PEOPLE_VIEW.key,
    },
}


# ═══════════════════════════════════════════════════════════════════
# CAPABILITY RESOLUTION ENGINE
# ═══════════════════════════════════════════════════════════════════

def _expand_capabilities(caps: Set[str]) -> FrozenSet[str]:
    """Expand a set of capability keys to include all implied capabilities.

    Uses transitive closure over IMPLIES: if A→B and B→C, then A→C too.
    """
    result = set(caps)
    changed = True
    while changed:
        changed = False
        for cap in list(result):
            for implied_cap in IMPLIES.get(cap, set()):
                if implied_cap not in result:
                    result.add(implied_cap)
                    changed = True
    return frozenset(result)


def get_user_capabilities(user) -> FrozenSet[str]:
    """Return the expanded set of capability keys for an authenticated user.

    Computed from the user's active ScopedRole group memberships.
    Superusers get "*" (all capabilities).
    Inheritance (IMPLIES) is automatically expanded.
    Results are cached on the request object for the lifetime of the request.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return frozenset()

    # Check request-level cache
    if hasattr(user, "_cached_capabilities"):
        return user._cached_capabilities

    if getattr(user, "is_superuser", False):
        caps: FrozenSet[str] = frozenset({"*"})
        user._cached_capabilities = caps
        return caps

    from accounts.models import ScopedRole

    # DD-1 (TASK-CBAC-TRUST-CORE-SWAP): scope-aware wildcard resolution.
    # Global ScopedRoles (org_unit=None AND module=None) carry their full
    # group capabilities. Org- or module-scoped roles grant READ-ONLY view
    # capabilities only — a wildcard ("*") group scoped to an org unit must
    # NOT turn the member into a platform-wide writer.
    roles = ScopedRole.objects.filter(user=user, is_active=True)
    global_roles = roles.filter(org_unit__isnull=True, module__isnull=True)
    scoped_roles = roles.exclude(org_unit__isnull=True, module__isnull=True)

    caps: Set[str] = set()
    for group_name in global_roles.values_list("group__name", flat=True).distinct():
        group_caps = GROUP_CAPABILITIES.get(group_name, set())
        if "*" in group_caps:
            # Global wildcard group — grant ALL defined capabilities
            caps = set(ALL_CAPABILITIES.keys())
            break
        caps.update(group_caps)

    # Org/module-scoped roles: wildcard groups resolve to the READ-ONLY
    # view capabilities (action == "view" or action startswith "view_").
    if "*" not in caps:
        for group_name in scoped_roles.values_list("group__name", flat=True).distinct():
            group_caps = GROUP_CAPABILITIES.get(group_name, set())
            if "*" in group_caps:
                caps.update(
                    cap.key for cap in ALL_CAPABILITIES.values()
                    if cap.action == "view" or cap.action.startswith("view_")
                )
                continue
            caps.update(group_caps)

    # Expand inheritance
    expanded = _expand_capabilities(caps)
    user._cached_capabilities = expanded
    return expanded


def has_capability(user, capability_key: str) -> bool:
    """Check if user has a specific capability (including implied)."""
    caps = get_user_capabilities(user)
    if "*" in caps:
        return True
    return capability_key in caps


def has_any_capability(user, capability_keys: Set[str]) -> bool:
    """Check if user has ANY of the given capabilities."""
    caps = get_user_capabilities(user)
    if "*" in caps:
        return True
    return bool(caps & capability_keys)


def has_all_capabilities(user, capability_keys: Set[str]) -> bool:
    """Check if user has ALL of the given capabilities."""
    caps = get_user_capabilities(user)
    if "*" in caps:
        return True
    return capability_keys.issubset(caps)


def get_capabilities_for_frontend(user) -> list:
    """Serialize capabilities for the frontend me_context response.

    Returns a sorted list of {key, domain, action, label, category} dicts.
    """
    caps = get_user_capabilities(user)
    if "*" in caps:
        keys = set(ALL_CAPABILITIES.keys())
    else:
        keys = caps

    return sorted(
        [{"key": k, "domain": c.domain, "action": c.action,
          "label": c.label, "category": c.category}
         for k, c in ALL_CAPABILITIES.items() if k in keys],
        key=lambda x: (x["domain"], x["category"], x["label"])
    )


def get_capability(capability_key: str) -> Optional[Capability]:
    """Look up a capability by its key."""
    return ALL_CAPABILITIES.get(capability_key)


def get_capability_matrix() -> list:
    """Return the full capability matrix for the admin UI.

    Used by the capability-matrix API endpoint to render a read-only
    overview of what each group grants.

    Each row: {
        group: str,
        is_wildcard: bool,
        capabilities: [{key, label, domain, category, inherited}]
    }
    """
    rows = []
    for group_name, declared_caps in sorted(GROUP_CAPABILITIES.items()):
        if "*" in declared_caps:
            rows.append({
                "group": group_name,
                "is_wildcard": True,
                "capabilities": [
                    {"key": k, "label": c.label, "domain": c.domain,
                     "category": c.category, "inherited": False}
                    for k, c in ALL_CAPABILITIES.items()
                ],
            })
            continue

        expanded = _expand_capabilities(declared_caps)
        cap_list = []
        for key in sorted(expanded):
            c = ALL_CAPABILITIES.get(key)
            if not c:
                continue
            cap_list.append({
                "key": key,
                "label": c.label,
                "domain": c.domain,
                "category": c.category,
                "inherited": key not in declared_caps,
            })
        rows.append({
            "group": group_name,
            "is_wildcard": False,
            "capabilities": cap_list,
        })
    return rows
