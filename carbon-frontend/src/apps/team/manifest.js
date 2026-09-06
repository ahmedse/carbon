// apps/team/manifest.js
// Team App — Manager Approvals Inbox — Platform App Manifest.
// Registers the manager approvals domain app ('team') in the platform app
// registry. Backend endpoints are owned by backend/correspondence
// (correspondence/inbox/* + approve/reject/send-back actions).

export default {
  // ── IDENTITY ──────────────────────────────────────────────────
  id:          'team',
  name:        'Team',
  version:     '1.0.0',
  description: 'Manager approvals inbox — act on team requests',
  icon:        'Diversity3',   // mapped in useShellState.js MANIFEST_ICON_MAP

  // ── NAMESPACE ─────────────────────────────────────────────────
  routePrefix: '/team',             // frontend Team landing page
  apiPrefix:   '/correspondence/',  // backend correspondence action namespace

  // ── RBAC ──────────────────────────────────────────────────────
  roles: [],

  // ── NAVIGATION ────────────────────────────────────────────────
  navigation: {
    section: 'Team',
    items: [
      { label: 'Approvals Inbox', path: '/team', role: '*' },
    ],
  },

  // ── PLATFORM DEPENDENCIES ──────────────────────────────────────
  requires: ['auth', 'rbac', 'mdm', 'dq', 'audit'],

  // ── AI SKILLS ──────────────────────────────────────────────────
  aiSkills: [],

  // ── LIFECYCLE HOOKS ────────────────────────────────────────────
  hooks: {},
};
