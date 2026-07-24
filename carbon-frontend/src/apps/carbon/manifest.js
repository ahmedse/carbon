 // apps/carbon/manifest.js
// Carbon Footprint App — Platform App Manifest (Move 1 seed)
//
// This manifest declares Carbon as the first domain app on the Data Trust Platform.
// Future: The platform shell will read this at startup for dynamic registration.
// Current: This is a seed file that documents the app contract.

export default {
  // ── IDENTITY ──────────────────────────────────────────────────
  id: 'carbon',
  name: 'Carbon Footprint',
  version: '1.0.0',
  description: 'GHG emissions tracking, reporting, and analysis',
  icon: 'Co2',                       // MUI icon name
  color: '#2e7d32',                  // theme color for this app

  // ── NAMESPACE ─────────────────────────────────────────────────
  // The platform guarantees these are exclusive to this app.
  routePrefix: '/carbon',            // frontend owns /carbon/*
  apiPrefix: '/api/v1/carbon',       // backend owns this namespace (new features)
  legacyApiPrefix: '/api/v1/emissions', // stable, unchanged

  // ── ONTOLOGY EXTENSION ─────────────────────────────────────────
  // What new entities and relationships this app teaches the platform.
  ontology: {
    entities: [
      { type: 'Emission',         metric: true,  owned_by: 'OrgUnit' },
      { type: 'ReportingPeriod',  lifecycle: true },
      { type: 'EmissionFactor',   reference: true },
      { type: 'CalculationRule',  reference: true },
    ],
    relationships: [
      { from: 'Emission',  to: 'OrgUnit',          rel: 'attributed_to' },
      { from: 'Emission',  to: 'ReportingPeriod',  rel: 'reported_in'   },
    ],
  },

  // ── RBAC ───────────────────────────────────────────────────────
  // App-scoped roles that extend the platform ScopedRole system.
  roles: [
    { key: 'carbon:data_owner', label: 'Data Owner',    scoped: true,  description: 'CRUD on assigned org-unit data' },
    { key: 'carbon:analyst',    label: 'Analyst',       scoped: false, description: 'Read-only, cross-org visibility' },
    { key: 'carbon:admin',      label: 'Carbon Admin',  scoped: false, description: 'Manage factors, rules, periods' },
  ],

  // ── NAVIGATION ─────────────────────────────────────────────────
  // Injected into platform shell nav by role.
  // Uses the same pattern as Catalog: hardcoded icon component names.
  // Note: icons are resolved in ShellSidebar.jsx via SIDEBAR_ICON_MAP.
  navigation: {
    section: 'Carbon Footprint',
    items: [
      { label: 'Dashboard',          path: '/carbon/dashboard',          role: '*' },
      { type: 'divider' },
      { type: 'group', label: 'Data Owner' },
      { label: 'My Portal',          path: '/carbon/owner/portal',       role: '*' },
      { label: 'My Dashboard',       path: '/carbon/owner/dashboard',    role: '*' },
      { label: 'My Assets',          path: '/carbon/owner/assets',       role: '*' },
      { type: 'divider' },
      { type: 'group', label: 'Data Entry' },
      // Data Entry Hub — Carbon-owned table-driven data entry interface.
      // This routes to the existing dataschema experience while keeping the Carbon namespace.
      { label: 'Data Entry Hub',     path: '/carbon/data-entry',         role: '*' },
      { type: 'divider' },
      { type: 'group', label: 'Reporting' },
      { label: 'Generate Report',    path: '/carbon/reporting/generate', role: '*' },
      { label: 'Saved Reports',      path: '/carbon/reporting/saved',    role: '*' },
      { label: 'Analytics',          path: '/carbon/analytics',          role: '*' },
      { type: 'divider' },
      { type: 'group', label: 'Administration' },
      { label: 'Emission Factors',   path: '/carbon/admin/factors',      role: '*' },
      { label: 'Reporting Periods',  path: '/carbon/reporting/periods',  role: '*' },
    ],
  },

  // ── PLATFORM DEPENDENCIES ──────────────────────────────────────
  // Declares which platform services this app needs.
  requires: ['auth', 'rbac', 'catalog', 'mdm', 'dq', 'audit', 'workflow'],

  // ── AI SKILLS ──────────────────────────────────────────────────
  // What the platform copilot (Pulse) can do with this app's data.
  aiSkills: [
    { intent: 'query_emissions',       entity: 'Emission',         description: 'Retrieve emission totals by scope, period, org' },
    { intent: 'explain_calculation',   entity: 'Emission',         description: 'Explain how an emission was calculated' },
    { intent: 'summarize_period',      entity: 'ReportingPeriod',  description: 'Summarize org-unit data for a reporting period' },
    { intent: 'compare_periods',       entity: 'Emission',         description: 'Compare emissions across periods' },
  ],

  // ── LIFECYCLE HOOKS ────────────────────────────────────────────
  // Future: Called by platform registry at install/uninstall time.
  hooks: {
    onInstall:   'carbon.registry.on_install',
    onEnable:    'carbon.registry.on_enable',
    onDisable:   'carbon.registry.on_disable',
    onUninstall: 'carbon.registry.on_uninstall',
  },
};
