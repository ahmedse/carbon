import React from 'react';
import { Box, Typography, Grid, Card, CardContent, Chip, Alert } from '@mui/material';
import { APP_REGISTRY } from '../../apps/registry';

export default function RegisteredAppsPage() {
  return (
    <Box sx={{ p: 3 }}>
      <Typography variant='h5' fontWeight={700} gutterBottom>Registered Apps</Typography>
      <Alert severity='info' sx={{ mb: 3 }}>
        This lists the apps currently registered in the platform shell registry and their declared manifests.
      </Alert>
      <Grid container spacing={3}>
        {APP_REGISTRY.map((app) => (
          <Grid item xs={12} md={6} lg={4} key={app.id}>
            <Card>
              <CardContent>
                <Typography variant='h6' gutterBottom>{app.name}</Typography>
                <Typography variant='body2' color='text.secondary' sx={{ mb: 2 }}>{app.description}</Typography>
                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 1 }}>
                  <Chip label={`v${app.version}`} size='small' />
                  <Chip label={app.id} size='small' variant='outlined' />
                </Box>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}
