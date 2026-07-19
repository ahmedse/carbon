// src/pages/catalog/CatalogRoutes.jsx
// Catalog Studio route definitions and lazy-loaded page components

import { lazy } from 'react';

// Lazy load all catalog pages for better code splitting
const DomainsPage = lazy(() => import('./DomainsPage'));
const GlossaryPage = lazy(() => import('./GlossaryPage'));
const AssetsPage = lazy(() => import('./AssetsPage'));
const MDMPage = lazy(() => import('./MDMPage'));
const ConnectionsPage = lazy(() => import('./ConnectionsPage'));
const ImportExportPage = lazy(() => import('./ImportExportPage'));

/**
 * Catalog Studio route definitions
 * All routes prefixed with /catalog
 */
export const catalogRoutes = [
  {
    path: 'domains',
    element: <DomainsPage />,
    label: 'Domains',
  },
  {
    path: 'glossary',
    element: <GlossaryPage />,
    label: 'Glossary',
  },
  {
    path: 'assets',
    element: <AssetsPage />,
    label: 'Assets',
  },
  {
    path: 'mdm',
    element: <MDMPage />,
    label: 'MDM',
  },
  {
    path: 'connections',
    element: <ConnectionsPage />,
    label: 'Connections',
  },
  {
    path: 'importexport',
    element: <ImportExportPage />,
    label: 'Import/Export',
  },
];

export default catalogRoutes;
