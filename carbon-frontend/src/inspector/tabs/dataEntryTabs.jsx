// src/inspector/tabs/dataEntryTabs.jsx
// Contextual Inspector tabs for a Data Entry table (entityType: 'table').
//
// Lifted out of DataEntryPage (ADR-0019 Phase C). Each tab reads its primary
// data from `context.payload` fast-path ({ table, module, fields, tableId,
// moduleId } supplied by the page) and self-fetches secondary data (DQ metrics,
// asset profile, field metrics, evidence, calculations) using its own token.
//
// `registerDataEntryInspectorTabs()` registers all four tabs; returns an
// unregister function (use as effect cleanup).
/* eslint-disable react-refresh/only-export-components */

import React, { useEffect, useState } from 'react';
import {
  Box,
  Chip,
  CircularProgress,
  Divider,
  Stack,
  Typography,
  useTheme,
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import DescriptionIcon from '@mui/icons-material/Description';
import ErrorIcon from '@mui/icons-material/Error';
import FunctionsIcon from '@mui/icons-material/Functions';
import WarningIcon from '@mui/icons-material/Warning';
import { useAuth } from '../../auth/AuthContext';
import { getTableDQMetrics, getFieldDQMetrics } from '../../api/dq';
import { fetchAssetProfiles } from '../../api/catalog';
import { fetchCalculations } from '../../api/emissions';
import { apiFetch } from '../../api/api';
import { FONT } from '../../theme/themeTokens';
import { registerInspectorTab } from '../InspectorTabRegistry';

function fmtDate(v) {
  if (!v) return '—';
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString();
}

function DetailRow({ label, value }) {
  const theme = useTheme();
  return (
    <Box sx={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: 1, py: 1, borderBottom: `1px solid ${theme.palette.divider}` }}>
      <Typography variant="body2" color="text.secondary" sx={{ ...FONT.body }}>{label}</Typography>
      <Typography component="span" variant="body2" sx={{ ...FONT.cardTitle }}>{value ?? '—'}</Typography>
    </Box>
  );
}

/* ── Row Context tab — DQ + key metadata ───────────────────────────────── */

function RowContextTab({ context }) {
  const { token } = useAuth();
  const { table, module: mod } = context?.payload || {};
  const [dqMetrics, setDqMetrics] = useState(null);
  const [assetProfile, setAssetProfile] = useState(null);

  useEffect(() => {
    if (!table?.id || !token) return;
    getTableDQMetrics(table.id, token)
      .then(setDqMetrics)
      .catch(() => setDqMetrics(null));
    fetchAssetProfiles(token)
      .then((profiles) => {
        const match = (profiles || []).find(
          (p) => p.data_table === table.id || p.name === table.name
        );
        setAssetProfile(match || null);
      })
      .catch(() => setAssetProfile(null));
  }, [table?.id, table?.name, token]);

  const dqScore = dqMetrics?.score ?? assetProfile?.quality_score ?? 0;
  const dqColor = dqScore >= 80 ? 'success.main' : dqScore >= 60 ? 'warning.main' : 'error.main';
  const rows = table?.row_count ?? 0;
  const isLocked = table?.is_locked || assetProfile?.governance?.locked || false;

  return (
    <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Typography variant="body2" color="text.secondary" sx={{ ...FONT.sectionTitle, letterSpacing: '0.08em' }}>
        Row Context
      </Typography>

      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <Box sx={{ position: 'relative', display: 'inline-flex' }}>
          <CircularProgress variant="determinate" value={Math.min(dqScore, 100)} size={64} thickness={5} sx={{ color: dqColor }} />
          <Box sx={{ position: 'absolute', top: 0, left: 0, bottom: 0, right: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Typography variant="body2" sx={{ ...FONT.cardTitle, fontWeight: 700, color: dqColor }}>
              {dqScore > 0 ? `${Math.round(dqScore)}%` : '—'}
            </Typography>
          </Box>
        </Box>
        <Box>
          <Typography sx={{ ...FONT.cardTitle }}>DQ Score</Typography>
          <Chip
            label={dqScore >= 80 ? 'Passing' : dqScore >= 60 ? 'Warning' : dqScore > 0 ? 'Failing' : 'No data'}
            size="small"
            color={dqScore >= 80 ? 'success' : dqScore >= 60 ? 'warning' : dqScore > 0 ? 'error' : 'default'}
            variant="outlined"
            sx={{ mt: 0.5 }}
          />
        </Box>
      </Box>

      <Divider />

      <DetailRow label="Table" value={table?.name || table?.title} />
      <DetailRow label="Module" value={mod?.name} />
      <DetailRow label="Rows" value={rows ? Number(rows).toLocaleString() : '0'} />
      <DetailRow label="Fields" value={table?.field_count ?? '—'} />
      <DetailRow label="Last updated" value={fmtDate(table?.last_updated)} />
      <DetailRow label="Locked" value={isLocked ? 'Yes' : 'No'} />
      {assetProfile?.quality_status && (
        <DetailRow label="Quality status" value={assetProfile.quality_status} />
      )}
    </Box>
  );
}

/* ── Fields+Quality tab — per-field DQ badges ──────────────────────────── */

function FieldsQualityTab({ context }) {
  const { token } = useAuth();
  const { fields } = context?.payload || {};
  const [fieldMetrics, setFieldMetrics] = useState({});

  useEffect(() => {
    if (!token || !fields?.length) return;
    Promise.allSettled(
      fields.map((f) =>
        getFieldDQMetrics(f.id, token).then((m) => [f.id, m]).catch(() => [f.id, null])
      )
    ).then((results) => {
      const map = {};
      results.forEach((r) => { if (r.status === 'fulfilled') { const [id, m] = r.value; map[id] = m; } });
      setFieldMetrics(map);
    });
  }, [token, fields]);

  if (!fields?.length) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography sx={{ ...FONT.body, color: 'text.secondary' }}>No fields defined.</Typography>
      </Box>
    );
  }

  const getDqBadge = (fieldId) => {
    const m = fieldMetrics[fieldId];
    if (!m) return null;
    const score = m.quality_score ?? m.score ?? 0;
    if (!score && score !== 0) return null;
    const color = score >= 80 ? 'success' : score >= 60 ? 'warning' : 'error';
    const Icon = score >= 80 ? CheckCircleIcon : score >= 60 ? WarningIcon : ErrorIcon;
    return (
      <Chip
        icon={<Icon sx={{ fontSize: '0.75rem' }} />}
        label={`${Math.round(score)}%`}
        size="small"
        color={color}
        variant="outlined"
        sx={{ '& .MuiChip-label': { px: 0.5 }, '& .MuiChip-icon': { ml: 0.5 } }}
      />
    );
  };

  return (
    <Box sx={{ p: 1.5 }}>
      <Typography variant="body2" color="text.secondary" sx={{ ...FONT.sectionTitle, letterSpacing: '0.08em', mb: 1.5 }}>
        Fields & Quality
      </Typography>
      <Stack divider={<Divider flexItem />} spacing={0}>
        {fields.map((f) => (
          <Box key={f.id} sx={{ py: 1 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Typography sx={{ ...FONT.cardTitle }}>{f.name}</Typography>
              {getDqBadge(f.id)}
            </Box>
            <Typography sx={{ ...FONT.bodySmall, color: 'text.secondary', mt: 0.25 }}>
              {f.field_type || f.data_type || 'string'}
              {f.is_required ? ' · Required' : ''}
              {f.is_unique ? ' · Unique' : ''}
            </Typography>
            {f.description && (
              <Typography sx={{ ...FONT.bodySmall, color: 'text.disabled', mt: 0.25 }}>{f.description}</Typography>
            )}
          </Box>
        ))}
      </Stack>
    </Box>
  );
}

/* ── Evidence tab — documents attached to this table ────────────────────── */

function EvidenceTab({ context }) {
  const { token } = useAuth();
  const { tableId } = context?.payload || {};
  const [evidence, setEvidence] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token || !tableId) return;
    setLoading(true);
    apiFetch('evidence/?is_deleted=false', { token })
      .then((data) => setEvidence(Array.isArray(data) ? data : (data?.results || [])))
      .catch(() => setEvidence([]))
      .finally(() => setLoading(false));
  }, [token, tableId]);

  if (loading) {
    return (
      <Box sx={{ p: 2, display: 'flex', justifyContent: 'center' }}>
        <CircularProgress size={24} />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Typography variant="body2" color="text.secondary" sx={{ ...FONT.sectionTitle, letterSpacing: '0.08em' }}>
        Evidence
      </Typography>

      {evidence.length === 0 ? (
        <Box sx={{ textAlign: 'center', py: 3 }}>
          <DescriptionIcon sx={{ fontSize: '2rem', color: 'text.disabled', mb: 1 }} />
          <Typography sx={{ ...FONT.body, color: 'text.secondary' }}>
            No evidence documents
          </Typography>
          <Typography sx={{ ...FONT.bodySmall, color: 'text.disabled', mt: 0.5 }}>
            Upload receipts, invoices, or photos from the data row editor
          </Typography>
        </Box>
      ) : (
        <Stack divider={<Divider flexItem />} spacing={0}>
          {evidence.slice(0, 15).map((ev) => (
            <Box key={ev.id} sx={{ py: 1, display: 'flex', gap: 1, alignItems: 'flex-start' }}>
              <DescriptionIcon sx={{ fontSize: '0.875rem', mt: 0.25, color: 'text.secondary', flexShrink: 0 }} />
              <Box sx={{ minWidth: 0 }}>
                <Typography sx={{ ...FONT.cardTitle, lineHeight: 1.35 }}>
                  {ev.original_filename}
                </Typography>
                <Typography sx={{ ...FONT.bodySmall, color: 'text.disabled' }}>
                  {ev.file_size ? `${(ev.file_size / 1024).toFixed(1)} KB` : ''} · {fmtDate(ev.uploaded_at)}
                </Typography>
              </Box>
            </Box>
          ))}
        </Stack>
      )}

      {evidence.length > 15 && (
        <Typography sx={{ ...FONT.bodySmall, color: 'text.disabled', textAlign: 'center' }}>
          +{evidence.length - 15} more documents
        </Typography>
      )}
    </Box>
  );
}

/* ── Calculations tab — calc trace for this table ──────────────────────── */

function CalculationsTab({ context }) {
  const { token } = useAuth();
  const { table, moduleId } = context?.payload || {};
  const [calcs, setCalcs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token || !moduleId) return;
    setLoading(true);
    fetchCalculations({ module_id: moduleId }, token)
      .then((data) => setCalcs(Array.isArray(data) ? data : (data?.results || [])))
      .catch(() => setCalcs([]))
      .finally(() => setLoading(false));
  }, [token, moduleId]);

  const tableCalcs = calcs.filter((c) =>
    c.data_table === table?.id || c.data_table_id === table?.id || c.table_id === table?.id
  );

  if (loading) {
    return (
      <Box sx={{ p: 2, display: 'flex', justifyContent: 'center' }}>
        <CircularProgress size={24} />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Typography variant="body2" color="text.secondary" sx={{ ...FONT.sectionTitle, letterSpacing: '0.08em' }}>
        Calculations
      </Typography>

      {tableCalcs.length === 0 ? (
        <Box sx={{ textAlign: 'center', py: 3 }}>
          <FunctionsIcon sx={{ fontSize: '2rem', color: 'text.disabled', mb: 1 }} />
          <Typography sx={{ ...FONT.body, color: 'text.secondary' }}>
            No calculations found
          </Typography>
          <Typography sx={{ ...FONT.bodySmall, color: 'text.disabled', mt: 0.5 }}>
            Run calculation rules to compute emissions from this data
          </Typography>
        </Box>
      ) : (
        <>
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            <Chip
              icon={<FunctionsIcon sx={{ fontSize: '0.8125rem' }} />}
              label={`${tableCalcs.length} calculations`}
              size="small"
              color="primary"
              variant="outlined"
            />
            {(() => {
              const total = tableCalcs.reduce((sum, c) => sum + (c.co2e_kg || c.total_co2e || 0), 0);
              return (
                <Chip
                  label={`${(total / 1000).toFixed(2)} tCO₂e`}
                  size="small"
                  color="warning"
                  variant="outlined"
                />
              );
            })()}
          </Box>

          <Stack divider={<Divider flexItem />} spacing={0}>
            {tableCalcs.slice(0, 10).map((c, i) => (
              <Box key={c.id ?? i} sx={{ py: 1 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Typography sx={{ ...FONT.cardTitle }}>
                    {c.factor_name || c.factor_code || `Calc #${c.id}`}
                  </Typography>
                  <Typography sx={{ ...FONT.cardTitle, color: 'warning.main' }}>
                    {c.co2e_kg != null ? `${(c.co2e_kg / 1000).toFixed(3)} t` : '—'}
                  </Typography>
                </Box>
                <Typography sx={{ ...FONT.bodySmall, color: 'text.disabled' }}>
                  {c.activity_date || c.calculated_at ? fmtDate(c.activity_date || c.calculated_at) : ''}
                  {c.scope ? ` · Scope ${c.scope}` : ''}
                </Typography>
              </Box>
            ))}
          </Stack>

          {tableCalcs.length > 10 && (
            <Typography sx={{ ...FONT.bodySmall, color: 'text.disabled', textAlign: 'center' }}>
              +{tableCalcs.length - 10} more
            </Typography>
          )}
        </>
      )}
    </Box>
  );
}

/* ── Registration (contribution point) ───────────────────────────────────── */

/** Register all Data Entry table tabs; returns an unregister function. */
export function registerDataEntryInspectorTabs() {
  const unregister = [
    registerInspectorTab({
      id: 'data-entry-context',
      label: 'Row Context',
      order: 10,
      matches: (ctx) => ctx?.entityType === 'table',
      render: (ctx) => <RowContextTab context={ctx} />,
    }),
    registerInspectorTab({
      id: 'data-entry-fields',
      label: 'Fields+Qual',
      order: 20,
      matches: (ctx) => ctx?.entityType === 'table',
      render: (ctx) => <FieldsQualityTab context={ctx} />,
    }),
    registerInspectorTab({
      id: 'data-entry-evidence',
      label: 'Evidence',
      order: 30,
      matches: (ctx) => ctx?.entityType === 'table',
      render: (ctx) => <EvidenceTab context={ctx} />,
    }),
    registerInspectorTab({
      id: 'data-entry-calculations',
      label: 'Calculations',
      order: 40,
      matches: (ctx) => ctx?.entityType === 'table',
      render: (ctx) => <CalculationsTab context={ctx} />,
    }),
  ];
  return () => unregister.forEach((u) => u());
}
