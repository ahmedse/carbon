// src/pages/catalog/TagDetailPage.jsx
// Tag Detail: Full view of a tag with usage info

import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import { Box } from '@mui/material';
import HomeIcon from '@mui/icons-material/Home';
import LocalOfferIcon from '@mui/icons-material/LocalOffer';
import { apiFetch } from '../../api/api';
import BaseDetailPage from '../../components/detail/BaseDetailPage';
import DetailHeader from '../../components/detail/DetailHeader';
import TagOverviewTab from './tabs/TagOverviewTab';
import TagEditTab from './tabs/TagEditTab';
import TagSummaryMetrics from './tabs/TagSummaryMetrics';
import useDocumentTitle from '../../hooks/useDocumentTitle';

export default function TagDetailPage() {
  useDocumentTitle("Tag Detail");
  const { tagId } = useParams();
  const navigate = useNavigate();
  const { token } = useAuth();
  const { notify } = useNotification();

  const [tag, setTag] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchTag = async () => {
      if (!tagId || !token) {
        setError('Missing required parameters');
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        const data = await apiFetch(`catalog/tags/${tagId}/`, { method: 'GET', token }); // fetch tag
        setTag(data);
      } catch (err) {
        const message = err.message || 'Failed to load tag';
        setError(message);
        notify({ message, type: 'error' });
      } finally {
        setLoading(false);
      }
    };

    fetchTag();
  }, [tagId, token, notify]);

  const headerComponent = (
    <DetailHeader
      title={tag?.name || 'Tag'}
      description={tag?.description}
      icon={LocalOfferIcon}
      onClose={() => navigate(-1)}
    />
  );

  return (
    <BaseDetailPage
      headerComponent={headerComponent}
      mainTabs={[
        { label: 'Overview', component: TagOverviewTab },
        { label: 'Edit', component: TagEditTab },
      ]}
      metricsTabs={[
        { label: 'Summary', component: TagSummaryMetrics },
      ]}
      loading={loading}
      error={error}
      onClose={() => navigate(-1)}
      storageKey="carbonTagDetail"
      entityData={tag}
    />
  );
}
