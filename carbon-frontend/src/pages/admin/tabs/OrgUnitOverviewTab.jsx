// src/pages/admin/tabs/OrgUnitOverviewTab.jsx
import React from 'react';
import { Box, Table, TableHead, TableRow, TableCell, TableBody, Typography } from '@mui/material';
import { DetailTabContent } from '../../../components/detail/DetailMainPanel';

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

export default function OrgUnitOverviewTab({ entityData }) {
  if (!entityData) {
    return (
      <DetailTabContent>
        <Typography color="textSecondary">No data available</Typography>
      </DetailTabContent>
    );
  }

  const parentUnit = entityData.allOrgUnits?.find(u => u.id === entityData.parent)?.name || '—';

  const attributes = [
    { label: 'ID', value: entityData.id },
    { label: 'Name', value: entityData.name },
    { label: 'Type', value: ORG_TYPES[entityData.org_type] || entityData.org_type },
    { label: 'Code', value: entityData.code || '—' },
    { label: 'Parent Unit', value: parentUnit },
    { label: 'Description', value: entityData.description || '—' },
  ];

  return (
    <DetailTabContent>
      <Box sx={{ overflowX: 'auto' }}>
        <Table>
          <TableHead>
            <TableRow sx={{ bgcolor: 'grey.100' }}>
              <TableCell sx={{ fontWeight: 600 }}>Property</TableCell>
              <TableCell sx={{ fontWeight: 600 }}>Value</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {attributes.map((attr, idx) => (
              <TableRow key={idx} sx={{ '&:hover': { bgcolor: 'grey.50' } }}>
                <TableCell sx={{ fontWeight: 500, width: '30%' }}>{attr.label}</TableCell>
                <TableCell>{attr.value}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Box>
    </DetailTabContent>
  );
}
