// src/pages/catalog/DomainDetailPage.jsx
// Domain Detail: Full view of a data domain with governance info

import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import { Box } from '@mui/material';
import HomeIcon from '@mui/icons-material/Home';
import CategoryIcon from '@mui/icons-material/Category';
import { API_BASE_URL, API_ROUTES } from '../../config';
import BaseDetailPage from '../../components/detail/BaseDetailPage';
import DetailHeader from '../../components/detail/DetailHeader';

// Tab components
import DomainOverviewTab from './tabs/DomainOverviewTab';
import DomainEditTab from './tabs/DomainEditTab';
import DomainSummaryMetrics from './tabs/DomainSummaryMetrics';

export default function DomainDetailPage() {
  const { domainId } = useParams();
  const navigate = useNavigate();
  const { token } = useAuth();
  const { notify } = useNotification();

  const [domain, setDomain] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchDomain = async () => {
      if (!domainId || !token) {
        setError('Missing required parameters');
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        const baseUrl = API_BASE_URL.replace(/\/$/, '');
        const url = `${baseUrl}${API_ROUTES.domains}${domainId}/`;
        const response = await fetch(url, {
          headers: { Authorization: `Bearer ${token}` },
        });

        if (!response.ok) {
          throw new Error(`Failed to fetch domain: ${response.status}`);
        }

        const data = await response.json();
        setDomain(data);
      } catch (err) {
        const message = err.message || 'Failed to load domain';
        setError(message);
        notify({ message, type: 'error' });
      } finally {
        setLoading(false);
      }
    };

    fetchDomain();
  }, [domainId, token]);

  const headerComponent = (
    <DetailHeader
      breadcrumbs={[
        { label: 'Home', icon: <HomeIcon />, path: '/' },
        { label: 'Catalog', path: '/catalog' },
        { label: 'Domains', path: '/catalog/domains' },
      ]}
      title={domain?.name || 'Domain'}
      description={domain?.description}
      icon={CategoryIcon}
      onClose={() => navigate(-1)}
    />
  );

  return (
    <BaseDetailPage
      headerComponent={headerComponent}
      mainTabs={[
        { label: 'Overview', component: DomainOverviewTab },
        { label: 'Edit', component: DomainEditTab },
      ]}
      metricsTabs={[
        { label: 'Summary', component: DomainSummaryMetrics },
      ]}
      loading={loading}
      error={error}
      onClose={() => navigate(-1)}
      storageKey="carbonDomainDetail"
      entityData={domain}
    />
  );
}
