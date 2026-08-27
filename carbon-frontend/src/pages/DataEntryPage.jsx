// File: src/pages/DataEntryPage.jsx
// Data Entry — table data grid; right-panel detail now lives in the global
// contextual inspector drawer (see inspector/tabs/dataEntryTabs.jsx).

import React, { useEffect, useState, useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Box, Button } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useAuth } from '../auth/AuthContext';
import { fetchDataSchemaTables, fetchDataSchemaFields } from '../api/dataschema';
import TableDataPage from '../components/TableDataPage';
import PageHeader from '../components/Page/PageHeader';
import LoadingSkeleton from '../components/Page/LoadingSkeleton';
import useDocumentTitle from '../hooks/useDocumentTitle';
import { useNotes } from '../notes/NotesContext';
import { registerDataEntryInspectorTabs } from '../inspector/tabs/dataEntryTabs';

/* ── Page component ── */

export default function DataEntryPage() {
  useDocumentTitle("Data Entry");
  const { moduleId, tableId } = useParams();
  const navigate = useNavigate();
  const { token, user, context } = useAuth();

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
      fetchDataSchemaTables(token, projectId, moduleId).then((tables) => {
        const list = Array.isArray(tables) ? tables : tables?.results || [];
        return list.find((t) => String(t.id) === String(tableId));
      }),
      fetchDataSchemaFields(token, tableId, projectId, moduleId),
    ])
      .then(([table, fieldData]) => {
        setTableMeta(table || null);
        setFields(Array.isArray(fieldData) ? fieldData : fieldData?.results || []);
      })
      .catch(() => {/* right panel data is non-critical */});
  }, [token, projectId, moduleId, tableId]);

  // ── Contextual Inspector (global drawer) ────────────────────────────────
  const { setContexts } = useNotes();

  // Register the Data Entry table tabs once; unregister on unmount.
  useEffect(() => registerDataEntryInspectorTabs(), []);

  // Expose this table as the active inspector context with a payload fast-path
  // ({ table, module, fields, tableId, moduleId }) for the registered tabs.
  const inspectorContext = useMemo(
    () => [{
      entityType: 'table',
      entityId: tableId,
      label: tableMeta?.name || tableMeta?.title || `Table ${tableId}`,
      payload: { table: tableMeta, module, fields, tableId, moduleId },
    }],
    [tableMeta, module, fields, tableId, moduleId],
  );
  useEffect(() => {
    setContexts(inspectorContext);
    return () => setContexts(null);
  }, [inspectorContext, setContexts]);

  if (!user || !context) {
    return <LoadingSkeleton variant="detail" />;
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', bgcolor: 'background.default' }}>
      <Box sx={{ bgcolor: 'white', px: 2, pt: 1.5, pb: 0 }}>
        <PageHeader
          title="Data Entry"
          subtitle={module?.name || `Module ${moduleId}`}
          description="Enter and edit emission data row by row. Add new records, update values, and attach evidence documents. Use the inspector panel for data quality checks."
          actions={
            <Button
              size="small"
              startIcon={<ArrowBackIcon />}
              onClick={() => navigate(`/carbon/my-data/${moduleId}`)}
              sx={{ color: 'text.secondary' }}
            >
              Back to source
            </Button>
          }
        />
      </Box>
      <Box sx={{ flex: 1, overflow: 'auto', bgcolor: 'white', borderTop: 1, borderColor: 'divider' }}>
        <TableDataPage
          project_id={projectId}
          module_id={moduleId}
          moduleId={moduleId}
          tableId={tableId}
          lang={context.language || 'en'}
          token={token}
        />
      </Box>
    </Box>
  );
}