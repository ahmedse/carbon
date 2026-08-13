// src/pages/admin/ai/PulseArchetypesPanel.jsx
// Lists the vendored engine's declarative archetype bundles (filesystem
// read-only, via /ai/pulse/archetypes/). Never fabricated: loading spinner,
// offline paper, grounded empty state, then the real bundle list.
// RULE_8 tokens only; RULE_10 apiFetch only (via src/api/aiPulse.js); RULE_16.
import React, { useEffect, useMemo, useState } from 'react';
import { Box, Chip, CircularProgress, Paper, Stack, Typography } from '@mui/material';
import CloudOffIcon from '@mui/icons-material/CloudOff';
import useDocumentTitle from '../../../hooks/useDocumentTitle';
import PageContainer from '../../../components/layout/PageContainer';
import CarbonDataGrid from '../../../components/DataGrid/CarbonDataGrid';
import { useAuth } from '../../../auth/AuthContext';
import { getPulseArchetypes } from '../../../api/aiPulse';

export default function PulseArchetypesPanel() {
  useDocumentTitle('Archetypes');
  const { token } = useAuth();

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const payload = await getPulseArchetypes(token);
        if (!cancelled) {
          setData(payload);
          setOffline(false);
        }
      } catch {
        if (!cancelled) {
          setData(null);
          setOffline(true);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  const bundles = data?.bundles ?? [];
  const columns = useMemo(
    () => [
      { field: 'name', headerName: 'Bundle', minWidth: 240, flex: 1 },
      { field: 'kind', headerName: 'Kind', width: 140 },
    ],
    []
  );

  return (
    <PageContainer>
      <Stack spacing={1} sx={{ flex: 1, minHeight: 0 }}>
        <Stack direction="row" spacing={1} alignItems="center">
          <Typography variant="h5" fontWeight={700} sx={{ flex: 1 }}>Archetypes</Typography>
          {data && !offline && (
            <Chip size="small" variant="outlined" label={`${bundles.length} bundles`} />
          )}
        </Stack>
        <Typography variant="body2" color="text.secondary">
          Declarative engine bundles vendored with the platform. Read-only listing.
        </Typography>

        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
            <CircularProgress size={24} />
          </Box>
        ) : offline || !data ? (
          <Paper variant="outlined" sx={{ p: 4, textAlign: 'center' }}>
            <CloudOffIcon fontSize="large" sx={{ color: 'text.secondary' }} />
            <Typography variant="subtitle1" sx={{ mt: 1 }} fontWeight={600}>
              Data unavailable
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              Data unavailable — the Pulse read API is offline
            </Typography>
          </Paper>
        ) : bundles.length === 0 ? (
          <Paper variant="outlined" sx={{ p: 4, textAlign: 'center' }}>
            <Typography variant="subtitle1" fontWeight={600}>Archetypes</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              No engine archetype bundles found.
            </Typography>
          </Paper>
        ) : (
          <Paper variant="outlined" sx={{ flex: 1, minHeight: 0 }}>
            <CarbonDataGrid
              columns={columns}
              rows={bundles}
              getRowId={(row) => row.name}
              emptyMessage="No engine archetype bundles found."
            />
          </Paper>
        )}
      </Stack>
    </PageContainer>
  );
}
