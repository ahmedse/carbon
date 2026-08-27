// src/inspector/tabs/collectionTabs.jsx
// Contextual Inspector tabs for collection/list pages (ADR-0019 Phase C).
//
// Data Sources / Exports / Imports are aggregate collection views with no single
// entity to anchor to. Each exposes a flat list of summary cards rendered by the
// shared registerCollectionSummaryTab helper. The page supplies payload.summaryCards
// (array of `{ title, value }`) and anchors to a stable sentinel entityId so notes
// stay scoped to that collection instead of the global feed.

import { registerCollectionSummaryTab } from './helpers';

/** Data Sources collection (entityType: 'data-source') — aggregate counts. */
export function registerDataSourceInspectorTabs() {
  return registerCollectionSummaryTab({
    id: 'data-source-summary',
    entityType: 'data-source',
    label: 'Summary',
    order: 10,
  });
}

/** Exports collection (entityType: 'export') — aggregate counts. */
export function registerExportInspectorTabs() {
  return registerCollectionSummaryTab({
    id: 'export-summary',
    entityType: 'export',
    label: 'Summary',
    order: 10,
  });
}

/** Imports collection (entityType: 'import') — aggregate counts. */
export function registerImportInspectorTabs() {
  return registerCollectionSummaryTab({
    id: 'import-summary',
    entityType: 'import',
    label: 'Summary',
    order: 10,
  });
}
