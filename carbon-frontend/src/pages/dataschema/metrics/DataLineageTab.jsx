// File: src/pages/dataschema/metrics/DataLineageTab.jsx
// Data lineage tab (placeholder for future implementation)

import React from 'react';
import { Box, Typography, Alert } from '@mui/material';

export default function DataLineageTab({ rowId }) {
  return (
    <Box>
      <Alert severity="info" sx={{ fontSize: '0.85rem', mb: 2 }}>
        Data lineage tracking coming soon in Phase 2
      </Alert>
      
      <Typography variant="caption" sx={{ color: '#999', display: 'block' }}>
        This tab will show:
      </Typography>
      <Typography variant="caption" sx={{ color: '#999', display: 'block', mt: 1 }}>
        • Upstream data sources<br/>
        • Transformation history<br/>
        • Related datasets<br/>
        • Dependency graph
      </Typography>
    </Box>
  );
}
