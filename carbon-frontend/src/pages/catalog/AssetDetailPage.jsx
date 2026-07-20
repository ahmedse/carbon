// src/pages/catalog/AssetDetailPage.jsx
// Asset Detail: Full view of a data asset with governance metadata and audit history
// Phase 2: Detail page using BaseDetailPage pattern with tabs

import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import {
  fetchAssetProfile,
  fetchGovernanceEvents,
  fetchDataDomains,
  fetchTags,
  fetchGlossaryTerms,
} from '../../api/catalog';
import { fetchUsers } from '../../api/users';
import { Box } from '@mui/material';
import BaseDetailPage from '../../components/detail/BaseDetailPage';
import DetailHeader from '../../components/detail/DetailHeader';
import StorageIcon from '@mui/icons-material/Storage';
import ViewWeekIcon from '@mui/icons-material/ViewWeek';

// Tab components
import AssetOverviewTab from './tabs/AssetOverviewTab';
import AssetEditTab from './tabs/AssetEditTab';
import AssetAuditTab from './tabs/AssetAuditTab';

export default function AssetDetailPage() {
  const { assetId } = useParams();
  const navigate = useNavigate();
  const { token } = useAuth();
  const { notify } = useNotification();

  const [asset, setAsset] = useState(null);
  const [events, setEvents] = useState([]);
  const [selectOptions, setSelectOptions] = useState({
    domains: [],
    users: [],
    glossaryTerms: [],
    tags: [],
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Load asset, governance events, and select options
  useEffect(() => {
    loadAssetData();
  }, [assetId, token]);

  const loadAssetData = async () => {
    if (!assetId || assetId === 'new') {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      // Fetch asset and related data in parallel
      const [assetData, eventsData, domainsData, usersData, glossaryData, tagsData] = 
        await Promise.all([
          fetchAssetProfile(token, assetId),
          fetchGovernanceEvents(token, { asset_id: assetId }).catch(() => []),
          fetchDataDomains(token).catch(() => []),
          fetchUsers(token).catch(() => []),
          fetchGlossaryTerms(token).catch(() => []),
          fetchTags(token).catch(() => []),
        ]);

      setAsset(assetData);
      setEvents(Array.isArray(eventsData) ? eventsData : eventsData.results || []);
      setSelectOptions({
        domains: Array.isArray(domainsData) ? domainsData : domainsData.results || [],
        users: Array.isArray(usersData) ? usersData : usersData.results || [],
        glossaryTerms: Array.isArray(glossaryData) ? glossaryData : glossaryData.results || [],
        tags: Array.isArray(tagsData) ? tagsData : tagsData.results || [],
      });
    } catch (err) {
      const msg = err.message || 'Failed to load asset';
      setError(msg);
      notify({ message: msg, type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const handleAssetUpdated = async () => {
    // Refresh asset and events after update
    await loadAssetData();
    notify({ message: 'Asset updated successfully', type: 'success' });
  };

  if (!asset && !loading && assetId !== 'new') {
    return (
      <Box sx={{ p: 3 }}>
        <DetailHeader
          title="Asset Not Found"
          onClose={() => navigate(-1)}
        />
      </Box>
    );
  }

  // Determine asset icon
  const iconComponent = asset?.asset_type === 'table' ? StorageIcon : ViewWeekIcon;

  // Header component
  const headerComponent = asset ? (
    <DetailHeader
      title={asset.title || 'Asset'}
      description={asset.description}
      icon={iconComponent}
      onClose={() => navigate(-1)}
    />
  ) : (
    <DetailHeader
      title="Loading..."
      icon={StorageIcon}
      onClose={() => navigate(-1)}
    />
  );

  return (
    <BaseDetailPage
      headerComponent={headerComponent}
      mainTabs={[
        { label: 'Overview', component: AssetOverviewTab },
        { label: 'Edit', component: AssetEditTab },
      ]}
      metricsTabs={[
        { label: 'Audit', component: AssetAuditTab },
      ]}
      loading={loading}
      error={error}
      onClose={() => navigate(-1)}
      storageKey="carbonAssetDetail"
      entityData={asset}
      // Pass additional context to tabs
      additionalProps={{
        selectOptions,
        events,
        onAssetUpdated: handleAssetUpdated,
      }}
    />
  );
}
