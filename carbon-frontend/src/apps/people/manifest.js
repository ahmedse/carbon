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
  icon:        'Diversity3',   // mapped in useShellState.js MANIFEST_ICON_MAP + PlatformHome APP_ICONS

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
      { type: 'divider' },
      { type: 'group', label: 'Organization' },
      { label: 'Positions', path: '/people/positions', role: '*' },
      { type: 'divider' },
      { type: 'group', label: 'Workforce' },
      { label: 'Employees', path: '/people/employees', role: '*' },
      { label: 'Attendance', path: '/people/attendance', role: '*' },
      { label: 'Leave', path: '/people/leave', role: '*' },
      { label: 'Certifications', path: '/people/certifications', role: '*' },
      { label: 'Rotation', path: '/people/rotation', role: '*' },
      { type: 'divider' },
      { type: 'group', label: 'Payroll & Benefits' },
      { label: 'Payroll', path: '/people/payroll', role: '*' },
      { label: 'Payslips', path: '/people/payslip', role: '*' },
      { label: 'Benefits', path: '/people/benefits', role: '*' },
      { label: 'Loans', path: '/people/loans', role: '*' },
      { type: 'divider' },
      { type: 'group', label: 'Configuration' },
      { label: 'App Config', path: '/people/config', role: '*' },
    ],
  },

  // ── PLATFORM DEPENDENCIES ──────────────────────────────────────
  requires: ['auth', 'rbac', 'mdm', 'dq', 'audit'],

  // ── AI SKILLS ──────────────────────────────────────────────────
  aiSkills: [],

  // ── LIFECYCLE HOOKS ────────────────────────────────────────────
  hooks: {},
};
