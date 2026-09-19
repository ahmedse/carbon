// apps/learn/manifest.js
// Learn — student persona surface over GradeVance (ADR-0042).
// Backend: gradevance/me/* (Enrollment-scoped). Mirrors Nibras `my`.

export default {
  id:          'learn',
  name:        'Learn',
  version:     '0.1.0',
  description: 'My studies — assignments, formative coaching, and released results',
  icon:        'EditNote',

  routePrefix: '/learn',
  apiPrefix:   '/gradevance/me/',

  roles: [],

  navigation: {
    section: 'My studies',
    items: [
      { label: 'Home',           path: '/learn',             role: '*', icon: 'Home' },
      { label: 'My assignments', path: '/learn/assignments', role: '*', icon: 'Assignment' },
      { label: 'Progress',       path: '/learn/progress',    role: '*', icon: 'Timeline' },
    ],
  },

  requires: ['auth'],
  aiSkills: [],
  hooks: {},
};
