// src/pages/catalog/tabs/DomainSummaryMetrics.jsx

import React from 'react';
import DetailMetricsPanel, {
  MetricCard,
  MetricsGrid,
  MetricsSection,
} from '../../../components/detail/DetailMetricsPanel';
import InfoIcon from '@mui/icons-material/Info';
import UpdateIcon from '@mui/icons-material/Update';
import PersonIcon from '@mui/icons-material/Person';

export default function DomainSummaryMetrics({ entityData }) {
  if (!entityData) return null;

  const createdDate = entityData.created_at 
    ? new Date(entityData.created_at).toLocaleDateString()
    : '—';
  const updatedDate = entityData.updated_at
    ? new Date(entityData.updated_at).toLocaleDateString()
    : '—';

  return (
    <DetailMetricsPanel>
      <MetricsSection title="Domain Information">
        <MetricsGrid>
          <MetricCard
            label="ID"
            value={entityData.id}
            icon={<InfoIcon />}
            color="primary"
          />
          <MetricCard
            label="Owner"
            value={entityData.owner || 'Unassigned'}
            icon={<PersonIcon />}
            color="info"
          />
        </MetricsGrid>
      </MetricsSection>

      <MetricsSection title="Timestamps">
        <MetricsGrid>
          <MetricCard
            label="Created"
            value={createdDate}
            icon={<InfoIcon />}
            color="success"
          />
          <MetricCard
            label="Modified"
            value={updatedDate}
            icon={<UpdateIcon />}
            color="warning"
          />
        </MetricsGrid>
      </MetricsSection>
    </DetailMetricsPanel>
  );
}
