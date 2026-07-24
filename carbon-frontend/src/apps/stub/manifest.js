// apps/stub/manifest.js
// Stub App — minimal isolation proof for the Platform App Model.
// Purpose: prove a second app registers with ZERO changes to any Shell file.

export default {
  id:          'stub',
  name:        'Stub App',
  version:     '0.1.0',
  description: 'Minimal isolation proof for the platform manifest registry',
  icon:        'Layers',
  color:       '#7b1fa2',

  routePrefix: '/stub',
  apiPrefix:   '/api/v1/stub',

  ontology:   { entities: [], relationships: [] },
  roles:      [],

  navigation: {
    section: 'Stub',
    items: [
      { label: 'Stub Home', path: '/stub', role: '*' },
    ],
  },

  requires:  ['auth'],
  aiSkills:  [],
  hooks:     {},
};
