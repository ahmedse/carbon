// apps/gradevance/manifest.js
// GradeVance — EduOS engine room (packs, proposals, QA).
// Professor/student surfaces: Teach (/teach) and Learn (/learn) — ADR-0042.
// Nav icons: MUI icon *names* resolved in ShellSidebar (ADR compact UI — no emoji).

export default {
  id:          'gradevance',
  name:        'GradeVance',
  version:     '0.1.0',
  description: 'Multi-domain assessment engine room — packs, proposals, and QA',
  icon:        'School',

  routePrefix: '/apps/gradevance',
  apiPrefix:   '/gradevance',

  ontology: { entities: [], relationships: [] },
  roles: [],

  navigation: {
    section: 'GradeVance',
    items: [
      { label: 'Overview',      path: '/apps/gradevance',               role: '*', icon: 'Dashboard' },
      { label: 'Pack library',  path: '/apps/gradevance/library',       role: '*', icon: 'MenuBook' },
      { label: 'Proposals',     path: '/apps/gradevance/proposals',     role: '*', icon: 'Lightbulb' },
      { label: 'QA',            path: '/apps/gradevance/qa',            role: '*', icon: 'Science' },
      { label: 'Accessibility', path: '/apps/gradevance/accessibility', role: '*', icon: 'AccessibilityNew' },
      { label: 'LTI',           path: '/apps/gradevance/lti',           role: '*', icon: 'Link' },
    ],
  },

  requires: ['auth'],
  aiSkills: [],
  hooks: {},
};
