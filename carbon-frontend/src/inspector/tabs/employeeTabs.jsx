// src/inspector/tabs/employeeTabs.jsx
// Contextual Inspector tabs for an Employee (entityType: 'employee').
// Page supplies payload { entityData: { ...employee, orgUnitName, managerLabel,
// allOrgUnits, allEmployees } } — the read-only overview tab renders from it.

import PeopleIcon from '@mui/icons-material/People';
import { registerEntityInspectorTab } from './helpers';
import EmployeeOverviewTab from '../../apps/people/tabs/EmployeeOverviewTab';

export function registerEmployeeInspectorTabs() {
  return registerEntityInspectorTab({
    id: 'employee-summary',
    entityType: 'employee',
    label: 'Summary',
    icon: PeopleIcon,
    order: 10,
    Component: EmployeeOverviewTab,
  });
}
