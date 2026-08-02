// File: src/pages/catalog/SchemaDetailHeader.jsx
// Header with breadcrumbs, title, and close button for schema detail page

import React from 'react';
import { Box, Typography, IconButton } from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import StorageIcon from '@mui/icons-material/Storage';
import useDocumentTitle from '../../hooks/useDocumentTitle';

export default function SchemaDetailHeader({ tableData, onClose }) {
  useDocumentTitle("Table Schema");

  const getTableDisplayName = () => {
    if (!tableData) return 'Schema Details';
    return tableData.title || `Table #${tableData.id}`;
  };

  return (
    <Box
      sx={{
        bgcolor: 'white',
        borderBottom: '1px solid #e0e0e0',
        p: 2,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 2,
      }}
    >
      {/* Left: Title */}
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <StorageIcon sx={{ fontSize: '1.5rem', color: 'primary.main' }} />
          <Box>
            <Typography variant="h6" sx={{ fontWeight: 600, m: 0 }}>
              {getTableDisplayName()}
            </Typography>
            {tableData?.description && (
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                {tableData.description}
              </Typography>
            )}
          </Box>
        </Box>
      </Box>

      {/* Right: Close button */}
      <IconButton
        onClick={onClose}
        size="small"
        sx={{
          flexShrink: 0,
          bgcolor: 'action.hover',
          '&:hover': {
            bgcolor: 'action.selected',
          },
        }}
      >
        <CloseIcon fontSize="small" />
      </IconButton>
    </Box>
  );
}
