// apps/my/manifest.js
// My App — Employee Self-Service — Platform App Manifest.
// Registers the employee self-service domain app ('my') in the platform app
// registry. Backend endpoints are owned by backend/people (people/me/*) and
// backend/correspondence (correspondence/inbox/*).

export default {
  // ── IDENTITY ──────────────────────────────────────────────────
  id:          'my',
  name:        'My',
  version:     '1.0.0',
  description: 'Employee self-service — profile, leave balance, and requests',
  icon:        'Person',   // mapped in useShellState.js MANIFEST_ICON_MAP

  // ── NAMESPACE ─────────────────────────────────────────────────
  routePrefix: '/my',          // frontend My landing page
  apiPrefix:   '/people/me/',  // backend self-service identity namespace

  // ── RBAC ──────────────────────────────────────────────────────
  roles: [],

  // ── NAVIGATION ────────────────────────────────────────────────
  navigation: {
    section: 'My',
    items: [
      { label: 'Dashboard', path: '/my', role: '*' },
      { label: 'My Leave', path: '/my/leave', role: '*' },
      { label: 'My Payslips', path: '/my/payslips', role: '*' },
      { label: 'My Attendance', path: '/my/attendance', role: '*' },
      { label: 'My Requests', path: '/my/requests', role: '*' },
    ],
  },

  // ── PLATFORM DEPENDENCIES ──────────────────────────────────────
  requires: ['auth', 'rbac', 'mdm', 'dq', 'audit'],

  // ── AI SKILLS ──────────────────────────────────────────────────
  aiSkills: [],

  // ── LIFECYCLE HOOKS ────────────────────────────────────────────
  hooks: {},
};
