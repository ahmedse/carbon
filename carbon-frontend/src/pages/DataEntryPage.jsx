// File: src/pages/DataEntryPage.jsx
// Data Entry — enterprise three-column layout with EntityDetailShell.
// Main content = TableDataPage grid; right panel = table overview + fields.

import React, { useEffect, useState, useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Box, Divider, Stack, Typography, useTheme } from '@mui/material';
import { useAuth } from '../auth/AuthContext';
import { fetchDataSchemaTables, fetchDataSchemaFields } from '../api/dataschema';
import TableDataPage from '../components/TableDataPage';
import PageHeader from '../components/Page/PageHeader';
import LoadingSkeleton from '../components/Page/LoadingSkeleton';
import EntityDetailShell from '../components/entity/EntityDetailShell';

/* ── Right panel: Overview tab ── */

function TableOverviewTab({ table, module: mod }) {
  const theme = useTheme();
  const rows = table?.row_count ?? 0;
  const details = [
    { label: 'Table Name',   value: table?.name || table?.title },
    { label: 'Module',       value: mod?.name },
    { label: 'Rows',         value: rows ? Number(rows).toLocaleString() : '0' },
    { label: 'Fields',       value: table?.field_count ?? '—' },
    { label: 'Last Updated', value: table?.last_updated ? new Date(table.last_updated).toLocaleDateString() : '—' },
    { label: 'Status',       value: rows > 0 ? 'Has Data' : 'Empty' },
  ];
  return (
    <Box sx={{ p: 1.5, display: 'flex', flexDirection: 'column', gap: 1.25, fontSize: '0.75rem' }}>
      <Typography variant="body2" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.08em', fontSize: '0.68rem' }}>
        Table overview
      </Typography>
      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr', gap: 1.25 }}>
        {details.map(({ label, value }) => (
          <Box key={label} sx={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: 1, py: 1, borderBottom: `1px solid ${theme.palette.divider}` }}>
            <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.68rem' }}>{label}</Typography>
            <Typography component="span" variant="body2" sx={{ fontWeight: 600, fontSize: '0.78rem' }}>{value ?? '—'}</Typography>
          </Box>
        ))}
      </Box>
    </Box>
  );
}

/* ── Right panel: Fields tab ── */

function TableFieldsTab({ fields }) {
  if (!fields?.length) {
    return <Box sx={{ p: 2 }}><Typography sx={{ fontSize: '0.78rem', color: 'text.secondary' }}>No fields defined.</Typography></Box>;
  }
  return (
    <Box sx={{ p: 1.25 }}>
      <Stack divider={<Divider flexItem />} spacing={0}>
        {fields.map((f) => (
          <Box key={f.id} sx={{ py: 1 }}>
            <Typography sx={{ fontWeight: 600, fontSize: '0.8rem' }}>{f.name}</Typography>
            <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary' }}>
              {f.field_type || f.data_type}{f.is_required ? ' · Required' : ''}{f.is_unique ? ' · Unique' : ''}
            </Typography>
            {f.description && <Typography sx={{ fontSize: '0.72rem', color: 'text.secondary', mt: 0.25 }}>{f.description}</Typography>}
          </Box>
        ))}
      </Stack>
    </Box>
  );
}

/* ── Page component ── */

export default function DataEntryPage() {
  const { moduleId, tableId } = useParams();
  const navigate = useNavigate();
  const { token, user, context } = useAuth();
  const _theme = useTheme();

  const [tableMeta, setTableMeta] = useState(null);
  const [fields, setFields] = useState([]);
  const [panelTab, setPanelTab] = useState(0);

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

  if (!user || !context) {
    return <LoadingSkeleton variant="detail" />;
  }

  const rightPanelTabs = [
    { label: 'Overview', render: () => <TableOverviewTab table={tableMeta} module={module} /> },
    { label: 'Fields',   render: () => <TableFieldsTab fields={fields} /> },
  ];

  const rightPanel = (
    <Box sx={{ height: '100%', overflow: 'auto' }}>
      <TableOverviewTab table={tableMeta} module={module} />
    </Box>
  );

  return (
    <EntityDetailShell
      header={
        <PageHeader
          title="Data Entry"
          subtitle={module?.name || `Module ${moduleId}`}
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
      metricsPanel={rightPanel}
      metricsTabs={rightPanelTabs}
      activeMetricsTab={panelTab}
      onMetricsTabChange={(event, next) => setPanelTab(next)}
      panelWidthKey="dataEntry:panelWidth"
    />
  );
}