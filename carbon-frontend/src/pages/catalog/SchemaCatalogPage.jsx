// src/pages/catalog/SchemaCatalogPage.jsx
// Schema Catalog: Browsable registry with filters and search
import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import {
  Box, Typography, TextField, Button, Card, CardContent, CardHeader, Grid,
  CircularProgress, Alert, Chip, MenuItem, Paper, FormControl, InputLabel, Select
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import RefreshIcon from '@mui/icons-material/Refresh';
import StorageIcon from '@mui/icons-material/Storage';
import { fetchDataSchemaTables, fetchDataSchemaFields } from '../../api/dataschema';
import { fetchDataDomains, fetchAssetProfiles } from '../../api/catalog';

export default function SchemaCatalogPage() {
  const navigate = useNavigate();
  const { token } = useAuth();
  const { notify } = useNotification();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [tables, setTables] = useState([]);
  const [domains, setDomains] = useState([]);
  const [assets, setAssets] = useState({});

  // Filters
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedDomain, setSelectedDomain] = useState('');

  useEffect(() => {
    loadData();
  }, [token]);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [tablesData, domainsData, assetsData] = await Promise.all([
        fetchDataSchemaTables(token, null, null),
        fetchDataDomains(token),
        fetchAssetProfiles(token).catch(() => []),
      ]);

      setTables(tablesData || []);
      setDomains(domainsData || []);

      // Map assets by table_id for quick lookup
      const assetMap = {};
      (assetsData || []).forEach(a => {
        if (a.table_id) assetMap[a.table_id] = a;
      });
      setAssets(assetMap);
    } catch (err) {
      const msg = err.message || 'Failed to load schema catalog';
      setError(msg);
      notify({ message: msg, type: 'error' });
    } finally {
      setLoading(false);
    }
  }, [token, notify]);

  // Filter tables
  const filteredTables = tables.filter(table => {
    const matchesSearch = !searchTerm || 
      table.title?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      table.description?.toLowerCase().includes(searchTerm.toLowerCase());
    
    const matchesDomain = !selectedDomain || 
      assets[table.id]?.domain === parseInt(selectedDomain);

    return matchesSearch && matchesDomain;
  });

  const getAssetProfile = (tableId) => assets[tableId] || {};

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
      <Box sx={{ mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2 }}>
          <StorageIcon sx={{ fontSize: '2rem', color: 'primary.main' }} />
          <Box>
            <Typography variant="h5" fontWeight={700}>Schema Catalog</Typography>
            <Typography variant="body2" color="text.secondary">
              Browse all registered data tables and their metadata
            </Typography>
          </Box>
        </Box>
      </Box>

      {/* Error Alert */}
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {/* Filters & Search */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Grid container spacing={2} alignItems="flex-end">
          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              size="small"
              placeholder="Search tables..."
              startAdornment={<SearchIcon sx={{ mr: 1, color: 'action.disabled' }} />}
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              variant="outlined"
            />
          </Grid>
          <Grid item xs={12} sm={4}>
            <FormControl fullWidth size="small">
              <InputLabel>Domain</InputLabel>
              <Select
                value={selectedDomain}
                label="Domain"
                onChange={(e) => setSelectedDomain(e.target.value)}
              >
                <MenuItem value="">All Domains</MenuItem>
                {domains.map(d => (
                  <MenuItem key={d.id} value={d.id}>{d.name}</MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={2}>
            <Button
              fullWidth
              size="small"
              variant="outlined"
              startIcon={<RefreshIcon />}
              onClick={loadData}
            >
              Refresh
            </Button>
          </Grid>
        </Grid>
      </Paper>

      {/* Results Summary */}
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Showing {filteredTables.length} of {tables.length} tables
      </Typography>

      {/* Tables Grid */}
      {filteredTables.length === 0 ? (
        <Alert severity="info">No tables match your filters</Alert>
      ) : (
        <Grid container spacing={2}>
          {filteredTables.map(table => {
            const asset = getAssetProfile(table.id);
            const fieldCount = table.fields_count || 0;
            return (
              <Grid item xs={12} sm={6} md={4} key={table.id}>
                <Card
                  sx={{
                    cursor: 'pointer',
                    '&:hover': { boxShadow: 3 },
                    height: '100%',
                    display: 'flex',
                    flexDirection: 'column',
                  }}
                  onClick={() => navigate(`/catalog/schemas/${table.id}`)}
                >
                  <CardHeader
                    avatar={<StorageIcon sx={{ color: 'primary.main' }} />}
                    title={table.title}
                    titleTypographyProps={{ variant: 'subtitle1', fontWeight: 600 }}
                    sx={{ pb: 1 }}
                  />
                  <CardContent sx={{ pt: 0, flex: 1 }}>
                    {asset?.domain && (
                      <Box sx={{ mb: 1 }}>
                        <Chip
                          label={asset.domain}
                          size="small"
                          variant="outlined"
                        />
                      </Box>
                    )}
                    
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                      {table.description || 'No description'}
                    </Typography>

                    <Box sx={{ display: 'flex', gap: 1, mt: 2, flexWrap: 'wrap' }}>
                      <Chip
                        label={`${fieldCount} fields`}
                        size="small"
                        variant="outlined"
                      />
                      {asset?.classification && (
                        <Chip
                          label={asset.classification}
                          size="small"
                          color="primary"
                          variant="outlined"
                        />
                      )}
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            );
          })}
        </Grid>
      )}
    </Box>
  );
}
