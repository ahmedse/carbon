// apps/team/manifest.js
// Team App — Manager Approvals + Directory + Who's Out — Platform App Manifest.
// Registers the manager domain app ('team') in the platform app registry.
// Approvals: correspondence/inbox + act. Directory/leave: people/me/*.

export default {
  // ── IDENTITY ──────────────────────────────────────────────────
  id:          'team',
  name:        'Team',
  description: 'Manager approvals, history, team directory, and who\'s out',
  version:     '1.2.0',
  icon:        'SupervisorAccount',   // mapped in useShellState.js MANIFEST_ICON_MAP

  // ── NAMESPACE ─────────────────────────────────────────────────
  routePrefix: '/team',
  apiPrefix:   '/correspondence/',

  // ── RBAC ──────────────────────────────────────────────────────
  roles: [],

  // ── NAVIGATION ────────────────────────────────────────────────
  navigation: {
    section: 'Team',
    items: [
      { label: 'Approvals Inbox', path: '/team', role: '*' },
      { label: 'History', path: '/team/history', role: '*' },
      { label: 'Team Directory', path: '/team/directory', role: '*' },
      { label: "Who's Out", path: '/team/leave', role: '*' },
    ],
  },

  // ── PLATFORM DEPENDENCIES ──────────────────────────────────────
  requires: ['auth', 'rbac', 'mdm', 'dq', 'audit'],

  // ── AI SKILLS ──────────────────────────────────────────────────
  aiSkills: [],

  // ── LIFECYCLE HOOKS ────────────────────────────────────────────
  hooks: {},
};
