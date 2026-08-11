// src/pages/catalog/tabs/DataProductAuditTab.jsx
// Data Product Audit Tab: governance events for the module and its tables
// (backend /audit_trail/ endpoint). Action-colored chips + timestamp formatting.
import React, { useMemo } from 'react';
import { Box, Chip, Typography, Alert } from '@mui/material';
import { DataGrid } from '@mui/x-data-grid';
import { DetailTabContent } from '../../../components/detail/DetailMainPanel';

const ACTION_COLOR = {
  add: 'success', create: 'success',
  edit: 'info', update: 'info',
  delete: 'error',
  archive: 'warning', restore: 'default',
  lock: 'warning', unlock: 'info',
  publish: 'success', unpublish: 'default',
};

function formatDate(value) {
  if (!value) return '—';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString();
}

export default function DataProductAuditTab({ entityData, additionalProps = {} }) {
  const { auditEvents = [] } = additionalProps;

  const columns = useMemo(() => [
    {
      field: 'timestamp',
      headerName: 'Timestamp',
      width: 180,
      valueGetter: (value, row) => row.timestamp || null,
      valueFormatter: (value) => formatDate(value),
    },
    {
      field: 'action',
      headerName: 'Action',
      width: 140,
      renderCell: (params) => (
        <Chip
          label={params.value || '—'}
          size="small"
          color={ACTION_COLOR[params.value] || 'default'}
          variant="outlined"
        />
      ),
    },
    {
      field: 'entity_type',
      headerName: 'Entity',
      width: 130,
      valueGetter: (value, row) => {
        const type = row.entity_type || '—';
        const id = row.entity_id;
        return id != null ? `${type} #${id}` : type;
      },
    },
    { field: 'username', headerName: 'User', width: 150, valueGetter: (value, row) => row.username || '—' },
    {
      field: 'message',
      headerName: 'Details',
      flex: 1,
      minWidth: 240,
      valueGetter: (value, row) => row.message || row.action || '—',
    },
  ], []);

  if (!entityData) {
    return (
      <DetailTabContent>
        <Typography variant="body2" color="text.secondary">No data available</Typography>
      </DetailTabContent>
    );
  }

  return (
    <DetailTabContent>
      <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 2 }}>
        Governance Events ({auditEvents.length})
      </Typography>

      {auditEvents.length === 0 ? (
        <Alert severity="info">No governance events recorded for this data product.</Alert>
      ) : (
        <Box sx={{ height: 420, width: '100%' }}>
          <DataGrid
            rows={auditEvents}
            columns={columns}
            density="compact"
            pageSizeOptions={[10, 25, 50]}
            initialState={{ pagination: { paginationModel: { pageSize: 10 } } }}
            disableRowSelectionOnClick
          />
        </Box>
      )}
    </DetailTabContent>
  );
}
