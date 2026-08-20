// src/pages/admin/ai/AgentTopologyPanel.jsx
// Route /admin/ai/topology — AI Admin OBSERVE surface: the system's DECLARED
// agent topology (ADR-001), rendered through the shared ForceGraph primitive
// via AgentTopologyGraph. Read-only — no chat, no plan controls (that is the
// Workspace, src/shell/**). RULE_8 tokens only; RULE_10 apiFetch only (via
// src/api/aiCatalog.js); RULE_16 grounded states (loading / offline / empty).
import React, { useEffect, useState } from 'react';
import { Alert, Box, Button, Chip, CircularProgress, Paper, Stack, Typography } from '@mui/material';
import CloudOffIcon from '@mui/icons-material/CloudOff';
import RefreshIcon from '@mui/icons-material/Refresh';
import useDocumentTitle from '../../../hooks/useDocumentTitle';
import PageContainer from '../../../components/layout/PageContainer';
import AgentTopologyGraph from '../../../components/graph/AgentTopologyGraph';
import { useAuth } from '../../../auth/AuthContext';
import { getTopology } from '../../../api/aiCatalog';

export default function AgentTopologyPanel() {
  useDocumentTitle('Agent Topology');
  const { token } = useAuth();

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const payload = await getTopology(token);
      setData(payload);
      setOffline(false);
    } catch {
      setData(null);
      setOffline(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const nodeCount = Array.isArray(data?.nodes) ? data.nodes.length : 0;

  return (
    <PageContainer>
      <Stack spacing={1} sx={{ width: '100%', maxWidth: 1080 }}>
        <Stack direction="row" alignItems="center" spacing={1}>
          <Typography variant="h6" sx={{ fontSize: '1rem', fontWeight: 700, flex: 1 }}>
            Agent Topology
          </Typography>
          {!loading && !offline && (
            <Chip
              size="small"
              variant="outlined"
              label={`${nodeCount} agents declared`}
              sx={{ fontSize: '0.625rem', height: 20 }}
            />
          )}
          <Button
            size="small"
            startIcon={<RefreshIcon sx={{ fontSize: 15 }} />}
            onClick={load}
            disabled={loading}
            sx={{ fontSize: '0.75rem' }}
          >
            Refresh
          </Button>
        </Stack>

        <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
          The system&apos;s declared graph (ADR-001): agents as nodes, declared handoffs as edges.
          Click a node to inspect it. Admin observe surface — read-only.
        </Typography>

        {loading && (
          <Paper variant="outlined" sx={{ p: 4, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
            <CircularProgress size={28} />
          </Paper>
        )}

        {!loading && offline && (
          <Paper variant="outlined" sx={{ p: 3 }}>
            <Stack spacing={1} alignItems="flex-start">
              <Stack direction="row" spacing={1} alignItems="center">
                <CloudOffIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
                <Typography variant="body2" fontWeight={600} sx={{ fontSize: '0.8125rem' }}>
                  Topology unavailable
                </Typography>
              </Stack>
              <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
                Could not reach the catalog service. Check the API and try again.
              </Typography>
              <Button size="small" startIcon={<RefreshIcon sx={{ fontSize: 15 }} />} onClick={load}>
                Retry
              </Button>
            </Stack>
          </Paper>
        )}

        {!loading && !offline && nodeCount === 0 && (
          <Alert severity="info" sx={{ fontSize: '0.75rem' }}>
            No agents registered yet — the declared topology is empty. Agents are registered from the Agents panel.
          </Alert>
        )}

        {!loading && !offline && nodeCount > 0 && (
          <Box>
            <AgentTopologyGraph topology={data} />
          </Box>
        )}
      </Stack>
    </PageContainer>
  );
}
