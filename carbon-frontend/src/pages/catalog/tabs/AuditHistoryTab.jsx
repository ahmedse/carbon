// src/pages/catalog/tabs/AuditHistoryTab.jsx
// Audit history: schema changes (SchemaChangeLog) + governance events.
import React, { useState, useEffect, useCallback } from 'react';
import {
  Box, Table, TableHead, TableBody, TableRow, TableCell, Typography, Chip,
  CircularProgress, Alert, Tabs, Tab, Accordion, AccordionSummary, AccordionDetails,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { useAuth } from '../../../auth/AuthContext';
import { useNotification } from '../../../components/NotificationProvider';
import { DetailTabContent } from '../../../components/detail/DetailMainPanel';
import { fetchSchemaChangeLogs } from '../../../api/dataschema';
import { fetchGovernanceEvents, fetchAssetProfiles } from '../../../api/catalog';

const ACTION_COLOR = {
  add: 'success', create: 'success',
  edit: 'info', update: 'info',
  delete: 'error',
  archive: 'warning', restore: 'default',
};

function unwrap(data) {
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.results)) return data.results;
  return [];
}

function JsonDiff({ before, after }) {
  if (before == null && after == null) return <Typography variant="caption">No details</Typography>;
  return (
    <Box sx={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>
      {before != null && (
        <Box sx={{ mb: 1 }}>
          <Typography variant="caption" color="error.main" fontWeight={600}>Before</Typography>
          <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{JSON.stringify(before, null, 2)}</pre>
        </Box>
      )}
      {after != null && (
        <Box>
          <Typography variant="caption" color="success.main" fontWeight={600}>After</Typography>
          <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{JSON.stringify(after, null, 2)}</pre>
        </Box>
      )}
    </Box>
  );
}

export default function AuditHistoryTab({ tableId }) {
  const { token } = useAuth();
  const { notify } = useNotification();

  const [tab, setTab] = useState(0);
  const [loading, setLoading] = useState(true);
  const [schemaLogs, setSchemaLogs] = useState([]);
  const [schemaError, setSchemaError] = useState(null);
  const [govEvents, setGovEvents] = useState([]);

  const load = useCallback(async () => {
    setLoading(true);
    setSchemaError(null);
    try {
      // Schema change logs (admin-only server-side → may 403).
      try {
        const logs = await fetchSchemaChangeLogs(token, { data_table: tableId });
        setSchemaLogs(unwrap(logs));
      } catch (err) {
        setSchemaError(err.message || 'Schema change log unavailable (admin only)');
        setSchemaLogs([]);
      }

      // Governance events filtered client-side to this table's asset.
      const [assetsData, eventsData] = await Promise.all([
        fetchAssetProfiles(token).catch(() => []),
        fetchGovernanceEvents(token).catch(() => []),
      ]);
      const tid = parseInt(tableId, 10);
      const asset = unwrap(assetsData).find((a) => a.data_table === tid && !a.data_field);
      const events = unwrap(eventsData);
      setGovEvents(asset ? events.filter((e) => e.asset === asset.id) : []);
    } catch (err) {
      notify({ message: err.message || 'Failed to load audit history', type: 'error' });
    } finally {
      setLoading(false);
    }
  }, [token, tableId, notify]);

  useEffect(() => { load(); }, [load]);

  if (loading) {
    return (
      <DetailTabContent>
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}><CircularProgress /></Box>
      </DetailTabContent>
    );
  }

  return (
    <DetailTabContent>
      <Typography variant="h6" gutterBottom>Audit History</Typography>

      <Tabs value={tab} onChange={(e, v) => setTab(v)} sx={{ mb: 2 }}>
        <Tab label={`Schema Changes (${schemaLogs.length})`} />
        <Tab label={`Governance Events (${govEvents.length})`} />
      </Tabs>

      {tab === 0 && (
        <>
          {schemaError && <Alert severity="info" sx={{ mb: 2 }}>{schemaError}</Alert>}
          {schemaLogs.length === 0 && !schemaError ? (
            <Alert severity="info">No schema changes recorded for this table.</Alert>
          ) : schemaLogs.length > 0 && (
            <Box sx={{ overflowX: 'auto' }}>
              <Table size="small">
                <TableHead>
                  <TableRow sx={{ bgcolor: 'grey.100' }}>
                    <TableCell sx={{ fontWeight: 600 }}>Date</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Action</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Field</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>User</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Details</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {schemaLogs.map((log) => (
                    <TableRow key={log.id} sx={{ verticalAlign: 'top' }}>
                      <TableCell>{new Date(log.timestamp).toLocaleString()}</TableCell>
                      <TableCell>
                        <Chip label={log.action} size="small" color={ACTION_COLOR[log.action] || 'default'} variant="outlined" />
                      </TableCell>
                      <TableCell>{log.data_field_label || '—'}</TableCell>
                      <TableCell>{log.user ?? '—'}</TableCell>
                      <TableCell sx={{ minWidth: 220 }}>
                        <Accordion disableGutters elevation={0} sx={{ '&:before': { display: 'none' } }}>
                          <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ px: 0, minHeight: 0 }}>
                            <Typography variant="caption">{log.notes || 'View changes'}</Typography>
                          </AccordionSummary>
                          <AccordionDetails sx={{ px: 0 }}>
                            <JsonDiff before={log.before} after={log.after} />
                          </AccordionDetails>
                        </Accordion>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Box>
          )}
        </>
      )}

      {tab === 1 && (
        govEvents.length === 0 ? (
          <Alert severity="info">No governance events recorded for this table.</Alert>
        ) : (
          <Box sx={{ overflowX: 'auto' }}>
            <Table size="small">
              <TableHead>
                <TableRow sx={{ bgcolor: 'grey.100' }}>
                  <TableCell sx={{ fontWeight: 600 }}>Date</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>Action</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>Entity</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>User</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>Details</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {govEvents.map((ev) => (
                  <TableRow key={ev.id} sx={{ verticalAlign: 'top' }}>
                    <TableCell>{new Date(ev.timestamp).toLocaleString()}</TableCell>
                    <TableCell>
                      <Chip label={ev.action} size="small" color={ACTION_COLOR[ev.action] || 'default'} variant="outlined" />
                    </TableCell>
                    <TableCell>{ev.entity_type || '—'}</TableCell>
                    <TableCell>{ev.user ?? '—'}</TableCell>
                    <TableCell sx={{ minWidth: 220 }}>
                      <Accordion disableGutters elevation={0} sx={{ '&:before': { display: 'none' } }}>
                        <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ px: 0, minHeight: 0 }}>
                          <Typography variant="caption">View changes</Typography>
                        </AccordionSummary>
                        <AccordionDetails sx={{ px: 0 }}>
                          <JsonDiff before={ev.before} after={ev.after} />
                        </AccordionDetails>
                      </Accordion>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Box>
        )
      )}
    </DetailTabContent>
  );
}
