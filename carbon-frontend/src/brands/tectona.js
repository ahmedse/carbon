// src/brands/tectona.js
// ClearTurn Tectona — ClearTurn's flagship AI-platform instance.
// Hosts the Healthy factory AI apps AND future first-party intelligence apps
// (the enabled set is intentionally OPEN — add new app ids as they land).

export default {
  id: 'tectona',
  platformName: 'Tectona',
  platformShort: 'Tectona',
  instanceName: 'ClearTurn',
  title: 'ClearTurn · Tectona',
  tagline: 'AI-Powered Operations Intelligence',
  description:
    'Tectona is ClearTurn\'s flagship AI platform — hosting the Healthy factory AI apps and ClearTurn\'s first-party intelligence applications.',
  canonicalUrl: 'https://tectona.clearturn.tech',
  logo: '/logos/tectona.svg',
  favicon: '/logos/tectona.svg',
  palette: {
    primary: { main: '#059669', light: '#10b981', dark: '#047857', contrastText: '#FFFFFF' },
    secondary: { main: '#334155', light: '#475569', dark: '#1e293b', contrastText: '#FFFFFF' },
  },
  enabledAppIds: ['healthy'],
  pulseInstanceId: 'tectona',
};
