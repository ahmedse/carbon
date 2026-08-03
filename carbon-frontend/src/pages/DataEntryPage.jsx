// File: src/pages/DataEntryPage.jsx
// Data Entry — enterprise three-column layout with EntityDetailShell.
// Main content = TableDataPage grid; right panel = table overview + fields.

import React, { useEffect, useState, useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Box, Chip, CircularProgress, Divider, LinearProgress, Stack, Typography, useTheme } from '@mui/material';
import AssessmentIcon from '@mui/icons-material/Assessment';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import DescriptionIcon from '@mui/icons-material/Description';
import ErrorIcon from '@mui/icons-material/Error';
import FunctionsIcon from '@mui/icons-material/Functions';
import WarningIcon from '@mui/icons-material/Warning';
import { useAuth } from '../auth/AuthContext';
import { fetchDataSchemaTables, fetchDataSchemaFields } from '../api/dataschema';
import { getTableDQMetrics, getFieldDQMetrics } from '../api/dq';
import { fetchAssetProfiles } from '../api/catalog';
import { fetchCalculations } from '../api/emissions';
import { apiFetch } from '../api/api';
import TableDataPage from '../components/TableDataPage';
import PageHeader from '../components/Page/PageHeader';
import LoadingSkeleton from '../components/Page/LoadingSkeleton';
import EntityDetailShell from '../components/entity/EntityDetailShell';
import useDetailPanel from '../components/entity/useDetailPanel';
import useDocumentTitle from '../hooks/useDocumentTitle';

/* ── Shared helpers ────────────────────────────────────────────────────── */

function fmtDate(v) {
  if (!v) return '—';
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString();
}

function DetailRow({ label, value, theme }) {
  return (
    <Box sx={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: 1, py: 1, borderBottom: `1px solid ${theme.palette.divider}` }}>
      <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.68rem' }}>{label}</Typography>
      <Typography component="span" variant="body2" sx={{ fontWeight: 600, fontSize: '0.78rem' }}>{value ?? '—'}</Typography>
    </Box>
  );
}

/* ── Row Context tab — DQ + key metadata ───────────────────────────────── */

function RowContextTab({ table, module: mod, token }) {
  const theme = useTheme();
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
      <Typography variant="body2" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.08em', fontSize: '0.68rem' }}>
        Row Context
      </Typography>

      {/* DQ Gauge */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <Box sx={{ position: 'relative', display: 'inline-flex' }}>
          <CircularProgress variant="determinate" value={Math.min(dqScore, 100)} size={64} thickness={5} sx={{ color: dqColor }} />
          <Box sx={{ position: 'absolute', top: 0, left: 0, bottom: 0, right: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Typography variant="body2" sx={{ fontWeight: 700, fontSize: '0.78rem', color: dqColor }}>
              {dqScore > 0 ? `${Math.round(dqScore)}%` : '—'}
            </Typography>
          </Box>
        </Box>
        <Box>
          <Typography sx={{ fontSize: '0.75rem', fontWeight: 600 }}>DQ Score</Typography>
          <Chip
            label={dqScore >= 80 ? 'Passing' : dqScore >= 60 ? 'Warning' : dqScore > 0 ? 'Failing' : 'No data'}
            size="small"
            color={dqScore >= 80 ? 'success' : dqScore >= 60 ? 'warning' : dqScore > 0 ? 'error' : 'default'}
            variant="outlined"
            sx={{ height: 20, fontSize: '0.68rem', mt: 0.5 }}
          />
        </Box>
      </Box>

      <Divider />

      <DetailRow label="Table" value={table?.name || table?.title} theme={theme} />
      <DetailRow label="Module" value={mod?.name} theme={theme} />
      <DetailRow label="Rows" value={rows ? Number(rows).toLocaleString() : '0'} theme={theme} />
      <DetailRow label="Fields" value={table?.field_count ?? '—'} theme={theme} />
      <DetailRow label="Last updated" value={fmtDate(table?.last_updated)} theme={theme} />
      <DetailRow label="Locked" value={isLocked ? 'Yes' : 'No'} theme={theme} />
      {assetProfile?.quality_status && (
        <DetailRow label="Quality status" value={assetProfile.quality_status} theme={theme} />
      )}
    </Box>
  );
}

/* ── Fields+Quality tab — per-field DQ badges ──────────────────────────── */

function FieldsQualityTab({ fields, token }) {
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
        <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary' }}>No fields defined.</Typography>
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
        icon={<Icon sx={{ fontSize: '12px !important' }} />}
        label={`${Math.round(score)}%`}
        size="small"
        color={color}
        variant="outlined"
        sx={{ height: 18, fontSize: '0.62rem', '& .MuiChip-label': { px: 0.5 }, '& .MuiChip-icon': { ml: '3px' } }}
      />
    );
  };

  return (
    <Box sx={{ p: 1.5 }}>
      <Typography variant="body2" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.08em', fontSize: '0.68rem', mb: 1.5 }}>
        Fields & Quality
      </Typography>
      <Stack divider={<Divider flexItem />} spacing={0}>
        {fields.map((f) => (
          <Box key={f.id} sx={{ py: 1 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Typography sx={{ fontWeight: 600, fontSize: '0.8rem' }}>{f.name}</Typography>
              {getDqBadge(f.id)}
            </Box>
            <Typography sx={{ fontSize: '0.68rem', color: 'text.secondary', mt: 0.25 }}>
              {f.field_type || f.data_type || 'string'}
              {f.is_required ? ' · Required' : ''}
              {f.is_unique ? ' · Unique' : ''}
            </Typography>
            {f.description && (
              <Typography sx={{ fontSize: '0.68rem', color: 'text.disabled', mt: 0.25 }}>{f.description}</Typography>
            )}
          </Box>
        ))}
      </Stack>
    </Box>
  );
}

/* ── Evidence tab — documents attached to this table ────────────────────── */

function EvidenceTab({ tableId, token }) {
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
      <Typography variant="body2" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.08em', fontSize: '0.68rem' }}>
        Evidence
      </Typography>

      {evidence.length === 0 ? (
        <Box sx={{ textAlign: 'center', py: 3 }}>
          <DescriptionIcon sx={{ fontSize: 32, color: 'text.disabled', mb: 1 }} />
          <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary' }}>
            No evidence documents
          </Typography>
          <Typography sx={{ fontSize: '0.68rem', color: 'text.disabled', mt: 0.5 }}>
            Upload receipts, invoices, or photos from the data row editor
          </Typography>
        </Box>
      ) : (
        <Stack divider={<Divider flexItem />} spacing={0}>
          {evidence.slice(0, 15).map((ev) => (
            <Box key={ev.id} sx={{ py: 1, display: 'flex', gap: 1, alignItems: 'flex-start' }}>
              <DescriptionIcon sx={{ fontSize: 14, mt: '2px', color: 'text.secondary', flexShrink: 0 }} />
              <Box sx={{ minWidth: 0 }}>
                <Typography sx={{ fontSize: '0.72rem', fontWeight: 600, lineHeight: 1.35 }}>
                  {ev.original_filename}
                </Typography>
                <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled' }}>
                  {ev.file_size ? `${(ev.file_size / 1024).toFixed(1)} KB` : ''} · {fmtDate(ev.uploaded_at)}
                </Typography>
              </Box>
            </Box>
          ))}
        </Stack>
      )}

      {evidence.length > 15 && (
        <Typography sx={{ fontSize: '0.68rem', color: 'text.disabled', textAlign: 'center' }}>
          +{evidence.length - 15} more documents
        </Typography>
      )}
    </Box>
  );
}

/* ── Calculations tab — calc trace for this table ──────────────────────── */

function CalculationsTab({ table, moduleId, token }) {
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
      <Typography variant="body2" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.08em', fontSize: '0.68rem' }}>
        Calculations
      </Typography>

      {tableCalcs.length === 0 ? (
        <Box sx={{ textAlign: 'center', py: 3 }}>
          <FunctionsIcon sx={{ fontSize: 32, color: 'text.disabled', mb: 1 }} />
          <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary' }}>
            No calculations found
          </Typography>
          <Typography sx={{ fontSize: '0.68rem', color: 'text.disabled', mt: 0.5 }}>
            Run calculation rules to compute emissions from this data
          </Typography>
        </Box>
      ) : (
        <>
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            <Chip
              icon={<FunctionsIcon sx={{ fontSize: 13 }} />}
              label={`${tableCalcs.length} calculations`}
              size="small"
              color="primary"
              variant="outlined"
              sx={{ height: 22, fontSize: '0.65rem' }}
            />
            {(() => {
              const total = tableCalcs.reduce((sum, c) => sum + (c.co2e_kg || c.total_co2e || 0), 0);
              return (
                <Chip
                  label={`${(total / 1000).toFixed(2)} tCO₂e`}
                  size="small"
                  color="warning"
                  variant="outlined"
                  sx={{ height: 22, fontSize: '0.65rem' }}
                />
              );
            })()}
          </Box>

          <Stack divider={<Divider flexItem />} spacing={0}>
            {tableCalcs.slice(0, 10).map((c, i) => (
              <Box key={c.id ?? i} sx={{ py: 1 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Typography sx={{ fontSize: '0.72rem', fontWeight: 600 }}>
                    {c.factor_name || c.factor_code || `Calc #${c.id}`}
                  </Typography>
                  <Typography sx={{ fontSize: '0.7rem', fontWeight: 700, color: 'warning.main' }}>
                    {c.co2e_kg != null ? `${(c.co2e_kg / 1000).toFixed(3)} t` : '—'}
                  </Typography>
                </Box>
                <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled' }}>
                  {c.activity_date || c.calculated_at ? fmtDate(c.activity_date || c.calculated_at) : ''}
                  {c.scope ? ` · Scope ${c.scope}` : ''}
                </Typography>
              </Box>
            ))}
          </Stack>

          {tableCalcs.length > 10 && (
            <Typography sx={{ fontSize: '0.68rem', color: 'text.disabled', textAlign: 'center' }}>
              +{tableCalcs.length - 10} more
            </Typography>
          )}
        </>
      )}
    </Box>
  );
}

/* ── Page component ── */

export default function DataEntryPage() {
  useDocumentTitle("Data Entry");
  const { moduleId, tableId } = useParams();
  const navigate = useNavigate();
  const { token, user, context } = useAuth();
  const _theme = useTheme();

  const [tableMeta, setTableMeta] = useState(null);
  const [fields, setFields] = useState([]);

  const module = useMemo(
    () => (context?.modules || []).find((m) => String(m.id) === String(moduleId)),
    [context?.modules, moduleId],
  );

  const projectId = context?.project_id || context?.projectId;

  useEffect(() => {
    if (!token || !projectId || !moduleId || !tableId) return;
    Promise.all([
      fetchDataSchemaTables(token, projectId, moduleId).then((tables) =>
        (tables || []).find((t) => String(t.id) === String(tableId)),
      ),
      fetchDataSchemaFields(token, tableId, projectId, moduleId),
    ])
      .then(([table, fieldData]) => {
        setTableMeta(table || null);
        setFields(fieldData || []);
      })
      .catch(() => {/* right panel data is non-critical */});
  }, [token, projectId, moduleId, tableId]);

  const { metricsPanel, metricsTabs, activeMetricsTab, onMetricsTabChange } = useDetailPanel({
    tabs: [
      { label: 'Row Context',  description: 'Data quality scores, asset profile, and key metadata for this table', render: () => <RowContextTab table={tableMeta} module={module} token={token} /> },
      { label: 'Fields+Qual',  description: 'Field-level completeness, uniqueness, and data type validation', render: () => <FieldsQualityTab fields={fields} token={token} /> },
      { label: 'Evidence',     description: 'Uploaded documents, certificates, and audit trail for this table', render: () => <EvidenceTab tableId={tableId} token={token} /> },
      { label: 'Calculations', description: 'Emission factor calculations linked to this table data', render: () => <CalculationsTab table={tableMeta} moduleId={moduleId} token={token} /> },
    ],
    storageKey: 'dataEntry:panelTab',
    configurable: true,
  });

  if (!user || !context) {
    return <LoadingSkeleton variant="detail" />;
  }

  return (
    <EntityDetailShell
      header={
        <PageHeader
          title="Data Entry"
          subtitle={module?.name || `Module ${moduleId}`}
          description="Enter and edit emission data row by row. Add new records, update values, and attach evidence documents. Use the right panel for data quality checks."
          actions={
            <Box
              component="button"
              onClick={() => navigate(`/carbon/my-data/${moduleId}`)}
              sx={{ border: 'none', background: 'transparent', cursor: 'pointer', color: 'text.secondary', fontSize: '0.8125rem', '&:hover': { color: 'text.primary' } }}
            >
              ← Back to source
            </Box>
          }
        />
      }
      mainContent={
        <TableDataPage
          project_id={projectId}
          module_id={moduleId}
          moduleId={moduleId}
          tableId={tableId}
          lang={context.language || 'en'}
          token={token}
        />
      }
      metricsPanel={metricsPanel}
      metricsTabs={metricsTabs}
      activeMetricsTab={activeMetricsTab}
      onMetricsTabChange={onMetricsTabChange}
      panelWidthKey="dataEntry:panelWidth"
    />
  );
}