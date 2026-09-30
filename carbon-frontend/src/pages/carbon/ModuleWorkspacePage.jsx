import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Chip, IconButton, Tooltip } from '@mui/material';
import VisibilityIcon from '@mui/icons-material/Visibility';
import { useAuth } from '../../auth/AuthContext';
import { fetchDataSchemaTables } from '../../api/dataschema';
import { fetchOwnerActivity } from '../../api/emissions';
import { PageHeader, ErrorAlert, LoadingSkeleton } from '../../components';
import FilteredDataGrid from '../../components/FilteredDataGrid';
import PageContainer from '../../components/layout/PageContainer';
import { SCOPE_META } from '../../theme/themeTokens';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useNotes } from '../../notes/NotesContext';
import { registerModuleInspectorTabs } from '../../inspector/tabs/moduleTabs';

export default function ModuleWorkspacePage() {
  useDocumentTitle("My Data Workspace");
  const navigate = useNavigate();
  const { moduleId } = useParams();
  const { token, context } = useAuth();
  const [tables, setTables] = useState([]);
  const [activity, setActivity] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [tableSearch, setTableSearch] = useState('');

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
      renderCell: (params) => params.value || params.row.name,
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
            <VisibilityIcon fontSize="small" />
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

  if (loading) {
    return (
      <PageContainer>
        <PageHeader title="Source Workspace" />
        <LoadingSkeleton variant="detail" />
      </PageContainer>
    );
  }
  if (error) return (
    <PageContainer>
      <PageHeader title="Source Workspace" />
      <ErrorAlert message={error} onRetry={() => window.location.reload()} />
    </PageContainer>
  );

  const scopeMeta = SCOPE_META[module?.scope];

  return (
    <PageContainer>
      <PageHeader
        title={module?.name || 'Source Workspace'}
        subtitle={`${scopeMeta?.label || 'Scope'} — ${tables.length} tables, ${tables.reduce((sum, item) => sum + (item.row_count || 0), 0)} rows`}
        description="Browse, filter, edit, and manage rows in each table. Use the inspector panel for quality checks. Add new rows or import data from CSV."
        badge={scopeMeta ? { label: scopeMeta.label, color: scopeMeta.color } : undefined}
      />
      <FilteredDataGrid
        embedded
        rows={tables.filter((row) => {
          if (!tableSearch) return true;
          const q = tableSearch.toLowerCase();
          return (row.title || row.name || '').toLowerCase().includes(q);
        })}
        columns={columns}
        searchValue={tableSearch}
        onSearchChange={setTableSearch}
        searchPlaceholder="Search tables…"
        onClearFilters={() => setTableSearch('')}
        emptyMessage="No tables defined for this source yet"
        emptySubtext="Contact your administrator to set up data tables."
      />
    </PageContainer>
  );
}
