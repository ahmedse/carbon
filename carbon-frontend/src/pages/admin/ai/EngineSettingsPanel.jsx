// src/pages/admin/ai/EngineSettingsPanel.jsx
// Route /admin/ai/engine-settings — read-only engine config & capability
// inventory backed by /ai/pulse/settings/ (secrets redacted server-side).
// Never fabricated: loading spinner, offline paper, then the real sections.
// RULE_8 tokens only; RULE_10 apiFetch only (via src/api/aiPulse.js); RULE_16.
import React, { useEffect, useState } from 'react';
import {
  Box,
  Chip,
  CircularProgress,
  Paper,
  Stack,
  Typography,
} from '@mui/material';
import CloudOffIcon from '@mui/icons-material/CloudOff';
import TuneIcon from '@mui/icons-material/Tune';
import useDocumentTitle from '../../../hooks/useDocumentTitle';
import PageContainer from '../../../components/layout/PageContainer';
import { CarbonDataGrid } from '../../../components/DataGrid';
import { useAuth } from '../../../auth/AuthContext';
import { getSettings } from '../../../api/aiPulse';

/** Defensive scalar formatting: null/undefined -> '—', objects -> JSON. */
function formatValue(value) {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'object') return JSON.stringify(value);
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  return String(value);
}

/** A single read-only key/value row. */
function KvRow({ label, value }) {
  return (
    <Stack
      direction="row"
      spacing={2}
      sx={{ py: 0.5, borderBottom: 1, borderColor: 'divider', '&:last-child': { borderBottom: 0 } }}
    >
      <Typography variant="body2" color="text.secondary" sx={{ width: 260, flexShrink: 0 }}>
        {label}
      </Typography>
      <Typography variant="body2" sx={{ wordBreak: 'break-word' }}>
        {formatValue(value)}
      </Typography>
    </Stack>
  );
}

/** A titled group of key/value rows. */
function KvGroup({ title, entries }) {
  const rows = Array.isArray(entries)
    ? entries
    : Object.entries(entries ?? {});
  if (!rows.length) {
    return (
      <Paper variant="outlined" sx={{ p: 2 }}>
        <Typography variant="overline" color="text.secondary">{title}</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          No data available.
        </Typography>
      </Paper>
    );
  }
  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Typography variant="overline" color="text.secondary">{title}</Typography>
      <Stack spacing={0} sx={{ mt: 1 }}>
        {rows.map(([key, value]) => (
          <KvRow key={key} label={String(key)} value={value} />
        ))}
      </Stack>
    </Paper>
  );
}

/** Chip cloud for list-of-strings sections (agents). */
function ChipList({ title, items }) {
  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Typography variant="overline" color="text.secondary">{title}</Typography>
      {items.length ? (
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mt: 1 }}>
          {items.map((item) => (
            <Chip key={item} size="small" variant="outlined" label={item} />
          ))}
        </Box>
      ) : (
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          No agents registered.
        </Typography>
      )}
    </Paper>
  );
}

/** Kind chip color per tool origin. */
const KIND_COLORS = {
  static: 'default',
  plugin: 'primary',
  workflow: 'secondary',
  mcp: 'info',
};

/** Tool catalog: rich metadata (kind, confirmation, capability, app). */
function ToolsCatalog({ tools }) {
  const rows = (tools ?? []).map((tool, index) => ({
    id: tool.name || `tool-${index}`,
    name: tool.name ?? '—',
    kind: tool.kind ?? 'unknown',
    requiresConfirmation: Boolean(tool.requires_confirmation),
    capability: tool.capability ?? '',
    appIdentifier: tool.app_identifier ?? '',
    description: tool.description ?? '',
  }));

  const columns = [
    {
      field: 'name',
      headerName: 'Tool',
      width: 220,
      renderCell: ({ value }) => (
        <Typography variant="body2" sx={{ fontWeight: 600 }}>{value}</Typography>
      ),
    },
    {
      field: 'kind',
      headerName: 'Kind',
      width: 120,
      renderCell: ({ value }) => (
        <Chip size="small" variant="outlined" color={KIND_COLORS[value] || 'default'} label={value} />
      ),
    },
    {
      field: 'requiresConfirmation',
      headerName: 'Confirm',
      width: 100,
      renderCell: ({ value }) => (
        <Chip
          size="small"
          variant="outlined"
          color={value ? 'warning' : 'success'}
          label={value ? 'confirm' : 'auto'}
        />
      ),
    },
    {
      field: 'capability',
      headerName: 'Capability',
      width: 180,
      renderCell: ({ value }) => (
        <Typography variant="body2" color={value ? 'text.primary' : 'text.secondary'}>
          {value || '—'}
        </Typography>
      ),
    },
    {
      field: 'appIdentifier',
      headerName: 'App',
      width: 110,
      renderCell: ({ value }) => (
        <Typography variant="body2" color={value ? 'text.primary' : 'text.secondary'}>
          {value || '—'}
        </Typography>
      ),
    },
    {
      field: 'description',
      headerName: 'Description',
      flex: 1,
      minWidth: 320,
      renderCell: ({ value }) => (
        <Typography variant="body2" color="text.secondary" sx={{ wordBreak: 'break-word' }}>
          {value || '—'}
        </Typography>
      ),
    },
  ];

  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Typography variant="overline" color="text.secondary">Tools catalog</Typography>
      {rows.length ? (
        <Box sx={{ mt: 1 }}>
          <CarbonDataGrid
            columns={columns}
            rows={rows}
            density="compact"
            showColumnToggle={false}
            emptyMessage="No tools registered."
          />
        </Box>
      ) : (
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          No tools registered.
        </Typography>
      )}
    </Paper>
  );
}

/** MCP servers: name/command/args rows. */
function McpServers({ servers }) {
  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Typography variant="overline" color="text.secondary">MCP servers</Typography>
      {servers.length ? (
        <Stack spacing={0} sx={{ mt: 1 }}>
          {servers.map((server) => (
            <Stack
              key={server.name}
              direction="row"
              spacing={2}
              sx={{ py: 0.5, borderBottom: 1, borderColor: 'divider', '&:last-child': { borderBottom: 0 } }}
            >
              <Typography variant="body2" sx={{ width: 260, flexShrink: 0, fontWeight: 600 }}>
                {server.name}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ wordBreak: 'break-word' }}>
                {server.command ? `${server.command} ${(server.args || []).join(' ')}`.trim() : '—'}
              </Typography>
            </Stack>
          ))}
        </Stack>
      ) : (
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          No MCP servers configured.
        </Typography>
      )}
    </Paper>
  );
}

export default function EngineSettingsPanel() {
  useDocumentTitle('Engine Settings');
  const { token } = useAuth();

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const payload = await getSettings(token);
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

  return (
    <PageContainer>
      <Stack spacing={1.5} sx={{ flex: 1, minHeight: 0 }}>
        <Stack direction="row" spacing={1} alignItems="center">
          <Typography variant="h5" fontWeight={700} sx={{ flex: 1 }}>Engine Settings</Typography>
          {data && !offline && <TuneIcon color="primary" />}
        </Stack>
        <Typography variant="body2" color="text.secondary">
          Effective intelligence-core configuration and capability inventory. Secrets are redacted server-side.
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
              Data unavailable — the Pulse settings API is offline
            </Typography>
          </Paper>
        ) : (
          <>
            <KvGroup title="LLM provider" entries={data.llm ?? {}} />
            <KvGroup title="Limits & guardrails" entries={data.limits ?? {}} />

            <Paper variant="outlined" sx={{ p: 2 }}>
              <Typography variant="overline" color="text.secondary">Cache</Typography>
              <Stack spacing={0} sx={{ mt: 1 }}>
                <KvRow label="ttl_seconds" value={data.cache?.ttl_seconds} />
                <KvRow label="store" value={data.cache?.store ?? {}} />
              </Stack>
            </Paper>

            <Paper variant="outlined" sx={{ p: 2 }}>
              <Typography variant="overline" color="text.secondary">Rate limit</Typography>
              <Stack spacing={0} sx={{ mt: 1 }}>
                <KvRow label="requests_per_minute" value={data.rate_limit} />
              </Stack>
            </Paper>

            <KvGroup title="Routing" entries={data.routing ?? {}} />
            <McpServers servers={data.mcp_servers ?? []} />
            <ToolsCatalog tools={data.tools_catalog ?? []} />
            <ChipList title="Agents" items={data.agents ?? []} />
          </>
        )}
      </Stack>
    </PageContainer>
  );
}
