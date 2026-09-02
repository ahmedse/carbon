// src/pages/admin/tabs/OrgUnitSummaryMetrics.jsx
import React from 'react';
import { Box, Typography } from '@mui/material';
import DetailMetricsPanel, {
  MetricCard,
  MetricsGrid,
  MetricsSection,
} from '../../../components/detail/DetailMetricsPanel';
import InfoIcon from '@mui/icons-material/Info';
import AccountTreeIcon from '@mui/icons-material/AccountTree';

const ORG_TYPES = {
  'university': 'University',
  'campus': 'Campus',
  'college': 'College',
  'department': 'Department',
  'division': 'Division',
  'team': 'Team',
  'facility': 'Facility',
  'other': 'Other',
  'company': 'Company',
  'section': 'Section',
  'crew': 'Crew',
  'base': 'Base',
  'yard': 'Yard',
  'store': 'Store',
  'cost_center': 'Cost Center',
};

export default function OrgUnitSummaryMetrics({ entityData }) {
  if (!entityData) return null;

  const parentUnit = entityData.allOrgUnits?.find(u => u.id === entityData.parent)?.name || 'No parent';

  return (
    <DetailMetricsPanel>
      <MetricsSection title="Hierarchy">
        <MetricsGrid>
          <MetricCard
            label="Type"
            value={ORG_TYPES[entityData.org_type] || entityData.org_type}
            icon={<AccountTreeIcon />}
            color="primary"
          />
          <MetricCard
            label="Parent"
            value={parentUnit}
            icon={<AccountTreeIcon />}
            color="info"
          />
        </MetricsGrid>
      </MetricsSection>

      <MetricsSection title="Details">
        <MetricsGrid>
          <MetricCard
            label="ID"
            value={entityData.id}
            icon={<InfoIcon />}
            color="success"
          />
          <MetricCard
            label="Code"
            value={entityData.code || '—'}
            icon={<InfoIcon />}
            color="warning"
          />
        </MetricsGrid>
      </MetricsSection>
    </DetailMetricsPanel>
  );
}
