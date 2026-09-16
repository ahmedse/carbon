// src/pages/admin/ai/CapabilitiesPanel.jsx
// Route /admin/ai/capabilities — read-only Capability registry (PEC-R2).
// Also mounted by AIWorkspace Console Capabilities tab.
//
// CBAC: ai:view_console (same gate as Skills / Processes). Read-only — no
// create/edit/delete. RULE_8 tokens; RULE_10 apiFetch via listCapabilities;
// RULE_23 outcome copy in primary labels (host_action only in detail drawer).
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Button,
  Chip,
  CircularProgress,
  Drawer,
  IconButton,
  Paper,
  Stack,
  Typography,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import CloudOffIcon from '@mui/icons-material/CloudOff';
import RefreshIcon from '@mui/icons-material/Refresh';
import useDocumentTitle from '../../../hooks/useDocumentTitle';
import PageContainer from '../../../components/layout/PageContainer';
import CarbonDataGrid from '../../../components/DataGrid/CarbonDataGrid';
import { useAuth } from '../../../auth/AuthContext';
import {
  AI_VIEW_CONSOLE,
  expandCapabilities,
  hasCap,
} from '../../../capabilities';
import { listCapabilities } from '../../../api/aiCatalog';

/** Kind → outcome label (RULE_23 — no engine jargon in primary UI). */
export function kindLabel(kind) {
  if (kind === 'read_only') return 'Look up';
  if (kind === 'human_task') return 'Needs a person';
  if (kind === 'mutation') return 'Changes data';
  if (kind === 'assertion') return 'Verify';
  return kind || '—';
}

function capabilityKeys(caps) {
  if (!Array.isArray(caps)) return [];
  return caps
    .map((c) =>
      typeof c === 'string' ? c : c?.key || c?.capability || c?.code || '',
    )
    .filter(Boolean);
}

function permissionsSummary(permissions) {
  if (!permissions || typeof permissions !== 'object') return '—';
  const parts = [];
  for (const [group, values] of Object.entries(permissions)) {
    if (Array.isArray(values) && values.length) {
      parts.push(`${group}: ${values.join(', ')}`);
    }
  }
  return parts.length ? parts.join(' · ') : '—';
}

export default function CapabilitiesPanel() {
  useDocumentTitle('Capabilities');
  const { token, userCapabilities } = useAuth();

  const caps = useMemo(() => capabilityKeys(userCapabilities), [userCapabilities]);
  const canView = useMemo(
    () => hasCap(expandCapabilities(caps), AI_VIEW_CONSOLE),
    [caps],
  );

  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [selected, setSelected] = useState(null);

  const load = useCallback(async () => {
    if (!canView) {
      setRows([]);
      setLoading(false);
      setOffline(false);
      return;
    }
    setLoading(true);
    try {
      const data = await listCapabilities(token);
      setRows(Array.isArray(data) ? data : []);
      setOffline(false);
      setSelected((prev) => {
        if (!prev) return null;
        const next = (Array.isArray(data) ? data : []).find(
          (r) => r.capability_id === prev.capability_id,
        );
        return next || null;
      });
    } catch {
      setRows([]);
      setOffline(true);
    } finally {
      setLoading(false);
    }
  }, [token, canView]);

  useEffect(() => {
    load();
  }, [load]);

  const columns = useMemo(
    () => [
      {
        field: 'business_name',
        headerName: 'Capability',
        flex: 1,
        minWidth: 180,
      },
      {
        field: 'kind',
        headerName: 'Kind',
        width: 140,
        valueFormatter: (value) => kindLabel(value),
      },
      {
        field: 'purpose',
        headerName: 'Purpose',
        flex: 1.2,
        minWidth: 200,
      },
      {
        field: 'owner',
        headerName: 'Owner',
        width: 110,
      },
      {
        field: 'version',
        headerName: 'Version',
        width: 90,
      },
      {
        field: 'requires_confirmation',
        headerName: 'Confirm',
        width: 100,
        renderCell: ({ value }) => (
          <Chip
            size="small"
            label={value ? 'Yes' : 'No'}
            variant="outlined"
            sx={{
              fontSize: '0.625rem',
              height: 18,
              '& .MuiChip-label': { px: 0.75 },
            }}
          />
        ),
      },
    ],
    [],
  );

  if (!canView) {
    return (
      <PageContainer>
        <Typography color="text.secondary" sx={{ fontSize: '0.8125rem' }}>
          Viewing the capability registry requires ai:view_console.
        </Typography>
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <Stack spacing={1} sx={{ width: '100%', maxWidth: 1200 }}>
        <Stack direction="row" alignItems="center" spacing={1}>
          <Typography variant="h6" sx={{ fontSize: '1rem', fontWeight: 700, flex: 1 }}>
            Capabilities
          </Typography>
          <Button
            size="small"
            startIcon={<RefreshIcon sx={{ fontSize: '0.9375rem' }} />}
            onClick={load}
            disabled={loading}
            sx={{ fontSize: '0.75rem' }}
          >
            Refresh
          </Button>
        </Stack>

        <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
          Governed actions the console can offer. Read-only registry — open a row
          for details.
        </Typography>

        {loading && (
          <Paper
            variant="outlined"
            sx={{ p: 4, display: 'flex', justifyContent: 'center', alignItems: 'center' }}
          >
            <CircularProgress size={28} />
          </Paper>
        )}

        {!loading && offline && (
          <Paper variant="outlined" sx={{ p: 3 }}>
            <Stack spacing={1} alignItems="flex-start">
              <Stack direction="row" spacing={1} alignItems="center">
                <CloudOffIcon sx={{ fontSize: '1.125rem', color: 'text.secondary' }} />
                <Typography variant="body2" fontWeight={600} sx={{ fontSize: '0.8125rem' }}>
                  Capability registry unavailable
                </Typography>
              </Stack>
              <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
                Could not reach the catalog service. Check the API and try again.
              </Typography>
              <Button
                size="small"
                startIcon={<RefreshIcon sx={{ fontSize: '0.9375rem' }} />}
                onClick={load}
              >
                Retry
              </Button>
            </Stack>
          </Paper>
        )}

        {!loading && !offline && (
          <Paper variant="outlined" sx={{ overflow: 'hidden' }}>
            <CarbonDataGrid
              columns={columns}
              rows={rows}
              loading={false}
              getRowId={(row) => row.capability_id}
              pageSize={10}
              pageSizeOptions={[10, 25, 50]}
              density="compact"
              emptyMessage="No capabilities in the registry yet."
              onRowClick={(params) => setSelected(params.row)}
            />
          </Paper>
        )}

        <Drawer
          anchor="right"
          open={Boolean(selected)}
          onClose={() => setSelected(null)}
          PaperProps={{ sx: { width: { xs: '100%', sm: 480 }, p: 2.5 } }}
        >
          {selected && (
            <Stack spacing={1}>
              <Stack direction="row" alignItems="center" spacing={1}>
                <Typography sx={{ fontSize: '1rem', fontWeight: 700, flex: 1 }}>
                  {selected.business_name}
                </Typography>
                <IconButton
                  size="small"
                  onClick={() => setSelected(null)}
                  aria-label="Close detail"
                >
                  <CloseIcon />
                </IconButton>
              </Stack>

              <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                <Chip
                  size="small"
                  label={kindLabel(selected.kind)}
                  sx={{ fontSize: '0.625rem', height: 18 }}
                />
                <Chip
                  size="small"
                  label={selected.requires_confirmation ? 'Needs confirmation' : 'No confirmation'}
                  variant="outlined"
                  sx={{ fontSize: '0.625rem', height: 18 }}
                />
              </Stack>

              <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
                {selected.purpose || 'No purpose described.'}
              </Typography>

              <Stack direction="row" spacing={2} sx={{ flexWrap: 'wrap', rowGap: 0.5 }}>
                <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
                  Owner: <strong>{selected.owner || '—'}</strong>
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6875rem' }}>
                  Version: <strong>{selected.version || '—'}</strong>
                </Typography>
              </Stack>

              <Typography variant="body2" fontWeight={600} sx={{ fontSize: '0.75rem', mt: 1 }}>
                Permissions
              </Typography>
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ fontSize: '0.6875rem', overflowWrap: 'anywhere' }}
              >
                {permissionsSummary(selected.permissions)}
              </Typography>

              <Typography variant="body2" fontWeight={600} sx={{ fontSize: '0.75rem', mt: 1 }}>
                Technical id
              </Typography>
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ fontSize: '0.6875rem', overflowWrap: 'anywhere' }}
                data-testid="capability-host-action"
              >
                {selected.host_action || selected.capability_id || '—'}
              </Typography>
            </Stack>
          )}
        </Drawer>
      </Stack>
    </PageContainer>
  );
}
