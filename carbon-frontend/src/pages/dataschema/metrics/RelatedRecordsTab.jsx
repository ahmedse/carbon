// File: src/pages/dataschema/metrics/RelatedRecordsTab.jsx
// Related records tab (placeholder for future implementation)

import React from 'react';
import { Box, Typography, Alert } from '@mui/material';

export default function RelatedRecordsTab({ rowId }) {
  return (
    <Box>
      <Alert severity="info" sx={{ fontSize: '0.85rem', mb: 2 }}>
        Related records navigation coming soon in Phase 2
      </Alert>
      
      <Typography variant="caption" sx={{ color: '#999', display: 'block' }}>
        This tab will show:
      </Typography>
      <Typography variant="caption" sx={{ color: '#999', display: 'block', mt: 1 }}>
        • Parent records<br/>
        • Child records<br/>
        • Cross-references<br/>
        • One-click navigation
      </Typography>
    </Box>
  );
}
