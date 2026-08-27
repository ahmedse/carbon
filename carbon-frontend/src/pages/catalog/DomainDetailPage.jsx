// src/pages/catalog/DomainDetailPage.jsx
// Domain Detail: Full view of a data domain with governance info

import React, { useEffect, useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
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
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useNotes } from '../../notes/NotesContext';
import { registerDomainInspectorTabs } from '../../inspector/tabs/catalogTabs';

export default function DomainDetailPage() {
  useDocumentTitle("Domain Detail");
  const { t } = useTranslation('catalog');
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
        setError(t('missingParams'));
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        const data = await apiFetch(`catalog/domains/${domainId}/`, { method: 'GET', token }); // fetch domain
        setDomain(data);
      } catch (err) {
        const message = err.message || t('domainLoadError');
        setError(message);
        notify({ message, type: 'error' });
      } finally {
        setLoading(false);
      }
    };

    fetchDomain();
  }, [domainId, token, notify, t]);

  // ── Contextual Inspector (global drawer) ────────────────────────────
  const { setContexts } = useNotes();

  useEffect(() => registerDomainInspectorTabs(), []);

  const inspectorContext = useMemo(
    () => [{ entityType: 'domain', entityId: domainId, label: domain?.name, payload: { entityData: domain } }],
    [domainId, domain],
  );
  useEffect(() => {
    setContexts(inspectorContext);
    return () => setContexts(null);
  }, [inspectorContext, setContexts]);

  const headerComponent = (
    <DetailHeader
      title={domain?.name || t('domainFallback')}
      description={domain?.description}
      icon={CategoryIcon}
      onClose={() => navigate(-1)}
    />
  );

  return (
    <BaseDetailPage
      headerComponent={headerComponent}
      mainTabs={[
        { label: t('overview'), component: DomainOverviewTab },
        { label: t('common:edit'), component: DomainEditTab },
      ]}
      loading={loading}
      error={error}
      onClose={() => navigate(-1)}
      storageKey="carbonDomainDetail"
      entityData={domain}
    />
  );
}
