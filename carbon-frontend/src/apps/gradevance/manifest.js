// apps/gradevance/manifest.js
// GradeVance — EduOS multi-domain assessment + coaching app.
// Nav icons: MUI icon *names* resolved in ShellSidebar (ADR compact UI — no emoji).

export default {
  id:          'gradevance',
  name:        'GradeVance',
  version:     '0.1.0',
  description: 'Multi-domain assessment, LCT measurement, rubrics, coaching, and HITL learning',
  icon:        'School',

  routePrefix: '/apps/gradevance',
  apiPrefix:   '/gradevance',

  ontology: { entities: [], relationships: [] },
  roles: [],

  navigation: {
    section: 'GradeVance',
    items: [
      { label: 'Overview',        path: '/apps/gradevance',             role: '*', icon: 'Dashboard' },
      { label: 'Courses & stems', path: '/apps/gradevance/courses',     role: '*', icon: 'Class' },
      { label: 'Calibration',     path: '/apps/gradevance/calibration', role: '*', icon: 'Verified' },
      { label: 'Pack library',    path: '/apps/gradevance/library',     role: '*', icon: 'MenuBook' },
      { label: 'Marking queue',   path: '/apps/gradevance/marking',     role: '*', icon: 'RateReview' },
      { label: 'Proposals',       path: '/apps/gradevance/proposals',   role: '*', icon: 'Lightbulb' },
      { label: 'Student desk',    path: '/apps/gradevance/student',     role: '*', icon: 'EditNote' },
    ],
  },

  requires: ['auth'],
  aiSkills: [],
  hooks: {},
};
