// File: src/components/GridActionCell.jsx
// Reusable action cell component for data grid (View icon, Delete button)

import React from 'react';
import { Box, IconButton, Tooltip, Chip } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import VisibilityIcon from '@mui/icons-material/Visibility';
import DeleteIcon from '@mui/icons-material/Delete';
import AttachFileIcon from '@mui/icons-material/AttachFile';

export function EvidenceCell({ params }) {
  const evidenceCount = params.row.evidence_count || 0;
  if (evidenceCount === 0) return null;
  return (
    <Chip
      icon={<AttachFileIcon />}
      label={evidenceCount}
      size="small"
      variant="outlined"
    />
  );
}

export function ActionCell({ params, onDeleteRow }) {
  const { t } = useTranslation('common');
  const navigate = useNavigate();
  const tableId = params.row.table_id;
  const rowId = params.row.id;

  const handleViewRow = () => {
    if (tableId && rowId) {
      navigate(`/carbon/data-entry/row/${tableId}/${rowId}`);
    }
  };

  const handleDelete = (e) => {
    e.stopPropagation();
    onDeleteRow(params.row);
  };

  return (
    <Box sx={{ display: 'flex', gap: 0.5 }}>
      <Tooltip title={t('viewDetails')}>
        <IconButton
          size="small"
          onClick={(e) => {
            e.stopPropagation();
            handleViewRow();
          }}
        >
          <VisibilityIcon fontSize="small" />
        </IconButton>
      </Tooltip>
      <Tooltip title={t('delete')}>
        <IconButton size="small" onClick={handleDelete}>
          <DeleteIcon fontSize="small" />
        </IconButton>
      </Tooltip>
    </Box>
  );
}
