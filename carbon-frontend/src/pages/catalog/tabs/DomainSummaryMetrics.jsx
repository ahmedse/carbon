// src/pages/catalog/tabs/DomainSummaryMetrics.jsx

import React from 'react';
import { useTranslation } from 'react-i18next';
import DetailMetricsPanel, {
  MetricCard,
  MetricsGrid,
  MetricsSection,
} from '../../../components/detail/DetailMetricsPanel';
import InfoIcon from '@mui/icons-material/Info';
import UpdateIcon from '@mui/icons-material/Update';
import PersonIcon from '@mui/icons-material/Person';

export default function DomainSummaryMetrics({ entityData }) {
  const { t } = useTranslation('catalog');
  if (!entityData) return null;

  const createdDate = entityData.created_at 
    ? new Date(entityData.created_at).toLocaleDateString()
    : '—';
  const updatedDate = entityData.updated_at
    ? new Date(entityData.updated_at).toLocaleDateString()
    : '—';

  return (
    <DetailMetricsPanel>
      <MetricsSection title={t('domainInformation')}>
        <MetricsGrid>
          <MetricCard
            label={t('id')}
            value={entityData.id}
            icon={<InfoIcon />}
            color="primary"
          />
          <MetricCard
            label={t('owner')}
            value={entityData.owner || t('unassigned')}
            icon={<PersonIcon />}
            color="info"
          />
        </MetricsGrid>
      </MetricsSection>

      <MetricsSection title={t('timestamps')}>
        <MetricsGrid>
          <MetricCard
            label={t('created')}
            value={createdDate}
            icon={<InfoIcon />}
            color="success"
          />
          <MetricCard
            label={t('modified')}
            value={updatedDate}
            icon={<UpdateIcon />}
            color="warning"
          />
        </MetricsGrid>
      </MetricsSection>
    </DetailMetricsPanel>
  );
}
