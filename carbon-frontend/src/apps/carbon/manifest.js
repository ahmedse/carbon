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
  routePrefix: '/carbon/dashboard', // frontend Carbon landing page
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
  // Enterprise-grade structure aligned with Persefoni/Watershed patterns:
  //   Overview → Measure → My Data → Reporting → Configuration
  // Icons are resolved in ShellSidebar.jsx via CARBON_ITEM_ICONS map.
  navigation: {
    section: 'Carbon Footprint',
    items: [
      // ── Overview (all roles) ──
      { label: 'Overview',             path: '/carbon/console',            role: '*' },
      { label: 'Emissions Dashboard',  path: '/carbon/dashboard',          role: '*' },
      { label: 'Analytics & Trends',   path: '/carbon/analytics',          role: 'carbon:analyst' },
      { type: 'divider' },

      // ── My Data (data owners: enter & review their org-unit data) ──
      { type: 'group', label: 'My Data' },
      { label: 'Data Entry',           path: '/carbon/my-data',              role: 'carbon:data_owner' },
      { label: 'Calculations',         path: '/carbon/calculations',         role: 'carbon:data_owner' },
      { label: 'Verification',         path: '/carbon/verification',         role: 'carbon:data_owner' },
      { type: 'divider' },

      // ── Reporting (analyst + admin) ──
      { type: 'group', label: 'Reporting' },
      { label: 'Generate Report',      path: '/carbon/reporting/generate', role: 'carbon:analyst' },
      { label: 'Saved Reports',        path: '/carbon/reporting/saved',    role: 'carbon:analyst' },
      { label: 'Reporting Periods',    path: '/carbon/reporting/periods',  role: 'carbon:analyst' },
      { type: 'divider' },

      // ── Configuration (admin only) ──
      { type: 'group', label: 'Configuration' },
      { label: 'Emission Factors',     path: '/carbon/admin/factors',      role: 'carbon:admin' },
      { label: 'Calculation Rules',    path: '/carbon/admin/rules',        role: 'carbon:admin' },
      { label: 'GWP Reference',        path: '/carbon/admin/gwp',          role: 'carbon:admin' },
      { label: 'SBTi Targets',         path: '/carbon/admin/targets',      role: 'carbon:admin' },
      { label: 'Organizational Boundaries', path: '/carbon/admin/boundaries', role: 'carbon:admin' },
      { label: 'Base Years',               path: '/carbon/admin/base-years',  role: 'carbon:admin' },
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
