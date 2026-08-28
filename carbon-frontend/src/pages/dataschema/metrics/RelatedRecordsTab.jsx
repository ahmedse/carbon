// File: src/pages/dataschema/metrics/RelatedRecordsTab.jsx
// FK-linked related records — smart groups by actual relationships.
// Replaces the old same-table dump with meaningful cross-table discovery.
//
// Algorithm:
//   1. Fetch FK fields for the table (DataField with reference_table != null)
//   2. For each FK where the row has a value, fetch related rows
//   3. Fetch explicit TableRelations (from/to)
//   4. Find temporal neighbors (adjacent period_month rows)
//   5. Build collapsible relationship groups with PanelTable

import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Box,
  Typography,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Chip,
  CircularProgress,
  Alert,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { useNavigate } from 'react-router-dom';
import { authFetch } from '../../../api/api';
import { PanelTable } from '../../../components/panel';

const MAX_FK_GROUPS = 8;

export default function RelatedRecordsTab({ rowId, tableId, token, rowData }) {
  const { t } = useTranslation('dataschema');
  const navigate = useNavigate();
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const discoverRelationships = useCallback(async () => {
    if (!tableId || !token) return;
    setLoading(true);
    setError(null);
    const built = [];

    try {
      // 1. Fetch FK fields
      const fieldsRes = await authFetch(`dataschema/fields/?data_table=${tableId}`, { token });
      let fields = [];
      if (fieldsRes.ok) {
        const data = await fieldsRes.json();
        fields = Array.isArray(data.results) ? data.results : (Array.isArray(data) ? data : []);
      }
      const fkFields = fields.filter(f => f.reference_table != null);

      // 2. Get row values
      const rowVals = rowData?.values || {};
      const periodMonth = rowVals.period_month || rowVals.month || null;

      // 3. For each FK with a value, fetch related rows
      const fkTasks = [];
      for (const fk of fkFields.slice(0, MAX_FK_GROUPS)) {
        const fkValue = rowVals[fk.name];
        if (fkValue == null || fkValue === '') continue;

        fkTasks.push(
          (async () => {
            try {
              const res = await authFetch(
                `dataschema/rows/?data_table=${fk.reference_table}&${encodeURIComponent(fk.name)}=${encodeURIComponent(fkValue)}`,
                { token }
              );
              if (res.ok) {
                const data = await res.json();
                const rows = Array.isArray(data.results) ? data.results : (Array.isArray(data) ? data : []);
                if (rows.length > 0) {
                  let refTableName = t('related.tableNumber', { id: fk.reference_table });
                  try {
                    const tblRes = await authFetch(`dataschema/tables/?id=${fk.reference_table}`, { token });
                    if (tblRes.ok) {
                      const tbls = await tblRes.json();
                      const arr = Array.isArray(tbls.results) ? tbls.results : (Array.isArray(tbls) ? tbls : []);
                      const match = arr.find(t => String(t.id) === String(fk.reference_table));
                      if (match) refTableName = match.title || match.name || refTableName;
                    }
                  } catch { /* use default */ }
                  return {
                    type: 'fk',
                    label: t('related.linkedBy', { name: fk.label || fk.display_name || fk.name }),
                    sharedValue: t('related.sharedValue', { field: fk.label || fk.name, value: fkValue }),
                    tables: [{ name: refTableName, tableId: fk.reference_table, rows }],
                  };
                }
              }
            } catch { /* skip */ }
            return null;
          })()
        );
      }

      // 4. Fetch explicit relations
      fkTasks.push(
        (async () => {
          try {
            const [fromRes, toRes] = await Promise.all([
              authFetch(`dataschema/relations/?from_table=${tableId}`, { token }),
              authFetch(`dataschema/relations/?to_table=${tableId}`, { token }),
            ]);
            const relations = [];
            for (const r of [fromRes, toRes]) {
              if (r.ok) {
                const data = await r.json();
                const items = Array.isArray(data.results) ? data.results : (Array.isArray(data) ? data : []);
                relations.push(...items);
              }
            }
            if (relations.length === 0) return null;
            const relGroups = [];
            for (const rel of relations) {
              const targetTableId = String(rel.from_table) === String(tableId) ? rel.to_table : rel.from_table;
              const targetName = String(rel.from_table) === String(tableId)
                ? (rel.to_table_name || t('related.tableNumber', { id: rel.to_table }))
                : (rel.from_table_name || t('related.tableNumber', { id: rel.from_table }));
              let rows = [];
              try {
                const rowsRes = await authFetch(`dataschema/rows/?data_table=${targetTableId}&page_size=5`, { token });
                if (rowsRes.ok) {
                  const data = await rowsRes.json();
                  rows = Array.isArray(data.results) ? data.results : (Array.isArray(data) ? data : []);
                }
              } catch { /* skip */ }
              relGroups.push({
                type: 'relation',
                label: rel.label || rel.relation_type || t('related.relatedFallback'),
                sharedValue: rel.relation_type || 'reference',
                tables: [{ name: targetName, tableId: targetTableId, rows }],
              });
            }
            return relGroups.length > 0 ? relGroups : null;
          } catch { return null; }
        })()
      );

      // 5. Temporal neighbors
      if (periodMonth) {
        fkTasks.push(
          (async () => {
            try {
              const res = await authFetch(`dataschema/rows/?data_table=${tableId}&ordering=period_month&page_size=100`, { token });
              if (res.ok) {
                const data = await res.json();
                const allRows = Array.isArray(data.results) ? data.results : (Array.isArray(data) ? data : []);
                const idx = allRows.findIndex(r => String(r.id) === String(rowId));
                const neighbors = [];
                if (idx > 0) neighbors.push({ ...allRows[idx - 1], _relation: t('related.previous') });
                if (idx >= 0 && idx < allRows.length - 1) neighbors.push({ ...allRows[idx + 1], _relation: t('related.next') });
                if (neighbors.length > 0) {
                  return {
                    type: 'temporal',
                    label: t('related.temporalNeighbors'),
                    sharedValue: t('related.period', { period: periodMonth }),
                    tables: [{ name: t('related.thisTable'), tableId, rows: neighbors }],
                  };
                }
              }
            } catch { /* skip */ }
            return null;
          })()
        );
      }

      // 6. Wait for all async tasks
      const results = await Promise.allSettled(fkTasks);
      for (const r of results) {
        if (r.status === 'fulfilled' && r.value) {
          if (Array.isArray(r.value)) built.push(...r.value);
          else built.push(r.value);
        }
      }
    } catch (err) {
      console.error('RelatedRecords discovery error:', err);
      setError(t('related.discoverError'));
    }

    setGroups(built);
    setLoading(false);
  }, [tableId, token, rowData, rowId, t]);

  useEffect(() => {
    discoverRelationships();
  }, [discoverRelationships]);

  function renderGroupRows(rows) {
    return rows.map(r => {
      const vals = r.values || {};
      const label = vals.period_month || vals.name || vals.building_id || vals.meter_id || t('related.rowNumber', { id: r.id });
      const detailKeys = Object.keys(vals).filter(k => k !== 'notes' && k !== 'period_month').slice(0, 2);
      return {
        id: r.id,
        label: String(label),
        detail: detailKeys.map(k => `${k}: ${String(vals[k]).substring(0, 15)}`).join(' · '),
        dqScore: r.quality_score ?? null,
        _relation: r._relation || null,
        _tableId: r.data_table || tableId,
      };
    });
  }

  if (loading) {
    return (
      <Box sx={{ p: 3, textAlign: 'center' }}>
        <CircularProgress size={20} />
        <Typography sx={{ fontSize: '0.7rem', color: 'text.disabled', mt: 1 }}>
          {t('related.discovering')}
        </Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 2 }}>
        <Alert severity="warning" sx={{ fontSize: '0.75rem' }}>{error}</Alert>
      </Box>
    );
  }

  if (groups.length === 0) {
    return (
      <Box sx={{ p: 2 }}>
        <Alert severity="info" sx={{ fontSize: '0.75rem' }}>
          {t('related.noneFound')}
        </Alert>
      </Box>
    );
  }

  return (
    <Box>
      <Typography sx={{ fontSize: '0.68rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'text.secondary', mb: 1.5, px: 2, pt: 2 }}>
        {t('related.title')}
      </Typography>

      {groups.map((group, gi) => (
        <Accordion
          key={gi}
          disableGutters
          elevation={0}
          defaultExpanded={gi === 0}
          sx={{
            border: 'none',
            '&:before': { display: 'none' },
            borderBottom: '1px solid',
            borderColor: 'divider',
          }}
        >
          <AccordionSummary
            expandIcon={<ExpandMoreIcon sx={{ fontSize: '1rem' }} />}
            sx={{ minHeight: 36, '& .MuiAccordionSummary-content': { my: 0.5 }, px: 2 }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
              <Typography sx={{ fontSize: '0.72rem', fontWeight: 700 }}>{group.label}</Typography>
              <Chip label={group.sharedValue} size="small" variant="outlined" sx={{ height: 18, fontSize: '0.6rem' }} />
              <Chip label={t('related.rowCount', { count: group.tables.reduce((s, t) => s + t.rows.length, 0) })} size="small" color="primary"
                sx={{ height: 18, fontSize: '0.6rem' }} />
            </Box>
          </AccordionSummary>
          <AccordionDetails sx={{ pt: 0, px: 2, pb: 1.5 }}>
            {group.tables.map((table, ti) => {
              const tableRows = renderGroupRows(table.rows);
              return (
                <Box key={ti} sx={{ mb: ti < group.tables.length - 1 ? 2 : 0 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 1 }}>
                    <Typography sx={{ fontSize: '0.7rem', fontWeight: 600, color: 'text.secondary' }}>
                      {table.name}
                    </Typography>
                    <Chip label={`${tableRows.length}`} size="small" sx={{ height: 16, fontSize: '0.58rem' }} />
                  </Box>
                  <PanelTable
                    dense
                    columns={[
                      {
                        key: 'label',
                        header: t('related.row'),
                        width: group.type === 'temporal' ? '55%' : '50%',
                        render: (v, row) => (
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                            {row._relation && (
                              <Chip label={row._relation} size="small" color="primary" variant="outlined"
                                sx={{ height: 18, fontSize: '0.6rem', mr: 0.5 }} />
                            )}
                            <Typography
                              sx={{ fontSize: '0.72rem', fontWeight: 600, cursor: 'pointer',
                                '&:hover': { color: 'primary.main', textDecoration: 'underline' } }}
                              onClick={() => navigate(`/carbon/my-data/row/${row._tableId || table.tableId}/${row.id}`)}
                            >
                              {v}
                            </Typography>
                          </Box>
                        ),
                      },
                      ...(group.type !== 'temporal' ? [{
                        key: 'detail',
                        header: t('related.values'),
                        width: '35%',
                        render: (v) => (
                          <Typography sx={{ fontSize: '0.65rem', color: 'text.secondary' }}>{v || '—'}</Typography>
                        ),
                      }] : []),
                      {
                        key: 'dqScore',
                        header: t('related.dqScore'),
                        width: '15%',
                        align: 'right',
                        render: (v) => (
                          <Typography sx={{ fontSize: '0.7rem', fontWeight: 700,
                            color: v != null ? (v >= 80 ? 'success.main' : v >= 60 ? 'warning.main' : 'error.main') : 'text.disabled',
                          }}>
                            {v != null ? `${Math.round(v)}%` : '—'}
                          </Typography>
                        ),
                      },
                    ]}
                    rows={tableRows}
                    emptyText={t('related.noRows')}
                  />
                </Box>
              );
            })}
          </AccordionDetails>
        </Accordion>
      ))}
    </Box>
  );
}
