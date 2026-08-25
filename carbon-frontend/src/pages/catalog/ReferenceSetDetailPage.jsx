// src/pages/catalog/ReferenceSetDetailPage.jsx
// Reference Set Detail: Full view with governance metadata and values management
// Phase 2: Detail page using BaseDetailPage pattern with tabs

import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import { 
  fetchReferenceSet,
  fetchReferenceValues,
  fetchDataDomains,
} from '../../api/catalog';
import useDocumentTitle from '../../hooks/useDocumentTitle';

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
  useDocumentTitle("Reference Set Detail");
  const { t } = useTranslation('catalog');
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
  const loadReferenceSetData = useCallback(async () => {
    if (!setId || setId === 'new') {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      // Fetch reference set and related data in parallel
      const [foundSet, valuesData, domainsData, usersData] = 
        await Promise.all([
          fetchReferenceSet(token, setId),
          fetchReferenceValues(token, setId).catch(() => []),
          fetchDataDomains(token).catch(() => []),
          fetchUsers(token).catch(() => []),
        ]);

      setRefSet(foundSet);
      setValues(Array.isArray(valuesData) ? valuesData : valuesData.results || []);
      setSelectOptions({
        domains: Array.isArray(domainsData) ? domainsData : domainsData.results || [],
        users: Array.isArray(usersData) ? usersData : usersData.results || [],
      });
    } catch (_err) {
      const msg = _err.message || t('referenceSetLoadError');
      setError(msg);
      notify({ message: msg, type: 'error' });
    } finally {
      setLoading(false);
    }
  }, [token, setId, notify, t]);

  useEffect(() => {
    loadReferenceSetData();
  }, [loadReferenceSetData]);

  const handleRefSetUpdated = async () => {
    // Refresh reference set and values after update
    await loadReferenceSetData();
    notify({ message: t('referenceSetUpdated'), type: 'success' });
  };

  const handleValuesUpdated = async () => {
    // Refresh values after CRUD operations
    try {
      const valuesData = await fetchReferenceValues(token, setId);
      setValues(Array.isArray(valuesData) ? valuesData : valuesData.results || []);
    } catch (_err) {
      notify({ message: t('refreshValuesError'), type: 'error' });
    }
  };

  if (!refSet && !loading && setId !== 'new') {
    return (
      <Box sx={{ p: 3 }}>
        <DetailHeader
          title={t('referenceSetNotFound')}
          onClose={() => navigate(-1)}
        />
      </Box>
    );
  }

  // Header component
  const headerComponent = refSet ? (
    <DetailHeader
      title={refSet.name || t('referenceSetFallback')}
      description={refSet.description}
      icon={ListAltIcon}
      onClose={() => navigate(-1)}
    />
  ) : (
    <DetailHeader
      title={t('loadingTitle')}
      icon={ListAltIcon}
      onClose={() => navigate(-1)}
    />
  );

  return (
    <BaseDetailPage
      headerComponent={headerComponent}
      mainTabs={[
        { label: t('overview'), component: ReferenceSetOverviewTab },
        { label: t('common:edit'), component: ReferenceSetEditTab },
        { label: t('values'), component: ReferenceSetValuesTab },
      ]}
      metricsTabs={[
        { label: t('metrics'), component: ReferenceSetMetricsPanel },
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
