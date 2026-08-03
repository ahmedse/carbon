import React, { useState, useEffect, useCallback } from 'react';
import {
  Box, Typography, Grid, Card, CardContent, Chip, Alert, Switch,
  FormControlLabel, CircularProgress, Snackbar,
} from '@mui/material';
import useDocumentTitle from '../../hooks/useDocumentTitle';

import { apiFetch } from '../../api/api';
import { useAuth } from '../../auth/AuthContext';

export default function RegisteredAppsPage() {
  useDocumentTitle("Registered Apps");
  const { _user } = useAuth();
  const [apps, setApps] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [snackbar, setSnackbar] = useState({ open: false, message: '' });

  const fetchApps = useCallback(async () => {
    try {
      setLoading(true);
      const data = await apiFetch('accounts/platform-apps/');
      setApps(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchApps(); }, [fetchApps]);

  const handleToggle = async (appId, currentEnabled) => {
    try {
      const updated = await apiFetch(`accounts/platform-apps/${appId}/`, {
        method: 'PUT',
        body: { is_enabled: !currentEnabled },
      });
      setApps(prev => prev.map(a => a.app_id === appId ? { ...a, is_enabled: updated.is_enabled } : a));
      setSnackbar({ open: true, message: `${appId} ${updated.is_enabled ? 'enabled' : 'disabled'}` });
    } catch (err) {
      setSnackbar({ open: true, message: `Failed: ${err.message}` });
    }
  };

  if (loading) return <Box sx={{ p: 3, textAlign: 'center' }}><CircularProgress /></Box>;
  if (error) return <Box sx={{ p: 3 }}><Alert severity="error">Failed to load apps: {error}</Alert></Box>;

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant='h5' fontWeight={700} gutterBottom>Registered Apps</Typography>
      <Alert severity='info' sx={{ mb: 3 }}>
        Enable or disable domain apps for the platform. Disabled apps are hidden from the home portal and activity bar for all users.
      </Alert>
      <Grid container spacing={3}>
        {apps.map((app) => (
          <Grid size={{ xs: 12, md: 6, lg: 4 }} key={app.app_id}>
            <Card sx={{ borderTop: `4px solid ${app.is_enabled ? '#2e7d32' : '#9e9e9e'}` }}>
              <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
                  <Typography variant='h6'>{app.name}</Typography>
                  <FormControlLabel
                    control={
                      <Switch
                        checked={app.is_enabled}
                        onChange={() => handleToggle(app.app_id, app.is_enabled)}
                        color="success"
                      />
                    }
                    label={app.is_enabled ? 'Enabled' : 'Disabled'}
                    labelPlacement="start"
                  />
                </Box>
                <Typography variant='body2' color='text.secondary' sx={{ mb: 2 }}>
                  {app.description || 'No description'}
                </Typography>
                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                  <Chip label={`v${app.version}`} size='small' />
                  <Chip label={app.app_id} size='small' variant='outlined' />
                  {(app.roles || []).map(r => (
                    <Chip key={r.key} label={r.label} size='small' variant='outlined' color='primary' />
                  ))}
                </Box>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
      {apps.length === 0 && (
        <Alert severity="warning">No apps registered. Add manifests to the APP_REGISTRY.</Alert>
      )}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={3000}
        onClose={() => setSnackbar({ open: false, message: '' })}
        message={snackbar.message}
      />
    </Box>
  );
}
