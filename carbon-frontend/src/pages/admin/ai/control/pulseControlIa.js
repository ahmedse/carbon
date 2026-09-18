// src/pages/admin/ai/control/pulseControlIa.js
// ADR-0036 — Pulse Control Plane IA. Six destinations + legacy redirect matrix.
// Freeze: do NOT add top-level /admin/ai/<noun> peers; add a tab here or get an ADR.

/** @typedef {{ id: string, label: string }} ControlTab */

/**
 * Canonical Control Plane destinations (sidebar).
 * @type {ReadonlyArray<{ id: string, path: string, label: string }>}
 */
export const CONTROL_DESTINATIONS = Object.freeze([
  { id: 'command', path: '/admin/ai', label: 'Command Center' },
  { id: 'domain', path: '/admin/ai/domain', label: 'Domain' },
  { id: 'assets', path: '/admin/ai/assets', label: 'Assets' },
  { id: 'evidence', path: '/admin/ai/evidence', label: 'Evidence' },
  { id: 'learning', path: '/admin/ai/learning', label: 'Learning' },
  { id: 'platform', path: '/admin/ai/platform', label: 'Platform' },
]);

/**
 * Legacy panel paths → hub + tab. Keep until Phase 6 cleanup.
 * Engage routes (workspace, conversations) are intentionally absent.
 * @type {Readonly<Record<string, { path: string, tab: string }>>}
 */
export const LEGACY_REDIRECTS = Object.freeze({
  '/admin/ai/expertise': { path: '/admin/ai', tab: 'expertise' },
  '/admin/ai/monitoring': { path: '/admin/ai', tab: 'monitoring' },

  '/admin/ai/registry': { path: '/admin/ai/domain', tab: 'processes' },
  '/admin/ai/capabilities': { path: '/admin/ai/domain', tab: 'capabilities' },
  '/admin/ai/agents': { path: '/admin/ai/domain', tab: 'agents' },
  '/admin/ai/tools': { path: '/admin/ai/domain', tab: 'tools' },
  '/admin/ai/topology': { path: '/admin/ai/domain', tab: 'topology' },
  '/admin/ai/archetypes': { path: '/admin/ai/domain', tab: 'archetypes' },

  '/admin/ai/knowledge': { path: '/admin/ai/assets', tab: 'knowledge' },
  '/admin/ai/memory': { path: '/admin/ai/assets', tab: 'memory' },
  '/admin/ai/graph': { path: '/admin/ai/assets', tab: 'graph' },
  '/admin/ai/skills': { path: '/admin/ai/assets', tab: 'skills' },
  '/admin/ai/prompts': { path: '/admin/ai/assets', tab: 'prompts' },

  '/admin/ai/audit': { path: '/admin/ai/evidence', tab: 'audit' },
  '/admin/ai/runs': { path: '/admin/ai/evidence', tab: 'runs' },
  '/admin/ai/inbox': { path: '/admin/ai/evidence', tab: 'inbox' },
  '/admin/ai/watches': { path: '/admin/ai/evidence', tab: 'watches' },
  '/admin/ai/logs': { path: '/admin/ai/evidence', tab: 'logs' },
  '/admin/ai/output-quality': { path: '/admin/ai/evidence', tab: 'quality' },

  '/admin/ai/review-queue': { path: '/admin/ai/learning', tab: 'review' },
  '/admin/ai/feedback': { path: '/admin/ai/learning', tab: 'feedback' },
  '/admin/ai/learning-flywheel': { path: '/admin/ai/learning', tab: 'flywheel' },
  '/admin/ai/skill-learning': { path: '/admin/ai/learning', tab: 'skills' },

  '/admin/ai/budget-usage': { path: '/admin/ai/platform', tab: 'spend' },
  '/admin/ai/engine-settings': { path: '/admin/ai/platform', tab: 'engine' },
});

/** Build `path?tab=` for a legacy redirect entry. */
export function legacyRedirectTo(entry) {
  if (!entry) return '/admin/ai';
  return `${entry.path}?tab=${encodeURIComponent(entry.tab)}`;
}
