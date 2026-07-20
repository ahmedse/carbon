// src/pages/catalog/tabs/GovernanceTab.jsx
// Governance metadata editor for a schema table's catalog AssetProfile.
// AssetProfiles are auto-provisioned server-side and are PATCH-only.
import React, { useState, useEffect, useCallback } from 'react';
import {
  Box, Button, TextField, FormControl, InputLabel, Select, MenuItem,
  Paper, Typography, Grid, Chip, CircularProgress, Alert, Autocomplete,
} from '@mui/material';
import SaveIcon from '@mui/icons-material/Save';
import { useAuth } from '../../../auth/AuthContext';
import { useNotification } from '../../../components/NotificationProvider';
import { DetailTabContent } from '../../../components/detail/DetailMainPanel';
import {
  fetchAssetProfiles, patchAssetProfile, fetchDataDomains, fetchTags,
} from '../../../api/catalog';
import { fetchUsers } from '../../../api/users';

// Matches backend catalog CLASSIFICATION_CHOICES / QUALITY_STATUS_CHOICES.
const CLASSIFICATIONS = ['public', 'internal', 'confidential', 'pii', 'sensitive'];
const QUALITY_COLOR = { passing: 'success', warning: 'warning', failing: 'error', unknown: 'default' };

function unwrap(data) {
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.results)) return data.results;
  return [];
}

export default function GovernanceTab({ tableId }) {
  const { token } = useAuth();
  const { notify } = useNotification();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const [asset, setAsset] = useState(null);
  const [domains, setDomains] = useState([]);
  const [tags, setTags] = useState([]);
  const [users, setUsers] = useState([]);

  const [form, setForm] = useState({
    description: '', classification: 'internal', domain: '',
    owner: '', steward: '', tags: [],
  });

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [assetsData, domainsData, tagsData, usersData] = await Promise.all([
        fetchAssetProfiles(token),
        fetchDataDomains(token).catch(() => []),
        fetchTags(token).catch(() => []),
        fetchUsers(token).catch(() => []), // may be admin-gated; degrade gracefully
      ]);

      const assets = unwrap(assetsData);
      const tid = parseInt(tableId, 10);
      const tableAsset = assets.find((a) => a.data_table === tid && !a.data_field);

      setDomains(unwrap(domainsData));
      setTags(unwrap(tagsData));
      setUsers(unwrap(usersData));
      setAsset(tableAsset || null);

      if (tableAsset) {
        setForm({
          description: tableAsset.description || '',
          classification: tableAsset.classification || 'internal',
          domain: tableAsset.domain || '',
          owner: tableAsset.owner || '',
          steward: tableAsset.steward || '',
          tags: tableAsset.tags || [],
        });
      }
    } catch (err) {
      setError(err.message || 'Failed to load governance metadata');
      notify({ message: err.message || 'Failed to load governance metadata', type: 'error' });
    } finally {
      setLoading(false);
    }
  }, [token, tableId, notify]);

  useEffect(() => { load(); }, [load]);

  const set = (key, value) => setForm((f) => ({ ...f, [key]: value }));

  const handleSave = async () => {
    if (!asset) { notify({ message: 'No asset profile for this table yet', type: 'error' }); return; }
    setSaving(true);
    setError(null);
    try {
      await patchAssetProfile(token, asset.id, {
        description: form.description,
        classification: form.classification,
        domain: form.domain || null,
        owner: form.owner || null,
        steward: form.steward || null,
        tags: form.tags,
      });
      notify({ message: 'Governance metadata saved', type: 'success' });
      load();
    } catch (err) {
      setError(err.message || 'Save failed');
      notify({ message: err.message || 'Save failed', type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const userLabel = (u) => u.username || u.email || `#${u.id}`;

  if (loading) {
    return (
      <DetailTabContent>
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}><CircularProgress /></Box>
      </DetailTabContent>
    );
  }

  return (
    <DetailTabContent>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">Governance</Typography>
        <Button variant="contained" startIcon={<SaveIcon />} onClick={handleSave} disabled={saving || !asset}>
          {saving ? 'Saving…' : 'Save Changes'}
        </Button>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {!asset && <Alert severity="warning" sx={{ mb: 2 }}>No catalog asset profile found for this table.</Alert>}

      <Grid container spacing={3}>
        <Grid item xs={12} md={7}>
          <Paper variant="outlined" sx={{ p: 3 }}>
            <Typography variant="subtitle2" fontWeight={600} gutterBottom>
              Classification &amp; Ownership
            </Typography>

            <FormControl fullWidth margin="normal">
              <InputLabel>Classification</InputLabel>
              <Select value={form.classification} label="Classification"
                onChange={(e) => set('classification', e.target.value)}>
                {CLASSIFICATIONS.map((c) => (
                  <MenuItem key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</MenuItem>
                ))}
              </Select>
            </FormControl>

            <FormControl fullWidth margin="normal">
              <InputLabel>Domain</InputLabel>
              <Select value={form.domain} label="Domain" onChange={(e) => set('domain', e.target.value)}>
                <MenuItem value="">None</MenuItem>
                {domains.map((d) => (<MenuItem key={d.id} value={d.id}>{d.name}</MenuItem>))}
              </Select>
            </FormControl>

            <FormControl fullWidth margin="normal">
              <InputLabel>Owner</InputLabel>
              <Select value={form.owner} label="Owner" onChange={(e) => set('owner', e.target.value)}>
                <MenuItem value="">None</MenuItem>
                {users.map((u) => (<MenuItem key={u.id} value={u.id}>{userLabel(u)}</MenuItem>))}
              </Select>
            </FormControl>

            <FormControl fullWidth margin="normal">
              <InputLabel>Steward</InputLabel>
              <Select value={form.steward} label="Steward" onChange={(e) => set('steward', e.target.value)}>
                <MenuItem value="">None</MenuItem>
                {users.map((u) => (<MenuItem key={u.id} value={u.id}>{userLabel(u)}</MenuItem>))}
              </Select>
            </FormControl>

            <Autocomplete
              multiple
              options={tags}
              getOptionLabel={(o) => o.name}
              value={tags.filter((t) => form.tags.includes(t.id))}
              onChange={(e, val) => set('tags', val.map((t) => t.id))}
              renderInput={(params) => <TextField {...params} label="Tags" margin="normal" />}
              renderTags={(value, getTagProps) =>
                value.map((option, index) => (
                  <Chip label={option.name} size="small" {...getTagProps({ index })} />
                ))
              }
            />

            <TextField
              label="Description" value={form.description}
              onChange={(e) => set('description', e.target.value)}
              fullWidth margin="normal" multiline rows={3}
            />
          </Paper>
        </Grid>

        <Grid item xs={12} md={5}>
          <Paper variant="outlined" sx={{ p: 3 }}>
            <Typography variant="subtitle2" fontWeight={600} gutterBottom>
              Quality (read-only)
            </Typography>

            <Box sx={{ mt: 2 }}>
              <Typography variant="body2" color="text.secondary">Quality Score</Typography>
              <Typography variant="h4"
                color={asset?.quality_score >= 80 ? 'success.main' : asset?.quality_score != null ? 'warning.main' : 'text.secondary'}>
                {asset?.quality_score != null ? asset.quality_score : 'N/A'}
              </Typography>
            </Box>

            <Box sx={{ mt: 3 }}>
              <Typography variant="body2" color="text.secondary" gutterBottom>Quality Status</Typography>
              <Chip
                label={asset?.quality_status || 'unknown'}
                color={QUALITY_COLOR[asset?.quality_status] || 'default'}
              />
            </Box>
          </Paper>
        </Grid>
      </Grid>
    </DetailTabContent>
  );
}
