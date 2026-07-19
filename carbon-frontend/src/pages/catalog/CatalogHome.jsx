// src/pages/catalog/CatalogHome.jsx
// Catalog Studio Home: Dashboard overview of data governance
import React, { useEffect, useState } from 'react';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import {
  Box, Typography, Card, CardContent, CardHeader, Grid, CircularProgress,
  Alert, Button, Chip, LinearProgress, Paper
} from '@mui/material';
import LibraryBooksIcon from '@mui/icons-material/LibraryBooks';
import StorageIcon from '@mui/icons-material/Storage';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import WarningIcon from '@mui/icons-material/Warning';
import ErrorIcon from '@mui/icons-material/Error';
import { fetchDataDomains } from '../../api/catalog';
import { fetchDataSchemaTables } from '../../api/dataschema';

export default function CatalogHome() {
  const { token } = useAuth();
  const { notify } = useNotification();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [stats, setStats] = useState({
    totalDomains: 0,
    totalTables: 0,
    tablesWithMetadata: 0,
    qualityScore: 0,
  });

  useEffect(() => {
    loadDashboardData();
  }, [token]);

  const loadDashboardData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [domains, tables] = await Promise.all([
        fetchDataDomains(token),
        fetchDataSchemaTables(token, null, null),
      ]);

      const tablesWithMetadata = tables.filter(t => t.asset_profile?.description).length;
      const qualityScore = tables.length > 0 ? Math.round((tablesWithMetadata / tables.length) * 100) : 0;

      setStats({
        totalDomains: domains.length,
        totalTables: tables.length,
        tablesWithMetadata,
        qualityScore,
      });
    } catch (err) {
      const msg = err.message || 'Failed to load catalog dashboard';
      setError(msg);
      notify({ message: msg, type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1 }}>
          <LibraryBooksIcon sx={{ fontSize: '2.5rem', color: 'primary.main' }} />
          <Box>
            <Typography variant="h4" fontWeight={700}>Catalog Studio</Typography>
            <Typography variant="body2" color="text.secondary">
              Centralized schema catalog with governance and lineage
            </Typography>
          </Box>
        </Box>
      </Box>

      {/* Error Alert */}
      {error && <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert>}

      {/* Metrics Grid */}
      <Grid container spacing={2} sx={{ mb: 4 }}>
        {/* Total Domains */}
        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ height: '100%' }}>
            <CardHeader
              title="Data Domains"
              titleTypographyProps={{ variant: 'subtitle2', fontWeight: 600 }}
              sx={{ pb: 1 }}
            />
            <CardContent sx={{ pt: 0 }}>
              <Typography variant="h3" fontWeight={700}>{stats.totalDomains}</Typography>
              <Typography variant="caption" color="text.secondary">
                Business data domains
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Total Tables */}
        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ height: '100%' }}>
            <CardHeader
              title="Tables"
              titleTypographyProps={{ variant: 'subtitle2', fontWeight: 600 }}
              sx={{ pb: 1 }}
            />
            <CardContent sx={{ pt: 0 }}>
              <Typography variant="h3" fontWeight={700}>{stats.totalTables}</Typography>
              <Typography variant="caption" color="text.secondary">
                Registered data tables
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Metadata Coverage */}
        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ height: '100%' }}>
            <CardHeader
              title="Metadata Coverage"
              titleTypographyProps={{ variant: 'subtitle2', fontWeight: 600 }}
              sx={{ pb: 1 }}
            />
            <CardContent sx={{ pt: 0 }}>
              <Typography variant="h3" fontWeight={700}>{stats.tablesWithMetadata}</Typography>
              <Typography variant="caption" color="text.secondary">
                Tables with documentation
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Quality Score */}
        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ height: '100%' }}>
            <CardHeader
              title="Quality Index"
              titleTypographyProps={{ variant: 'subtitle2', fontWeight: 600 }}
              sx={{ pb: 1 }}
            />
            <CardContent sx={{ pt: 0 }}>
              <Typography variant="h3" fontWeight={700}>{stats.qualityScore}%</Typography>
              <LinearProgress variant="determinate" value={stats.qualityScore} sx={{ mt: 1 }} />
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Quick Access Cards */}
      <Typography variant="h6" fontWeight={700} sx={{ mb: 2 }}>Quick Access</Typography>
      <Grid container spacing={2} sx={{ mb: 4 }}>
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <StorageIcon sx={{ color: 'primary.main' }} />
              <Typography variant="subtitle1" fontWeight={600}>Schema Browser</Typography>
            </Box>
            <Typography variant="body2" color="text.secondary">
              Browse and filter all data tables with domain, owner, and quality filters
            </Typography>
            <Box>
              <Button variant="outlined" size="small" href="/catalog/schemas">
                Open Schema Browser
              </Button>
            </Box>
          </Paper>
        </Grid>

        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <CheckCircleIcon sx={{ color: 'success.main' }} />
              <Typography variant="subtitle1" fontWeight={600}>Schema Manager</Typography>
            </Box>
            <Typography variant="body2" color="text.secondary">
              Create and manage tables, fields, and relations. Admin-only access.
            </Typography>
            <Box>
              <Button variant="outlined" size="small" href="/catalog/schema-manager">
                Open Schema Manager
              </Button>
            </Box>
          </Paper>
        </Grid>
      </Grid>

      {/* Governance & Metadata */}
      <Typography variant="h6" fontWeight={700} sx={{ mb: 2 }}>Governance & Metadata</Typography>
      <Grid container spacing={2}>
        <Grid item xs={12} sm={6} md={3}>
          <Button
            fullWidth
            variant="outlined"
            href="/catalog/domains"
            sx={{ py: 1.5 }}
          >
            Domains
          </Button>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Button
            fullWidth
            variant="outlined"
            href="/catalog/glossary"
            sx={{ py: 1.5 }}
          >
            Glossary
          </Button>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Button
            fullWidth
            variant="outlined"
            href="/catalog/reference-data"
            sx={{ py: 1.5 }}
          >
            Reference Data
          </Button>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Button
            fullWidth
            variant="outlined"
            href="/catalog/sources"
            sx={{ py: 1.5 }}
          >
            Data Sources
          </Button>
        </Grid>
      </Grid>
    </Box>
  );
}
