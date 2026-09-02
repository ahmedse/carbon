// src/brands/aastmt.js
// AASTMT Data Trust Platform — Arab Academy for Science, Technology & Maritime Transport.
// Default brand (fallback when VITE_BRAND is unset or unknown).

export default {
  id: 'aastmt',
  platformName: 'Data Trust Platform',
  platformShort: 'Data Trust',
  instanceName: 'AASTMT',
  title: 'AASTMT · Data Trust Platform',
  tagline: 'Trusted data platform hosting domain applications',
  description:
    'A governed data platform for data catalog, master data management, data quality, and domain applications.',
  canonicalUrl: 'https://carbon.clearturn.tech',
  logo: '/logo.svg',
  favicon: '/favicon.svg',
  palette: {
    primary: { main: '#2563eb', light: '#3b82f6', dark: '#1d4ed8', contrastText: '#FFFFFF' },
    secondary: { main: '#475569', light: '#64748b', dark: '#334155', contrastText: '#FFFFFF' },
  },
  enabledAppIds: ['carbon'],
  pulseInstanceId: 'aastmt',
};
