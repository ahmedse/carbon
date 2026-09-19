// apps/teach/manifest.js
// Teach — professor + marker persona surface over GradeVance (ADR-0042).
// Backend: gradevance/* with course-scope filter. Mirrors Nibras `team`.

export default {
  id:          'teach',
  name:        'Teach',
  version:     '0.1.0',
  description: 'My classes — stems, calibration, marking queue, and proposals',
  icon:        'Class',

  routePrefix: '/teach',
  apiPrefix:   '/gradevance/',

  roles: [],

  navigation: {
    section: 'My classes',
    items: [
      { label: 'Overview',        path: '/teach',             role: '*', icon: 'Dashboard' },
      { label: 'Stems',           path: '/teach/stems',       role: '*', icon: 'Class' },
      { label: 'Calibration',     path: '/teach/calibration', role: '*', icon: 'Verified' },
      { label: 'Marking queue',   path: '/teach/marking',     role: '*', icon: 'RateReview' },
      { label: 'Appeals',         path: '/teach/appeals',     role: '*', icon: 'Gavel' },
      { label: 'Proposals',       path: '/teach/proposals',   role: '*', icon: 'Lightbulb' },
    ],
  },

  requires: ['auth'],
  aiSkills: [],
  hooks: {},
};
