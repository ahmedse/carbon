// src/pages/admin/tabs/GroupOverviewTab.jsx
import React from 'react';
import { Box, Typography, Grid, Chip } from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';

function InfoRow({ label, value }) {
  return (
    <Box sx={{ mb: 1 }}> 
      <Typography variant='caption' color='text.secondary'>{label}</Typography>
      <Typography variant='body2'>{value || '—'}</Typography>
    </Box>
  );
}

export default function GroupOverviewTab({ entityData: group }) {
  if (!group) return null;

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant='h6' gutterBottom>Role Summary</Typography>
      <Grid container spacing={2}>
        <Grid item xs={12} md={6}>
          <InfoRow label='Group Name' value={group.name} />
          <InfoRow label='Type' value={group.role_type === 'platform' ? 'Platform Role' : 'App Role'} />
          <InfoRow label='App ID' value={group.app_id} />
          <InfoRow label='Manifest Key' value={group.manifest_key} />
        </Grid>
        <Grid item xs={12} md={6}>
          <InfoRow label='Scoped' value={group.is_scoped ? 'Yes' : 'No'} />
          <InfoRow label='Protected' value={group.is_protected ? 'Yes' : 'No'} />
          <InfoRow label='Users' value={group.users_count} />
          <InfoRow label='Permissions' value={group.permissions_count} />
        </Grid>
      </Grid>
      {group.description && (
        <Box sx={{ mt: 3 }}>
          <Typography variant='subtitle2' gutterBottom>Description</Typography>
          <Typography variant='body2' color='text.secondary'>{group.description}</Typography>
        </Box>
      )}
      <Box sx={{ mt: 3 }}>
        <Chip label={group.role_type === 'platform' ? 'Platform role' : 'App role'} color={group.role_type === 'platform' ? 'primary' : 'secondary'} />
      </Box>
    </Box>
  );
}
