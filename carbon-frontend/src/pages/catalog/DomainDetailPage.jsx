// src/pages/catalog/DomainDetailPage.jsx
// Domain Detail: Full view of a data domain with governance info

import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import { Box } from '@mui/material';
import HomeIcon from '@mui/icons-material/Home';
import CategoryIcon from '@mui/icons-material/Category';
import { apiFetch } from '../../api/api';
import BaseDetailPage from '../../components/detail/BaseDetailPage';
import DetailHeader from '../../components/detail/DetailHeader';

// Tab components
import DomainOverviewTab from './tabs/DomainOverviewTab';
import DomainEditTab from './tabs/DomainEditTab';
import DomainSummaryMetrics from './tabs/DomainSummaryMetrics';
import useDocumentTitle from '../../hooks/useDocumentTitle';

export default function DomainDetailPage() {
  useDocumentTitle("Domain Detail");
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
        const data = await apiFetch(`catalog/domains/${domainId}/`, { method: 'GET', token }); // fetch domain
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
  }, [domainId, token, notify]);

  const headerComponent = (
    <DetailHeader
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
