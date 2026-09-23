// src/pages/admin/tabs/GroupOverviewTab.jsx
import React from 'react';
import { Box, Typography, Grid, Chip } from '@mui/material';

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
      <Typography variant='h6' gutterBottom>Duty</Typography>
      <Typography variant='body2' color='text.secondary' sx={{ mb: 2 }}>
        A duty is a capability bundle. It is not tied to an org unit. Open Assignment Management to see each grant: one user, this duty, and one anchor org unit. Child units are included when access is checked. They are not extra rows.
      </Typography>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, md: 6 }}>
          <InfoRow label='Duty' value={group.duty || group.name} />
          <InfoRow label='Stored group' value={group.name} />
          <InfoRow label='Type' value={group.role_type === 'platform' ? 'Platform' : 'App'} />
          <InfoRow label='App' value={group.app_id} />
        </Grid>
        <Grid size={{ xs: 12, md: 6 }}>
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
