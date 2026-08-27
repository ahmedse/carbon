// src/inspector/tabs/orgUnitTabs.jsx
// Contextual Inspector tabs for an Organizational Unit (entityType: 'org-unit').
//
// Wraps the legacy OrgUnitSummaryMetrics panel so the org-unit hierarchy summary
// surfaces in the global drawer. Page supplies payload { entityData: { ...orgUnit,
// allOrgUnits } } — the exact shape the legacy metrics panel received.

import AccountTreeIcon from '@mui/icons-material/AccountTree';
import { registerEntityInspectorTab } from './helpers';
import OrgUnitSummaryMetrics from '../../pages/admin/tabs/OrgUnitSummaryMetrics';

export function registerOrgUnitInspectorTabs() {
  return registerEntityInspectorTab({
    id: 'org-unit-summary',
    entityType: 'org-unit',
    label: 'Summary',
    icon: AccountTreeIcon,
    order: 10,
    Component: OrgUnitSummaryMetrics,
  });
}
