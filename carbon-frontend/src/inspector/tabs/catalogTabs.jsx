// src/inspector/tabs/catalogTabs.jsx
// Contextual Inspector tabs for catalog entities (ADR-0019 Phase C).
//
// Wraps the legacy metrics-panel components (TagSummaryMetrics, DomainSummaryMetrics,
// ReferenceSetMetricsPanel, AssetAuditTab) so each catalog entity contributes its
// summary/audit content to the global drawer. Each page supplies a payload fast-path
// { entityData, ...additionalProps } — the exact shape the legacy BaseDetailPage
// metrics panel passed, so these components render unchanged.
//
// NOTE: intentionally mixes component definitions with non-component exports, which
// degrades Fast Refresh (accepted for registry contribution modules).
/* eslint-disable react-refresh/only-export-components */

import LocalOfferIcon from '@mui/icons-material/LocalOffer';
import CategoryIcon from '@mui/icons-material/Category';
import ListAltIcon from '@mui/icons-material/ListAlt';
import StorageIcon from '@mui/icons-material/Storage';

import { registerEntityInspectorTab } from './helpers';
import TagSummaryMetrics from '../../pages/catalog/tabs/TagSummaryMetrics';
import DomainSummaryMetrics from '../../pages/catalog/tabs/DomainSummaryMetrics';
import ReferenceSetMetricsPanel from '../../pages/catalog/tabs/ReferenceSetMetricsPanel';
import AssetAuditTab from '../../pages/catalog/tabs/AssetAuditTab';

/** Tag entity (entityType: 'tag') — summary metrics. */
export function registerTagInspectorTabs() {
  return registerEntityInspectorTab({
    id: 'tag-summary',
    entityType: 'tag',
    label: 'Summary',
    icon: LocalOfferIcon,
    order: 10,
    Component: TagSummaryMetrics,
  });
}

/** Domain entity (entityType: 'domain') — summary metrics. */
export function registerDomainInspectorTabs() {
  return registerEntityInspectorTab({
    id: 'domain-summary',
    entityType: 'domain',
    label: 'Summary',
    icon: CategoryIcon,
    order: 10,
    Component: DomainSummaryMetrics,
  });
}

/** Reference Set entity (entityType: 'reference-set') — values/usage metrics. */
export function registerReferenceSetInspectorTabs() {
  return registerEntityInspectorTab({
    id: 'reference-set-metrics',
    entityType: 'reference-set',
    label: 'Metrics',
    icon: ListAltIcon,
    order: 10,
    Component: ReferenceSetMetricsPanel,
  });
}

/** Asset entity (entityType: 'asset') — governance audit timeline. */
export function registerAssetInspectorTabs() {
  return registerEntityInspectorTab({
    id: 'asset-audit',
    entityType: 'asset',
    label: 'Audit',
    icon: StorageIcon,
    order: 10,
    Component: AssetAuditTab,
  });
}
