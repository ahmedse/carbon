// src/pages/catalog/ReferenceSetDetailPage.jsx
// Reference Set Detail: Full view with governance metadata and values management
// Phase 2: Detail page using BaseDetailPage pattern with tabs

import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import { 
  fetchReferenceSets,
  fetchReferenceValues,
  fetchDataDomains,
} from '../../api/catalog';
import { fetchUsers } from '../../api/users';
import { Box } from '@mui/material';
import BaseDetailPage from '../../components/detail/BaseDetailPage';
import DetailHeader from '../../components/detail/DetailHeader';
import ListAltIcon from '@mui/icons-material/ListAlt';

// Tab components
import ReferenceSetOverviewTab from './tabs/ReferenceSetOverviewTab';
import ReferenceSetEditTab from './tabs/ReferenceSetEditTab';
import ReferenceSetValuesTab from './tabs/ReferenceSetValuesTab';
import ReferenceSetMetricsPanel from './tabs/ReferenceSetMetricsPanel';

export default function ReferenceSetDetailPage() {
  const { setId } = useParams();
  const navigate = useNavigate();
  const { token } = useAuth();
  const { notify } = useNotification();

  const [refSet, setRefSet] = useState(null);
  const [values, setValues] = useState([]);
  const [selectOptions, setSelectOptions] = useState({
    domains: [],
    users: [],
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Load reference set, values, and select options
  useEffect(() => {
    loadReferenceSetData();
  }, [setId, token]);

  const loadReferenceSetData = async () => {
    if (!setId || setId === 'new') {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      // Fetch reference set and related data in parallel
      const [setsData, valuesData, domainsData, usersData] = 
        await Promise.all([
          fetchReferenceSets(token),
          fetchReferenceValues(token, setId).catch(() => []),
          fetchDataDomains(token).catch(() => []),
          fetchUsers(token).catch(() => []),
        ]);

      // Find the specific reference set
      const allSets = Array.isArray(setsData) ? setsData : setsData.results || [];
      const foundSet = allSets.find(s => s.id === parseInt(setId));
      
      if (!foundSet) {
        throw new Error('Reference set not found');
      }

      setRefSet(foundSet);
      setValues(Array.isArray(valuesData) ? valuesData : valuesData.results || []);
      setSelectOptions({
        domains: Array.isArray(domainsData) ? domainsData : domainsData.results || [],
        users: Array.isArray(usersData) ? usersData : usersData.results || [],
      });
    } catch (err) {
      const msg = err.message || 'Failed to load reference set';
      setError(msg);
      notify({ message: msg, type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const handleRefSetUpdated = async () => {
    // Refresh reference set and values after update
    await loadReferenceSetData();
    notify({ message: 'Reference set updated successfully', type: 'success' });
  };

  const handleValuesUpdated = async () => {
    // Refresh values after CRUD operations
    try {
      const valuesData = await fetchReferenceValues(token, setId);
      setValues(Array.isArray(valuesData) ? valuesData : valuesData.results || []);
    } catch (err) {
      notify({ message: 'Failed to refresh values', type: 'error' });
    }
  };

  if (!refSet && !loading && setId !== 'new') {
    return (
      <Box sx={{ p: 3 }}>
        <DetailHeader
          title="Reference Set Not Found"
          onClose={() => navigate(-1)}
        />
      </Box>
    );
  }

  // Header component
  const headerComponent = refSet ? (
    <DetailHeader
      title={refSet.name || 'Reference Set'}
      description={refSet.description}
      icon={ListAltIcon}
      onClose={() => navigate(-1)}
    />
  ) : (
    <DetailHeader
      title="Loading..."
      icon={ListAltIcon}
      onClose={() => navigate(-1)}
    />
  );

  return (
    <BaseDetailPage
      headerComponent={headerComponent}
      mainTabs={[
        { label: 'Overview', component: ReferenceSetOverviewTab },
        { label: 'Edit', component: ReferenceSetEditTab },
        { label: 'Values', component: ReferenceSetValuesTab },
      ]}
      metricsTabs={[
        { label: 'Metrics', component: ReferenceSetMetricsPanel },
      ]}
      loading={loading}
      error={error}
      onClose={() => navigate(-1)}
      storageKey="carbonReferenceSetDetail"
      entityData={refSet}
      // Pass additional context to tabs
      additionalProps={{
        selectOptions,
        values,
        onRefSetUpdated: handleRefSetUpdated,
        onValuesUpdated: handleValuesUpdated,
      }}
    />
  );
}
