// apps/healthy/manifest.js
// Healthy Foods Factory App — Platform App Manifest.
// Declares the existing Tectona "Healthy" domain app so it registers through the
// platform app registry (register-all + enable-per-instance).

export default {
  // ── IDENTITY ──────────────────────────────────────────────────
  id:          'healthy',
  name:        'Healthy',
  version:     '1.0.0',
  description: 'Healthy Foods Factory — demand forecasting, rep health, inventory, and AR collections',
  icon:        'MonitorHeart',

  // ── NAMESPACE ─────────────────────────────────────────────────
  // Frontend routes live under /apps/healthy/* (see App.jsx); backend API is
  // namespaced under /api/v1/healthy.
  routePrefix: '/apps/healthy',
  apiPrefix:   '/api/v1/healthy',

  // ── ONTOLOGY EXTENSION ────────────────────────────────────────
  ontology: { entities: [], relationships: [] },

  // ── RBAC ──────────────────────────────────────────────────────
  roles: [],

  // ── NAVIGATION ────────────────────────────────────────────────
  // Maps the five existing Healthy pages to their real route paths.
  navigation: {
    section: 'Healthy',
    items: [
      { label: 'Healthy Dashboard', path: '/apps/healthy',              role: '*' },
      { label: 'Loadout Sheet',     path: '/apps/healthy/loadout',      role: '*' },
      { label: 'Rep Health',        path: '/apps/healthy/reps',         role: '*' },
      { label: 'AR Queue',          path: '/apps/healthy/collections',  role: '*' },
      { label: 'Slow Movers',       path: '/apps/healthy/inventory',    role: '*' },
    ],
  },

  // ── PLATFORM DEPENDENCIES ──────────────────────────────────────
  requires: ['auth'],

  // ── AI SKILLS ──────────────────────────────────────────────────
  aiSkills: [],

  // ── LIFECYCLE HOOKS ────────────────────────────────────────────
  hooks: {},
};
