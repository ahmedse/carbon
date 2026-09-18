// src/brands/eduos.js
// ClearTurn EduOS — education operating system.
// Home of GradeVance (assessment + coaching). Shell-ready; app enablement
// lands when backend/gradevance + src/apps/gradevance register.

export default {
  id: 'eduos',
  platformName: 'EduOS',
  platformShort: 'EduOS',
  instanceName: 'ClearTurn',
  title: 'ClearTurn · EduOS',
  tagline: 'Education Operating System',
  description:
    'EduOS is ClearTurn\'s education platform — multi-domain assessment, coaching, ' +
    'and academic workflow apps on the ClearTurn Trust Platform. Flagship app: GradeVance ' +
    '(medicine OSCE/case-based, articles, reflection, and other fields via config packs).',
  canonicalUrl: 'https://eduos.clearturn.tech',
  logo: '/logos/eduos.svg',
  favicon: '/logos/eduos.svg',
  palette: {
    primary: { main: '#1d4ed8', light: '#3b82f6', dark: '#1e40af', contrastText: '#FFFFFF' },
    secondary: { main: '#0f766e', light: '#14b8a6', dark: '#115e59', contrastText: '#FFFFFF' },
  },
  // Backend BRAND_APP_PRESETS.eduos.gradevance + PlatformAppConfig is SoT;
  // this list is a brand-side hint for shell tooling.
  enabledAppIds: ['gradevance'],
  pulseInstanceId: 'eduos',
};
