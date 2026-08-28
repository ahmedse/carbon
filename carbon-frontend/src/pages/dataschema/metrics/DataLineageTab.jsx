// File: src/pages/dataschema/metrics/DataLineageTab.jsx
// Data lineage tab — shows upstream/downstream table relations and change history

import React, { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Box, Typography, Chip, CircularProgress, Alert, Table, TableHead,
  TableBody, TableRow, TableCell, Paper, Accordion, AccordionSummary,
  AccordionDetails, Divider,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import SwapHorizIcon from '@mui/icons-material/SwapHoriz';
import HistoryIcon from '@mui/icons-material/History';
import { useAuth } from '../../../auth/AuthContext';
import { fetchTableRelations, fetchSchemaChangeLogs } from '../../../api/dataschema';
import { fetchDataTables } from '../../../api/dataschema';

const RELATION_LABEL_KEYS = {
  lookup: 'relation.lookup',
  one_to_many: 'relation.oneToMany',
  many_to_many: 'relation.manyToMany',
};

function unwrap(data) {
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.results)) return data.results;
  return [];
}

export default function DataLineageTab({ rowId: _rowId }) {
  const { t } = useTranslation('dataschema');
  const { token } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [relations, setRelations] = useState([]);
  const [schemaLogs, setSchemaLogs] = useState([]);
  const [tableMap, setTableMap] = useState({});

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [rels, logs, tables] = await Promise.all([
        fetchTableRelations(token).catch(() => []),
        fetchSchemaChangeLogs(token).catch(() => []),
        fetchDataTables(token).catch(() => []),
      ]);
      const tMap = {};
      for (const t of unwrap(tables)) {
        tMap[t.id] = t.title;
      }
      setTableMap(tMap);
      setRelations(unwrap(rels));
      setSchemaLogs(unwrap(logs));
    } catch (err) {
      setError(err.message || t('lineage.loadError'));
    } finally {
      setLoading(false);
    }
  }, [token, t]);

  useEffect(() => { load(); }, [load]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return <Alert severity="error">{error}</Alert>;
  }

  const totalRelations = relations.length;
  const totalChanges = schemaLogs.length;

  return (
    <Box>
      {/* Summary */}
      <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap' }}>
        <Paper sx={{ p: 2, flex: 1, minWidth: 180, textAlign: 'center' }}>
          <AccountTreeIcon sx={{ color: 'primary.main', fontSize: '1.75rem', mb: 0.5 }} />
          <Typography variant="h6" fontWeight={700}>{totalRelations}</Typography>
          <Typography variant="caption" color="text.secondary">{t('lineage.relations')}</Typography>
        </Paper>
        <Paper sx={{ p: 2, flex: 1, minWidth: 180, textAlign: 'center' }}>
          <HistoryIcon sx={{ color: 'warning.main', fontSize: '1.75rem', mb: 0.5 }} />
          <Typography variant="h6" fontWeight={700}>{totalChanges}</Typography>
          <Typography variant="caption" color="text.secondary">{t('lineage.schemaChanges')}</Typography>
        </Paper>
        <Paper sx={{ p: 2, flex: 1, minWidth: 180, textAlign: 'center' }}>
          <SwapHorizIcon sx={{ color: 'success.main', fontSize: '1.75rem', mb: 0.5 }} />
          <Typography variant="h6" fontWeight={700}>{Object.keys(tableMap).length}</Typography>
          <Typography variant="caption" color="text.secondary">{t('lineage.trackedTables')}</Typography>
        </Paper>
      </Box>

      {/* Lineage Relations */}
      <Accordion defaultExpanded>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography fontWeight={600}>{t('lineage.tableRelations', { count: totalRelations })}</Typography>
        </AccordionSummary>
        <AccordionDetails>
          {totalRelations === 0 ? (
            <Alert severity="info" sx={{ fontSize: '0.85rem' }}>
              {t('lineage.noRelations')}
            </Alert>
          ) : (
            <Table size="small">
              <TableHead>
                <TableRow sx={{ backgroundColor: 'action.hover' }}>
                  <TableCell fontWeight={600}>{t('lineage.fromTable')}</TableCell>
                  <TableCell fontWeight={600}>{t('lineage.relation')}</TableCell>
                  <TableCell fontWeight={600}>{t('lineage.toTable')}</TableCell>
                  <TableCell fontWeight={600}>{t('lineage.notes')}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {relations.map((rel) => (
                  <TableRow key={rel.id} hover>
                    <TableCell>
                      <Chip label={tableMap[rel.from_table] || t('lineage.tableNumber', { id: rel.from_table })} size="small" />
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={t(RELATION_LABEL_KEYS[rel.relation_type] || rel.relation_type)}
                        size="small"
                        color="primary"
                        variant="outlined"
                      />
                    </TableCell>
                    <TableCell>
                      <Chip label={tableMap[rel.to_table] || t('lineage.tableNumber', { id: rel.to_table })} size="small" />
                    </TableCell>
                    <TableCell>
                      <Typography variant="caption">{rel.notes || '—'}</Typography>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </AccordionDetails>
      </Accordion>

      {/* Schema Change History */}
      <Accordion sx={{ mt: 2 }}>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography fontWeight={600}>{t('lineage.changeHistory', { count: totalChanges })}</Typography>
        </AccordionSummary>
        <AccordionDetails>
          {totalChanges === 0 ? (
            <Alert severity="info" sx={{ fontSize: '0.85rem' }}>
              {t('lineage.noChanges')}
            </Alert>
          ) : (
            <Table size="small">
              <TableHead>
                <TableRow sx={{ backgroundColor: 'action.hover' }}>
                  <TableCell fontWeight={600}>{t('lineage.action')}</TableCell>
                  <TableCell fontWeight={600}>{t('lineage.target')}</TableCell>
                  <TableCell fontWeight={600}>{t('lineage.timestamp')}</TableCell>
                  <TableCell fontWeight={600}>{t('lineage.notes')}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {schemaLogs.slice(0, 50).map((log) => {
                  const target = log.data_table
                    ? tableMap[log.data_table] || t('lineage.tableNumber', { id: log.data_table })
                    : log.data_field
                      ? t('lineage.fieldNumber', { id: log.data_field })
                      : '—';
                  return (
                    <TableRow key={log.id} hover>
                      <TableCell>
                        <Chip label={log.action} size="small" color="info" variant="outlined" />
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">{target}</Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="caption">
                          {log.timestamp ? new Date(log.timestamp).toLocaleString() : '—'}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="caption">{log.notes || '—'}</Typography>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </AccordionDetails>
      </Accordion>
    </Box>
  );
}
