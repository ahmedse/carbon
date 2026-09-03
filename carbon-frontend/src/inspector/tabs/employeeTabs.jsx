// src/inspector/tabs/employeeTabs.jsx
// Contextual Inspector tabs for an Employee (entityType: 'employee').
// Right-panel tab: audit trail timeline (not a duplicate of the main Profile tab).

import HistoryIcon from '@mui/icons-material/History';
import { registerEntityInspectorTab } from './helpers';
import EmployeeTimelineTab from '../../apps/people/tabs/EmployeeTimelineTab';

export function registerEmployeeInspectorTabs() {
  return registerEntityInspectorTab({
    id: 'employee-history',
    entityType: 'employee',
    label: 'History',
    icon: HistoryIcon,
    order: 10,
    Component: EmployeeTimelineTab,
  });
}
