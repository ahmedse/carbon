// src/pages/catalog/tabs/GovernanceTab.jsx
// Governance metadata editor for a schema table's catalog AssetProfile.
// AssetProfiles are auto-provisioned server-side and are PATCH-only.
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Box, Button, TextField, FormControl, InputLabel, Select, MenuItem,
  Paper, Typography, Grid, Chip, CircularProgress, Alert, Autocomplete,
  Stack,
} from '@mui/material';
import SaveIcon from '@mui/icons-material/Save';
import { useAuth } from '../../../auth/AuthContext';
import { useNotification } from '../../../components/NotificationProvider';
import { DetailTabContent } from '../../../components/detail/DetailMainPanel';
import {
  fetchTableAssetProfile, patchAssetProfile, fetchDataDomains, fetchTags, fetchGlossaryTerms,
} from '../../../api/catalog';
import { fetchUsers } from '../../../api/users';

// Matches backend catalog CLASSIFICATION_CHOICES / QUALITY_STATUS_CHOICES.
const CLASSIFICATIONS = ['public', 'internal', 'confidential', 'pii', 'sensitive'];
const CLASSIFICATION_LABELS = {
  public: 'Public', internal: 'Internal', confidential: 'Confidential',
  pii: 'PII', sensitive: 'Sensitive',
};
const QUALITY_COLOR = { passing: 'success', warning: 'warning', failing: 'error', unknown: 'default' };

const EMPTY_FORM = {
  description: '', classification: 'internal', domain: '',
  owner: '', steward: '', tags: [], semantic_type: '', glossary_term: '',
};

function unwrap(data) {
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.results)) return data.results;
  return [];
}

function formatDate(value) {
  if (!value) return '—';
  return new Date(value).toLocaleString();
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
  const [glossaryTerms, setGlossaryTerms] = useState([]);
  const [users, setUsers] = useState([]);

  const [form, setForm] = useState(EMPTY_FORM);
  const [initialForm, setInitialForm] = useState(EMPTY_FORM);

  const isDirty = useMemo(
    () => JSON.stringify(form) !== JSON.stringify(initialForm),
    [form, initialForm],
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [assetData, domainsData, tagsData, glossaryData, usersData] = await Promise.all([
        fetchTableAssetProfile(token, tableId),
        fetchDataDomains(token).catch(() => []),
        fetchTags(token).catch(() => []),
        fetchGlossaryTerms(token).catch(() => []),
        fetchUsers(token).catch(() => []), // may be admin-gated; degrade gracefully
      ]);

      const tableAsset = unwrap(assetData).find((a) => !a.data_field) || null;

      setDomains(unwrap(domainsData));
      setTags(unwrap(tagsData));
      setGlossaryTerms(unwrap(glossaryData));
      setUsers(unwrap(usersData));
      setAsset(tableAsset);

      if (tableAsset) {
        const next = {
          description: tableAsset.description || '',
          classification: tableAsset.classification || 'internal',
          domain: tableAsset.domain || '',
          owner: tableAsset.owner || '',
          steward: tableAsset.steward || '',
          tags: tableAsset.tags || [],
          semantic_type: tableAsset.semantic_type || '',
          glossary_term: tableAsset.glossary_term || '',
        };
        setForm(next);
        setInitialForm(next);
      } else {
        setForm(EMPTY_FORM);
        setInitialForm(EMPTY_FORM);
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
        semantic_type: form.semantic_type || '',
        glossary_term: form.glossary_term || null,
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

  if (error && !asset) {
    return (
      <DetailTabContent>
        <Stack spacing={2} alignItems="flex-start">
          <Alert severity="error">{error}</Alert>
          <Button variant="outlined" size="small" onClick={load}>Retry</Button>
        </Stack>
      </DetailTabContent>
    );
  }

  return (
    <DetailTabContent>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
        <Typography variant="h6">Governance</Typography>
        <Button variant="contained" size="small" startIcon={<SaveIcon />} onClick={handleSave}
          disabled={saving || !asset || !isDirty}>
          {saving ? 'Saving…' : 'Save Changes'}
        </Button>
      </Box>

      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Governance metadata for this table — classification, owning domain, owner, steward, and tags.
        The quality score is computed by Data Quality and is read-only.
      </Typography>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {!asset ? (
        <Paper variant="outlined" sx={{ p: 3, textAlign: 'center' }}>
          <Typography variant="body1" gutterBottom>No catalog asset profile found for this table.</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Asset profiles are provisioned automatically. Retry to create one for this table.
          </Typography>
          <Button variant="contained" size="small" onClick={load}>Retry</Button>
        </Paper>
      ) : (
        <Grid container spacing={3}>
          <Grid size={{ xs: 12, md: 7 }}>
            <Paper variant="outlined" sx={{ p: 3 }}>
              <Typography variant="subtitle2" fontWeight={600} gutterBottom>
                Classification &amp; Ownership
              </Typography>

              <FormControl fullWidth margin="normal">
                <InputLabel>Classification</InputLabel>
                <Select value={form.classification} label="Classification"
                  onChange={(e) => set('classification', e.target.value)}>
                  {CLASSIFICATIONS.map((c) => (
                    <MenuItem key={c} value={c}>{CLASSIFICATION_LABELS[c]}</MenuItem>
                  ))}
                </Select>
              </FormControl>

              <Autocomplete
                value={domains.find((d) => d.id === form.domain) || null}
                options={domains}
                getOptionLabel={(d) => d.name}
                isOptionEqualToValue={(opt, val) => opt.id === val.id}
                onChange={(e, val) => set('domain', val?.id || '')}
                renderInput={(params) => <TextField {...params} label="Domain" margin="normal" />}
              />

              <Autocomplete
                value={users.find((u) => u.id === form.owner) || null}
                options={users}
                getOptionLabel={userLabel}
                isOptionEqualToValue={(opt, val) => opt.id === val.id}
                onChange={(e, val) => set('owner', val?.id || '')}
                renderInput={(params) => <TextField {...params} label="Owner" margin="normal"
                  helperText="Accountable for the data in this table." />}
              />

              <Autocomplete
                value={users.find((u) => u.id === form.steward) || null}
                options={users}
                getOptionLabel={userLabel}
                isOptionEqualToValue={(opt, val) => opt.id === val.id}
                onChange={(e, val) => set('steward', val?.id || '')}
                renderInput={(params) => <TextField {...params} label="Steward" margin="normal"
                  helperText="Day-to-day custodian of data correctness." />}
              />

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
                label="Semantic Type" value={form.semantic_type}
                onChange={(e) => set('semantic_type', e.target.value)}
                fullWidth margin="normal" helperText="Optional business meaning, e.g. 'GHG emission factor'."
              />

              <Autocomplete
                value={glossaryTerms.find((g) => g.id === form.glossary_term) || null}
                options={glossaryTerms}
                getOptionLabel={(g) => g.term || g.name}
                isOptionEqualToValue={(opt, val) => opt.id === val.id}
                onChange={(e, val) => set('glossary_term', val?.id || '')}
                renderInput={(params) => <TextField {...params} label="Glossary Term" margin="normal"
                  helperText="Links this table to a governed business term." />}
              />

              <TextField
                label="Description" value={form.description}
                onChange={(e) => set('description', e.target.value)}
                fullWidth margin="normal" multiline rows={3}
              />
            </Paper>
          </Grid>

          <Grid size={{ xs: 12, md: 5 }}>
            <Paper variant="outlined" sx={{ p: 3 }}>
              <Typography variant="subtitle2" fontWeight={600} gutterBottom>
                Quality (read-only)
              </Typography>

              <Box sx={{ mt: 2 }}>
                <Typography variant="body2" color="text.secondary">Quality Score</Typography>
                <Typography variant="h4"
                  color={asset.quality_score >= 80 ? 'success.main' : asset.quality_score != null ? 'warning.main' : 'text.secondary'}>
                  {asset.quality_score != null ? asset.quality_score : 'N/A'}
                </Typography>
              </Box>

              <Box sx={{ mt: 3 }}>
                <Typography variant="body2" color="text.secondary" gutterBottom>Quality Status</Typography>
                <Chip
                  label={asset.quality_status || 'unknown'}
                  color={QUALITY_COLOR[asset.quality_status] || 'default'}
                  size="small"
                />
              </Box>

              <Box sx={{ mt: 3 }}>
                <Typography variant="body2" color="text.secondary" gutterBottom>Last Updated</Typography>
                <Typography variant="body2">{formatDate(asset.updated_at)}</Typography>
              </Box>

              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 2 }}>
                Quality is written by the Data Quality app and cannot be edited here.
              </Typography>
            </Paper>
          </Grid>
        </Grid>
      )}
    </DetailTabContent>
  );
}
