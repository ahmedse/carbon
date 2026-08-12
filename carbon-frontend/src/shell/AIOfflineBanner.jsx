// src/shell/AIOfflineBanner.jsx
import React from 'react';
import { Alert, Typography } from '@mui/material';
import CloudOffIcon from '@mui/icons-material/CloudOff';

function AIOfflineBanner() {
  return (
    <Alert
      severity="warning"
      icon={<CloudOffIcon fontSize="small" />}
      sx={{
        borderRadius: 0,
        '& .MuiAlert-message': { flex: 1 },
      }}
    >
      <Typography variant="caption">
        AI service is currently unavailable. You can still browse past
        conversations.
      </Typography>
    </Alert>
  );
}

export default AIOfflineBanner;
