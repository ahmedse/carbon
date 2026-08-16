// src/shell/AIArtifactBrowser.jsx
import React, { useCallback, useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Typography,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import { useAuth } from '../auth/AuthContext';
import { useNotification } from '../components/NotificationProvider';
import { listArtifacts, deleteArtifact } from '../api/aiWorkspace';
import AIArtifactCard from './AIArtifactCard';

const ARTIFACT_TYPES = [
  { value: '', label: 'All types' },
  { value: 'report', label: 'Report' },
  { value: 'query', label: 'Query' },
  { value: 'rule_set', label: 'Rule set' },
  { value: 'analysis', label: 'Analysis' },
];

function AIArtifactBrowser() {
  const { token } = useAuth();
  const { notify, notifyFromError } = useNotification();

  const [artifacts, setArtifacts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [typeFilter, setTypeFilter] = useState('');
  const [openArtifact, setOpenArtifact] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listArtifacts(token, { artifact_type: typeFilter || undefined, limit: 100 });
      const list = Array.isArray(data) ? data : (data?.results ?? []);
      setArtifacts(list);
    } catch (err) {
      setError(err.message || 'Could not load artifacts');
      notifyFromError(err, 'Could not load artifacts');
    } finally {
      setLoading(false);
    }
  }, [token, typeFilter, notifyFromError]);

  useEffect(() => { load(); }, [load]);

  const handleDelete = useCallback(async () => {
    if (!deleteTarget) return;
    const id = deleteTarget.id;
    setDeleteTarget(null);
    setArtifacts((prev) => prev.filter((a) => a.id !== id));
    try {
      await deleteArtifact(token, id);
      notify({ message: 'Artifact deleted', type: 'success' });
    } catch (err) {
      notifyFromError(err, 'Could not delete artifact');
      load();
    }
  }, [deleteTarget, token, notify, notifyFromError, load]);

  return (
    <Box sx={{ p: 2, height: '100%', overflow: 'auto' }}>
      {/* Toolbar */}
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
        <Typography variant="subtitle2" fontWeight={600} sx={{ flex: 1 }}>
          Artifacts
        </Typography>
        <FormControl size="small" sx={{ minWidth: 120 }}>
          <InputLabel>Type</InputLabel>
          <Select
            label="Type"
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            sx={{ fontSize: '0.8125rem' }}
          >
            {ARTIFACT_TYPES.map((t) => (
              <MenuItem key={t.value} value={t.value} sx={{ fontSize: '0.8125rem' }}>
                {t.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <Button size="small" startIcon={<RefreshIcon />} onClick={load} variant="outlined">
          Refresh
        </Button>
      </Stack>

      {/* States */}
      {loading && (
        <Typography variant="caption" color="text.secondary">
          Loading…
        </Typography>
      )}

      {!loading && error && (
        <Stack spacing={1} alignItems="flex-start">
          <Typography variant="caption" color="error.main">{error}</Typography>
          <Button size="small" variant="outlined" onClick={load}>Retry</Button>
        </Stack>
      )}

      {!loading && !error && artifacts.length === 0 && (
        <Box sx={{ textAlign: 'center', py: 6 }}>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            No artifacts yet.
          </Typography>
          <Typography variant="caption" color="text.disabled">
            Promote an AI response to an artifact from the conversation view.
          </Typography>
        </Box>
      )}

      {!loading && !error && artifacts.length > 0 && (
        <Stack spacing={1}>
          {artifacts.map((a) => (
            <AIArtifactCard
              key={a.id}
              artifact={a}
              onOpen={(art) => setOpenArtifact(art)}
            />
          ))}
        </Stack>
      )}

      {/* Artifact detail dialog */}
      {openArtifact && (
        <Dialog
          open
          onClose={() => setOpenArtifact(null)}
          maxWidth="sm"
          fullWidth
        >
          <DialogTitle sx={{ fontSize: '1rem', fontWeight: 600 }}>
            {openArtifact.title || 'Artifact'}
          </DialogTitle>
          <DialogContent>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
              Type: {openArtifact.artifact_type || '—'} · Created: {openArtifact.created_at ? new Date(openArtifact.created_at).toLocaleString() : '—'}
            </Typography>
            <Box
              component="pre"
              sx={{
                fontSize: '0.75rem',
                bgcolor: 'action.hover',
                p: 1.5,
                borderRadius: 1,
                overflowX: 'auto',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                maxHeight: 340,
                overflowY: 'auto',
                m: 0,
              }}
            >
              {JSON.stringify(openArtifact.content_json, null, 2)}
            </Box>
          </DialogContent>
          <DialogActions sx={{ px: 2, pb: 1.5 }}>
            <Button size="small" color="error" onClick={() => setDeleteTarget(openArtifact)}>
              Delete
            </Button>
            <Button size="small" onClick={() => setOpenArtifact(null)}>
              Close
            </Button>
          </DialogActions>
        </Dialog>
      )}

      {/* Delete confirmation */}
      <Dialog open={Boolean(deleteTarget)} onClose={() => setDeleteTarget(null)}>
        <DialogTitle sx={{ fontSize: '1rem', fontWeight: 600 }}>Delete artifact?</DialogTitle>
        <DialogContent>
          <Typography variant="body2">
            This permanently removes "{deleteTarget?.title || 'the artifact'}".
          </Typography>
        </DialogContent>
        <DialogActions sx={{ px: 2, pb: 1.5 }}>
          <Button size="small" onClick={() => setDeleteTarget(null)}>Cancel</Button>
          <Button size="small" color="error" variant="contained" onClick={handleDelete}>Delete</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

AIArtifactBrowser.propTypes = {};

export default AIArtifactBrowser;
