import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Box, Chip, IconButton, Tooltip, Typography } from '@mui/material';
import VisibilityIcon from '@mui/icons-material/Visibility';
import { useAuth } from '../../auth/AuthContext';
import { fetchDataSchemaTables } from '../../api/dataschema';
import { fetchOwnerActivity } from '../../api/emissions';
import { CarbonDataGrid, PageHeader, EmptyState, ErrorAlert, LoadingSkeleton } from '../../components';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useNotes } from '../../notes/NotesContext';
import { registerModuleInspectorTabs } from '../../inspector/tabs/moduleTabs';

const SCOPE_META = {
  1: { label: 'Scope 1', color: 'error' },
  2: { label: 'Scope 2', color: 'warning' },
  3: { label: 'Scope 3', color: 'info' },
};

export default function ModuleWorkspacePage() {
  useDocumentTitle("My Data Workspace");
  const navigate = useNavigate();
  const { moduleId } = useParams();
  const { token, context } = useAuth();
  const [tables, setTables] = useState([]);
  const [activity, setActivity] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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
        // DRF list endpoints return {results: [...], count, ...}; unwrap defensively.
        setTables(Array.isArray(tableData) ? tableData : tableData?.results || []);
        setActivity(Array.isArray(activityData) ? activityData : activityData?.results || []);
      })
      .catch((err) => {
        setError(err.message || 'Failed to load source workspace');
      })
      .finally(() => setLoading(false));
  }, [moduleId, projectId, token]);

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
      field: 'actions',
      headerName: '',
      width: 60,
      sortable: false,
      disableColumnMenu: true,
      renderCell: ({ row }) => (
        <Tooltip title="Open table data">
          <IconButton size="small" onClick={(e) => { e.stopPropagation(); navigate(`/carbon/my-data/${moduleId}/${row.id}`); }}>
            <VisibilityIcon sx={{ fontSize: '0.9375rem' }} />
          </IconButton>
        </Tooltip>
      ),
    },
  ], [moduleId, navigate]);

  // ── Contextual Inspector (global drawer) ────────────────────────────────
  const { setContexts } = useNotes();

  // Register the module tabs once; unregister on unmount (the registry is
  // reactive, so the global drawer picks the tabs up automatically).
  useEffect(() => registerModuleInspectorTabs(), []);

  // Expose this module as the active inspector context with a payload fast-path
  // so the registered tabs render from already-fetched data (module/tables/activity).
  const inspectorContext = useMemo(
    () => [{ entityType: 'module', entityId: moduleId, label: module?.name, payload: { module, tables, activity } }],
    [moduleId, module, tables, activity],
  );
  useEffect(() => {
    setContexts(inspectorContext);
    return () => setContexts(null);
  }, [inspectorContext, setContexts]);

  if (loading) return <LoadingSkeleton variant="detail" />;
  if (error) return (
    <Box>
      <PageHeader title="Source Workspace" subtitle="Loading workspace" />
      <ErrorAlert message={error} onRetry={() => window.location.reload()} />
    </Box>
  );

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', bgcolor: 'background.default' }}>
      <Box sx={{ bgcolor: 'white', px: 2, pt: 1.5, pb: 1, borderBottom: '1px solid', borderColor: 'divider' }}>
        <PageHeader
          title={module?.name || 'Loading...'}
          subtitle={`${SCOPE_META[module?.scope]?.label || 'Scope'} — ${tables.length} tables, ${tables.reduce((sum, t) => sum + (t.row_count || 0), 0)} rows`}
          description="Browse, filter, edit, and manage rows in each table. Use the inspector panel for quality checks. Add new rows or import data from CSV."
          badge={SCOPE_META[module?.scope]?.label ? { label: SCOPE_META[module?.scope]?.label, color: SCOPE_META[module?.scope]?.color } : undefined}
        />
      </Box>

      <Box sx={{ flex: 1, overflow: 'auto', p: 2 }}>
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
          />
        )}
      </Box>
    </Box>
  );
}
