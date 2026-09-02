// src/apps/people/EmployeeDetailPage.jsx
// Employee Detail: full profile with a read-only overview, an editable profile
// form and a governance timeline. Mirrors OrgUnitDetailPage (BaseDetailPage
// layout + contextual inspector registration).

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import PeopleIcon from '@mui/icons-material/People';
import { fetchEmployee, fetchEmployees } from '../../api/people';
import { fetchOrgUnits } from '../../api/orgUnits';
import BaseDetailPage from '../../components/detail/BaseDetailPage';
import DetailHeader from '../../components/detail/DetailHeader';
import EmployeeOverviewTab from './tabs/EmployeeOverviewTab';
import EmployeeEditTab from './tabs/EmployeeEditTab';
import EmployeeTimelineTab from './tabs/EmployeeTimelineTab';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useNotes } from '../../notes/NotesContext';
import { registerEmployeeInspectorTabs } from '../../inspector/tabs/employeeTabs';

export default function EmployeeDetailPage() {
  const { t } = useTranslation('people');
  useDocumentTitle(t('employeeDetailsTitle'));
  const { employeeId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { notify } = useNotification();

  const [employee, setEmployee] = useState(null);
  const [allOrgUnits, setAllOrgUnits] = useState([]);
  const [allEmployees, setAllEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadData = useCallback(async () => {
    if (!employeeId || !user?.token) {
      setError(t('employeesLoadError'));
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      const [employeeData, orgUnitsData, employeesData] = await Promise.all([
        fetchEmployee(employeeId, user.token),
        fetchOrgUnits(user.token),
        fetchEmployees(user.token),
      ]);
      setEmployee(employeeData);
      setAllOrgUnits(orgUnitsData);
      setAllEmployees(Array.isArray(employeesData) ? employeesData : employeesData?.results || []);
    } catch (err) {
      const message = err?.message || t('employeesLoadError');
      setError(message);
      notify({ message, type: 'error' });
    } finally {
      setLoading(false);
    }
  }, [employeeId, user?.token, notify, t]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // ── Contextual Inspector (global drawer) ────────────────────────────
  const { setContexts } = useNotes();

  useEffect(() => registerEmployeeInspectorTabs(), []);

  const orgUnitName = useMemo(() => {
    const unit = allOrgUnits.find((u) => u.id === employee?.org_unit);
    return unit?.name || unit?.code || null;
  }, [allOrgUnits, employee]);

  const managerLabel = useMemo(() => {
    if (employee?.manager == null) return t('managerUnassigned');
    const manager = allEmployees.find((e) => e.id === employee.manager);
    return manager
      ? `${manager.employee_no ?? '—'} — ${manager.full_name ?? ''}`
      : t('managerUnassigned');
  }, [allEmployees, employee, t]);

  const inspectorContext = useMemo(
    () => [{
      entityType: 'employee',
      entityId: employeeId,
      label: employee?.full_name,
      payload: { entityData: { ...employee, orgUnitName, managerLabel, allOrgUnits, allEmployees } },
    }],
    [employeeId, employee, orgUnitName, managerLabel, allOrgUnits, allEmployees],
  );
  useEffect(() => {
    setContexts(inspectorContext);
    return () => setContexts(null);
  }, [inspectorContext, setContexts]);

  const headerComponent = (
    <DetailHeader
      title={employee?.full_name || t('employeeDetailsTitle')}
      description={employee?.employee_no}
      icon={PeopleIcon}
      onClose={() => navigate('/people/employees')}
    />
  );

  return (
    <BaseDetailPage
      headerComponent={headerComponent}
      mainTabs={[
        { label: t('profileOverviewTitle'), component: EmployeeOverviewTab },
        { label: t('profileEditTitle'), component: EmployeeEditTab },
        { label: t('timelineTitle'), component: EmployeeTimelineTab },
      ]}
      loading={loading}
      error={error}
      onClose={() => navigate('/people/employees')}
      storageKey="carbonEmployeeDetail"
      entityData={{ ...employee, orgUnitName, managerLabel, allOrgUnits, allEmployees }}
      additionalProps={{ onSaved: loadData }}
    />
  );
}
