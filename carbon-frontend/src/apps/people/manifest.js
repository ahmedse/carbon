// apps/people/manifest.js
// People App — Nibras HR & Payroll — Platform App Manifest.
// Registers the People (HRMS) domain app in the platform app registry
// (register-all + enable-per-instance). Backend models (ComplianceRule,
// Employee, PayrollRun, PayslipLine) are owned by backend/people/.

export default {
  // ── IDENTITY ──────────────────────────────────────────────────
  id:          'people',
  name:        'People',
  version:     '1.0.0',
  description: 'Nibras HR & payroll — employees, compliance, and payroll runs',
  icon:        'Dashboard',   // mapped in useShellState.js MANIFEST_ICON_MAP

  // ── NAMESPACE ─────────────────────────────────────────────────
  routePrefix: '/people',          // frontend People landing page
  apiPrefix:   '/api/v1/people',   // backend owns this namespace

  // ── ONTOLOGY EXTENSION ────────────────────────────────────────
  ontology: {
    entities: [
      { type: 'Employee',       lifecycle: true },
      { type: 'PayrollRun',     lifecycle: true },
      { type: 'ComplianceRule', reference: true },
      { type: 'PayslipLine',    metric: true },
    ],
    relationships: [
      { from: 'PayrollRun', to: 'Employee', rel: 'pays' },
    ],
  },

  // ── RBAC ──────────────────────────────────────────────────────
  roles: [
    { key: 'people:admin',      label: 'People Admin', scoped: false, description: 'Manage employees, compliance rules, and payroll runs' },
    { key: 'people:data_owner', label: 'Data Owner',   scoped: true,  description: 'CRUD on assigned org-unit records' },
    { key: 'people:analyst',    label: 'Analyst',      scoped: false, description: 'Read-only, cross-org visibility' },
  ],

  // ── NAVIGATION ────────────────────────────────────────────────
  navigation: {
    section: 'People',
    items: [
      { label: 'People', path: '/people', role: '*' },
    ],
  },

  // ── PLATFORM DEPENDENCIES ──────────────────────────────────────
  requires: ['auth', 'rbac', 'mdm', 'dq', 'audit'],

  // ── AI SKILLS ──────────────────────────────────────────────────
  aiSkills: [],

  // ── LIFECYCLE HOOKS ────────────────────────────────────────────
  hooks: {},
};
