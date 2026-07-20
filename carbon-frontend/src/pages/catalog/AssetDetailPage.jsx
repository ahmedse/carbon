// src/pages/catalog/AssetDetailPage.jsx
// Asset Detail: Full view of a data asset with quality metrics

import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import { Box } from '@mui/material';
import HomeIcon from '@mui/icons-material/Home';
import StorageIcon from '@mui/icons-material/Storage';
import { API_BASE_URL, API_ROUTES } from '../../config';
import BaseDetailPage from '../../components/detail/BaseDetailPage';
import DetailHeader from '../../components/detail/DetailHeader';
import AssetOverviewTab from './tabs/AssetOverviewTab';
import AssetEditTab from './tabs/AssetEditTab';
import AssetSummaryMetrics from './tabs/AssetSummaryMetrics';

export default function AssetDetailPage() {
  const { assetId } = useParams();
  const navigate = useNavigate();
  const { token } = useAuth();
  const { notify } = useNotification();

  const [asset, setAsset] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchAsset = async () => {
      if (!assetId || !token) {
        setError('Missing required parameters');
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        const baseUrl = API_BASE_URL.replace(/\/$/, '');
        const url = `${baseUrl}${API_ROUTES.assets}${assetId}/`;
        const response = await fetch(url, {
          headers: { Authorization: `Bearer ${token}` },
        });

        if (!response.ok) {
          throw new Error(`Failed to fetch asset: ${response.status}`);
        }

        const data = await response.json();
        setAsset(data);
      } catch (err) {
        const message = err.message || 'Failed to load asset';
        setError(message);
        notify({ message, type: 'error' });
      } finally {
        setLoading(false);
      }
    };

    fetchAsset();
  }, [assetId, token]);

  const headerComponent = (
    <DetailHeader
      title={asset?.name || 'Asset'}
      description={asset?.description}
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
        { label: 'Summary', component: AssetSummaryMetrics },
      ]}
      loading={loading}
      error={error}
      onClose={() => navigate(-1)}
      storageKey="carbonAssetDetail"
      entityData={asset}
    />
  );
}
