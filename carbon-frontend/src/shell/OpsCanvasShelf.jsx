/** Ops Canvas shelf — Job Maps + legacy artifacts (ADR-0041 Phase 1). */
import React, { useCallback, useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Button,
  Dialog,
  DialogContent,
  DialogTitle,
  IconButton,
  Stack,
  Tab,
  Tabs,
  Typography,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import RefreshIcon from '@mui/icons-material/Refresh';
import ShareOutlinedIcon from '@mui/icons-material/ShareOutlined';
import MapOutlinedIcon from '@mui/icons-material/MapOutlined';
import { useAuth } from '../auth/AuthContext';
import { useNotification } from '../components/NotificationProvider';
import {
  createJobMap,
  listArtifacts,
  shareArtifact,
} from '../api/aiWorkspace';
import { getWorkObjectives } from '../api/aiWorkspace';
import AIArtifactCard from './AIArtifactCard';
import OpsCanvasHost from './OpsCanvasHost';

export default function OpsCanvasShelf({
  conversationId = null,
  relatedType = null,
  relatedId = null,
  onOpenInWorkspace = null,
}) {
  const { token } = useAuth();
  const { notify, notifyFromError } = useNotification();
  const [tab, setTab] = useState(0);
  const [jobMaps, setJobMaps] = useState([]);
  const [artifacts, setArtifacts] = useState([]);
  const [objectives, setObjectives] = useState([]);
  const [loading, setLoading] = useState(true);
  const [openMap, setOpenMap] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [maps, arts, objs] = await Promise.all([
        listArtifacts(token, {
          artifact_type: 'job_map',
          related_type: relatedType || undefined,
          related_id: relatedId || undefined,
          limit: 100,
        }),
        listArtifacts(token, { limit: 100 }),
        getWorkObjectives({ statusFilter: 'open' }).catch(() => []),
      ]);
      const mapList = Array.isArray(maps) ? maps : (maps?.results ?? []);
      const artList = Array.isArray(arts) ? arts : (arts?.results ?? []);
      setJobMaps(mapList);
      setArtifacts(artList.filter((a) => a.artifact_type !== 'job_map'));
      setObjectives(Array.isArray(objs) ? objs : (objs?.results ?? []));
    } catch (err) {
      notifyFromError(err, 'Could not load canvases');
    } finally {
      setLoading(false);
    }
  }, [token, relatedType, relatedId, notifyFromError]);

  useEffect(() => { load(); }, [load]);

  const handleShare = useCallback(async (artifact) => {
    try {
      const res = await shareArtifact(token, artifact.id);
      const tok = res?.share_token;
      if (tok && navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(tok);
      }
      notify({
        message: tok ? `Share token copied (${tok.slice(0, 8)}…)` : 'Shared',
        type: 'success',
      });
      load();
    } catch (err) {
      notifyFromError(err, 'Could not share canvas');
    }
  }, [token, notify, notifyFromError, load]);

  const handleNewBrief = useCallback(async () => {
    if (!conversationId) {
      notify({ message: 'Open a conversation first', type: 'warning' });
      return;
    }
    try {
      const art = await createJobMap(token, {
        conversation_id: conversationId,
        mode: 'chat',
        title: 'Job Brief',
        ask: 'Manual Job Brief',
        related_object: relatedType
          ? { type: relatedType, id: relatedId || '', label: '' }
          : undefined,
      });
      setOpenMap(art);
      notify({ message: 'Job Map created', type: 'success' });
      load();
    } catch (err) {
      notifyFromError(err, 'Could not create Job Map');
    }
  }, [conversationId, relatedType, relatedId, token, notify, notifyFromError, load]);

  return (
    <Box sx={{ p: 1.5, height: '100%', overflow: 'auto' }} data-testid="ops-canvas-shelf">
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
        <MapOutlinedIcon sx={{ fontSize: 18 }} />
        <Typography variant="subtitle2" fontWeight={700} sx={{ flex: 1 }}>
          Ops Canvas
        </Typography>
        <Button size="small" variant="outlined" onClick={handleNewBrief} disabled={!conversationId}>
          New brief
        </Button>
        <Button size="small" startIcon={<RefreshIcon />} onClick={load} variant="text">
          Refresh
        </Button>
      </Stack>

      <Tabs
        value={tab}
        onChange={(_, v) => setTab(v)}
        sx={{ minHeight: 32, mb: 1, '& .MuiTab-root': { minHeight: 32, py: 0, fontSize: '0.75rem' } }}
      >
        <Tab label={`Job Maps (${jobMaps.length})`} />
        <Tab label={`Artifacts (${artifacts.length})`} />
        <Tab label={`Objectives (${objectives.length})`} />
      </Tabs>

      {loading && (
        <Typography variant="caption" color="text.secondary">Loading…</Typography>
      )}

      {!loading && tab === 0 && (
        <Stack spacing={1}>
          {jobMaps.length === 0 && (
            <Typography variant="caption" color="text.secondary">
              No Job Maps yet. Multi-hop Chat answers and Agent plans create them automatically.
            </Typography>
          )}
          {jobMaps.map((a) => (
            <Box key={a.id} sx={{ position: 'relative' }}>
              <AIArtifactCard artifact={a} onOpen={() => setOpenMap(a)} />
              <IconButton
                size="small"
                aria-label="Share"
                onClick={() => handleShare(a)}
                sx={{ position: 'absolute', top: 8, right: 40 }}
              >
                <ShareOutlinedIcon fontSize="inherit" />
              </IconButton>
            </Box>
          ))}
        </Stack>
      )}

      {!loading && tab === 1 && (
        <Stack spacing={1}>
          {artifacts.length === 0 && (
            <Typography variant="caption" color="text.secondary">No other artifacts.</Typography>
          )}
          {artifacts.map((a) => (
            <AIArtifactCard key={a.id} artifact={a} onOpen={() => setOpenMap(a)} />
          ))}
        </Stack>
      )}

      {!loading && tab === 2 && (
        <Stack spacing={1}>
          {objectives.length === 0 && (
            <Typography variant="caption" color="text.secondary">
              No open work objectives. Save an investigation from Agent to resume here.
            </Typography>
          )}
          {objectives.map((o) => (
            <Box
              key={o.id}
              sx={{ border: 1, borderColor: 'divider', borderRadius: 1, p: 1.25, cursor: 'pointer' }}
              onClick={() => {
                if (onOpenInWorkspace && o.conversation_id) {
                  onOpenInWorkspace(o.conversation_id);
                }
              }}
            >
              <Typography variant="body2" fontWeight={600}>{o.title}</Typography>
              <Typography variant="caption" color="text.secondary">
                {o.status} · {(o.latest_summary || o.description || '').slice(0, 120)}
              </Typography>
            </Box>
          ))}
        </Stack>
      )}

      <Dialog
        open={Boolean(openMap)}
        onClose={() => setOpenMap(null)}
        fullWidth
        maxWidth="md"
        PaperProps={{ sx: { height: '85vh' } }}
      >
        <DialogTitle sx={{ display: 'flex', alignItems: 'center', pr: 1 }}>
          <Typography variant="subtitle1" fontWeight={700} sx={{ flex: 1 }}>
            {openMap?.title || 'Job Map'}
          </Typography>
          <IconButton onClick={() => setOpenMap(null)} aria-label="Close">
            <CloseIcon />
          </IconButton>
        </DialogTitle>
        <DialogContent dividers sx={{ p: 0 }}>
          {openMap?.artifact_type === 'job_map' || openMap?.content_json?.kind === 'job_map' ? (
            <OpsCanvasHost
              artifact={openMap}
              readOnly={openMap?.content_json?.mode !== 'agent'}
            />
          ) : (
            <Box sx={{ p: 2 }}>
              <Typography variant="body2" component="pre" sx={{ whiteSpace: 'pre-wrap', fontSize: '0.8rem' }}>
                {JSON.stringify(openMap?.content_json || openMap, null, 2)}
              </Typography>
            </Box>
          )}
        </DialogContent>
      </Dialog>
    </Box>
  );
}

OpsCanvasShelf.propTypes = {
  conversationId: PropTypes.string,
  relatedType: PropTypes.string,
  relatedId: PropTypes.string,
  onOpenInWorkspace: PropTypes.func,
};
