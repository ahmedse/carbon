// File: src/pages/catalog/SchemaDetailHeader.jsx
// Header with breadcrumbs, title, and close button for schema detail page

import React from 'react';
import { Box, Typography, IconButton, Breadcrumbs, Link, useTheme, useMediaQuery } from '@mui/material';
import { useNavigate, useParams } from 'react-router-dom';
import CloseIcon from '@mui/icons-material/Close';
import HomeIcon from '@mui/icons-material/Home';
import StorageIcon from '@mui/icons-material/Storage';

export default function SchemaDetailHeader({ tableData, onClose }) {
  const navigate = useNavigate();
  const { tableId } = useParams();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

  const handleBreadcrumbClick = (path) => {
    navigate(path);
  };

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
      {/* Left: Breadcrumbs and title */}
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Breadcrumbs
          separator="/"
          sx={{
            mb: 1,
            fontSize: '0.875rem',
            '& a': {
              cursor: 'pointer',
              '&:hover': {
                textDecoration: 'underline',
              },
            },
          }}
        >
          <Link
            component="button"
            type="button"
            onClick={() => handleBreadcrumbClick('/catalog')}
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 0.5,
              color: 'inherit',
              textDecoration: 'none',
            }}
          >
            <HomeIcon sx={{ fontSize: '1rem' }} />
            Catalog
          </Link>
          <Link
            component="button"
            type="button"
            onClick={() => handleBreadcrumbClick('/dataschema')}
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 0.5,
              color: 'inherit',
              textDecoration: 'none',
            }}
          >
            <StorageIcon sx={{ fontSize: '1rem' }} />
            Schema
          </Link>
          <Typography sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <StorageIcon sx={{ fontSize: '1rem' }} />
            {getTableDisplayName()}
          </Typography>
        </Breadcrumbs>
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
