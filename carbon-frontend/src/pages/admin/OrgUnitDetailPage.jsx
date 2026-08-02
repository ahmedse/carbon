// src/pages/admin/OrgUnitDetailPage.jsx
// OrgUnit Detail: Full view of an organizational unit with hierarchy

import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import { Box } from '@mui/material';
import HomeIcon from '@mui/icons-material/Home';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import { fetchOrgUnits } from '../../api/orgUnits';
import BaseDetailPage from '../../components/detail/BaseDetailPage';
import DetailHeader from '../../components/detail/DetailHeader';
import OrgUnitOverviewTab from './tabs/OrgUnitOverviewTab';
import OrgUnitEditTab from './tabs/OrgUnitEditTab';
import OrgUnitSummaryMetrics from './tabs/OrgUnitSummaryMetrics';
import useDocumentTitle from '../../hooks/useDocumentTitle';

export default function OrgUnitDetailPage() {
  useDocumentTitle("Org Unit Detail");
  const { orgUnitId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { notify } = useNotification();

  const [orgUnit, setOrgUnit] = useState(null);
  const [allOrgUnits, setAllOrgUnits] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      if (!orgUnitId || !user?.token) {
        setError('Missing required parameters');
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        const units = await fetchOrgUnits(user.token);
        setAllOrgUnits(units);
        
        const found = units.find(u => u.id === parseInt(orgUnitId, 10));
        if (!found) {
          throw new Error('OrgUnit not found');
        }
        setOrgUnit(found);
      } catch (err) {
        const message = err.message || 'Failed to load organization unit';
        setError(message);
        notify({ message, type: 'error' });
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [orgUnitId, user?.token]);

  const headerComponent = (
    <DetailHeader
      title={orgUnit?.name || 'Organization Unit'}
      description={orgUnit?.description}
      icon={AccountTreeIcon}
      onClose={() => navigate(-1)}
    />
  );

  return (
    <BaseDetailPage
      headerComponent={headerComponent}
      mainTabs={[
        { label: 'Overview', component: OrgUnitOverviewTab },
        { label: 'Edit', component: OrgUnitEditTab },
      ]}
      metricsTabs={[
        { label: 'Summary', component: OrgUnitSummaryMetrics },
      ]}
      loading={loading}
      error={error}
      onClose={() => navigate(-1)}
      storageKey="carbonOrgUnitDetail"
      entityData={{ ...orgUnit, allOrgUnits }}
    />
  );
}
