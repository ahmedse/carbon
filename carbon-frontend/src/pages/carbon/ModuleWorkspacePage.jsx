import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Box, Chip, Divider, Stack, Typography, LinearProgress, useTheme } from '@mui/material';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import { useAuth } from '../../auth/AuthContext';
import { fetchDataSchemaTables } from '../../api/dataschema';
import { fetchOwnerActivity } from '../../api/emissions';
import { CarbonDataGrid, PageHeader, EmptyState, ErrorAlert, LoadingSkeleton } from '../../components';
import EntityDetailShell from '../../components/entity/EntityDetailShell';

const SCOPE_META = {
  1: { label: 'Scope 1', color: 'error' },
  2: { label: 'Scope 2', color: 'warning' },
  3: { label: 'Scope 3', color: 'info' },
};

function fmtDate(v) {
  if (!v) return '—';
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString();
}

/* ── Right panel: Overview tab ── */

function ModuleOverviewTab({ module, tables }) {
  const theme = useTheme();
  const quality = module?.quality_score ?? 0;
  const completion = tables.length > 0
    ? Math.round(((tables.filter((t) => (t.row_count || 0) > 0).length) / tables.length) * 100)
    : 0;
  const missing = tables.filter((t) => (t.row_count || 0) === 0);

  const details = [
    { label: 'Source Name',  value: module?.name },
    { label: 'Scope',        value: SCOPE_META[module?.scope]?.label || '—' },
    { label: 'Tables',       value: tables.length },
    { label: 'Tables with data', value: tables.length - missing.length },
    { label: 'Last entry',   value: fmtDate(module?.last_entry) },
    { label: 'Quality score', value: module?.quality_score != null ? `${Math.round(module.quality_score)}%` : 'N/A' },
  ];

  return (
    <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 2, fontSize: '0.8rem' }}>
      <Typography variant="body2" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.08em', fontSize: '0.68rem' }}>
        Source overview
      </Typography>

      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr', gap: 1.25 }}>
        {details.map(({ label, value }) => (
          <Box
            key={label}
            sx={{ display: 'grid', gridTemplateColumns: '130px 1fr', gap: 1, py: 1, borderBottom: `1px solid ${theme.palette.divider}` }}
          >
            <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.75rem' }}>{label}</Typography>
            <Typography component="span" variant="body2" sx={{ fontWeight: 600, color: 'text.primary', fontSize: '0.82rem' }}>{value}</Typography>
          </Box>
        ))}
      </Box>

      <Box sx={{ pt: 1 }}>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1, fontWeight: 700, fontSize: '0.76rem' }}>
          Completion
        </Typography>
        <LinearProgress variant="determinate" value={completion} sx={{ height: 6, borderRadius: 99, mb: 0.5 }} />
        <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.78rem' }}>
          {completion}% of tables have data
        </Typography>
      </Box>

      <Box sx={{ pt: 1 }}>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1, fontWeight: 700, fontSize: '0.76rem' }}>
          Quality score
        </Typography>
        <Typography variant="body2" sx={{ fontWeight: 600, color: quality >= 80 ? 'success.main' : quality >= 60 ? 'warning.main' : 'error.main', fontSize: '0.82rem' }}>
          {module?.quality_score != null ? `${Math.round(quality)}%` : 'No score available'}
        </Typography>
      </Box>
    </Box>
  );
}

/* ── Right panel: Activity tab ── */

function ModuleActivityTab({ activity }) {
  if (!activity?.length) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary' }}>No recent activity.</Typography>
      </Box>
    );
  }
  return (
    <Box sx={{ p: 1.5 }}>
      <Stack divider={<Divider flexItem />} spacing={0}>
        {activity.map((item, i) => (
          <Box key={item.id ?? i} sx={{ py: 1 }}>
            <Typography sx={{ fontSize: '0.78rem' }}>{item.detail || item.message || 'Updated'}</Typography>
            <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary' }}>{fmtDate(item.timestamp || item.created_at)}</Typography>
          </Box>
        ))}
      </Stack>
    </Box>
  );
}

export default function ModuleWorkspacePage() {
  const navigate = useNavigate();
  const { moduleId } = useParams();
  const { token, context } = useAuth();
  const [tables, setTables] = useState([]);
  const [activity, setActivity] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [metricsTab, setMetricsTab] = useState(0);

  const projectId = context?.project_id || context?.projectId;
  const module = useMemo(
    () => (context?.modules || []).find((item) => String(item.id) === String(moduleId)),
    [context?.modules, moduleId]
  );

  useEffect(() => {
    if (!token || !projectId || !moduleId) return;
    setLoading(true);
    Promise.all([
      fetchDataSchemaTables(token, projectId, moduleId),
      fetchOwnerActivity({ limit: 8 }, token),
    ])
      .then(([tableData, activityData]) => {
        setTables(tableData || []);
        setActivity(activityData || []);
      })
      .catch((err) => {
        setError(err.message || 'Failed to load source workspace');
      })
      .finally(() => setLoading(false));
  }, [moduleId, projectId, token]);

  const _breadcrumb = useMemo(() => [
    { label: 'Home', path: '/dashboard' },
    { label: 'My Data', path: '/carbon/my-data' },
    { label: module?.name || '...' },
  ], [module?.name]);

  const columns = useMemo(() => [
    {
      field: 'title',
      headerName: 'Table Name',
      flex: 2,
      minWidth: 220,
      renderCell: (params) => <Typography sx={{ fontWeight: 600 }}>{params.value || params.row.name}</Typography>,
    },
    {
      field: 'row_count',
      headerName: 'Rows',
      width: 80,
      type: 'number',
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 120,
      renderCell: (params) => (
        <Chip label={params.row.row_count === 0 ? 'No Data' : 'Has Data'} color={params.row.row_count === 0 ? 'default' : 'success'} size="small" />
      ),
    },
    {
      field: 'arrow',
      headerName: '',
      width: 50,
      sortable: false,
      renderCell: () => <ChevronRightIcon fontSize="small" color="action" />,
    },
  ], []);

  if (loading) return <LoadingSkeleton variant="detail" />;
  if (error) return (
    <Box>
      <PageHeader title="Source Workspace" subtitle="Loading workspace" />
      <ErrorAlert message={error} onRetry={() => window.location.reload()} />
    </Box>
  );

  const rightPanelTabs = [
    { label: 'Overview', render: () => <ModuleOverviewTab module={module} tables={tables} /> },
    { label: 'Activity', render: () => <ModuleActivityTab activity={activity} /> },
  ];

  const rightPanelFallback = (
    <Box sx={{ height: '100%', overflow: 'auto' }}>
      <Box sx={{ p: 2 }}>
        <ModuleOverviewTab module={module} tables={tables} />
      </Box>
    </Box>
  );

  return (
    <EntityDetailShell
      header={(
        <PageHeader
          title={module?.name || 'Loading...'}
          subtitle={`${SCOPE_META[module?.scope]?.label || 'Scope'} — ${tables.length} tables, ${module?.row_count || 0} rows`}
          badge={SCOPE_META[module?.scope]?.label ? { label: SCOPE_META[module?.scope]?.label, color: SCOPE_META[module?.scope]?.color } : undefined}
        />
      )}
      mainTabs={[{ label: 'Tables', render: () => (
        <Box sx={{ p: 2 }}>
          {tables.length === 0 ? (
            <EmptyState
              title="No tables defined for this source yet"
              description="Contact your administrator to set up data tables."
            />
          ) : (
            <CarbonDataGrid
              rows={tables}
              columns={columns}
              height={420}
              pageSize={20}
              showColumnToggle={false}
              onRowClick={(params) => navigate(`/carbon/my-data/${moduleId}/${params.row.id}`)}
            />
          )}
        </Box>
      ) }]}
      metricsPanel={rightPanelFallback}
      metricsTabs={rightPanelTabs}
      activeMetricsTab={metricsTab}
      onMetricsTabChange={(event, next) => setMetricsTab(next)}
      panelWidthKey="moduleWorkspace:panelWidth"
    />
  );
}
