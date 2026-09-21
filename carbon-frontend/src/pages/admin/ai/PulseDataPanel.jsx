// src/pages/admin/ai/PulseDataPanel.jsx
// Generic read-only Pulse console panel — renders model-backed rows from the
// /ai/pulse/data/<key>/ read API. Never fabricates data: loading spinner,
// offline paper, grounded empty state, then the real rows in a DataGrid.
// Thin-grid deepen: curated columns, type filter, refresh, Evidence deep-link.
// RULE_8 tokens only; RULE_10 apiFetch only (via src/api/aiPulse.js); RULE_16.
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  Drawer,
  IconButton,
  Paper,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material';
import CloudOffIcon from '@mui/icons-material/CloudOff';
import CloseIcon from '@mui/icons-material/Close';
import RefreshIcon from '@mui/icons-material/Refresh';
import VisibilityOutlinedIcon from '@mui/icons-material/VisibilityOutlined';
import TravelExploreIcon from '@mui/icons-material/TravelExplore';
import { Link as RouterLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import useDocumentTitle from '../../../hooks/useDocumentTitle';
import PageContainer from '../../../components/layout/PageContainer';
import CarbonDataGrid from '../../../components/DataGrid/CarbonDataGrid';
import { useAuth } from '../../../auth/AuthContext';
import { getPulseData } from '../../../api/aiPulse';
import {
  formatCellValue,
  buildScopeLabel,
  buildDetailFields,
  listRowTypes,
  buildEvidenceHref,
  resolveColumnFields,
} from './pulseFormat';

/** Read-only detail drawer — the full record of the clicked Pulse row. */
function PulseDetailDrawer({ row, onClose }) {
  const { t } = useTranslation('ai');
  if (!row) return null;
  const fields = buildDetailFields(row);
  const rawJson = JSON.stringify(row, null, 2);
  const evidenceHref = buildEvidenceHref(row);

  return (
    <Drawer
      anchor="right"
      open
      onClose={onClose}
      PaperProps={{ sx: { width: { xs: '100%', sm: 560 }, p: 3 } }}
    >
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 2 }}>
        <Stack direction="row" spacing={1} alignItems="center">
          <Chip size="small" variant="outlined" label={row._type ?? 'record'} />
          <Typography sx={{ fontSize: '1rem', fontWeight: 700 }}>
            {row.id ?? row.conversation_id ?? row.name ?? t('control.pulseData.recordDetail')}
          </Typography>
        </Stack>
        <IconButton size="small" onClick={onClose} aria-label={t('control.pulseData.closeDetail')}>
          <CloseIcon />
        </IconButton>
      </Stack>

      {evidenceHref ? (
        <Button
          size="small"
          component={RouterLink}
          to={evidenceHref}
          variant="outlined"
          startIcon={<TravelExploreIcon />}
          sx={{ mb: 2, alignSelf: 'flex-start' }}
          onClick={onClose}
        >
          {t('control.pulseData.openInEvidence')}
        </Button>
      ) : null}

      <Divider sx={{ mb: 2 }} />

      {fields.length ? (
        <Stack spacing={1} sx={{ mb: 2 }}>
          {fields.map(({ key, value }) => (
            <Stack key={key} direction="row" spacing={1} alignItems="flex-start">
              <Typography
                variant="body2"
                sx={{
                  fontWeight: 600,
                  minWidth: 140,
                  flexShrink: 0,
                  color: 'text.secondary',
                }}
              >
                {key}
              </Typography>
              <Typography variant="body2" sx={{ overflowWrap: 'anywhere', flex: 1 }}>
                {value}
              </Typography>
            </Stack>
          ))}
        </Stack>
      ) : (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {t('control.pulseData.noScalar')}
        </Typography>
      )}

      <Divider sx={{ mb: 1 }} />
      <Typography variant="caption" color="text.secondary" sx={{ mb: 1 }}>
        {t('control.pulseData.rawJson')}
      </Typography>
      <Box
        component="pre"
        sx={{
          m: 0,
          p: 1.5,
          borderRadius: 1,
          bgcolor: 'action.hover',
          fontSize: '0.75rem',
          lineHeight: 1.5,
          overflow: 'auto',
          maxHeight: '50vh',
          whiteSpace: 'pre-wrap',
          overflowWrap: 'anywhere',
        }}
      >
        {rawJson}
      </Box>
    </Drawer>
  );
}

PulseDetailDrawer.propTypes = {
  row: PropTypes.object,
  onClose: PropTypes.func.isRequired,
};

PulseDetailDrawer.defaultProps = {
  row: null,
};

export default function PulseDataPanel({ title, description, dataKey, emptyHint, links }) {
  const { t } = useTranslation('ai');
  useDocumentTitle(title);
  const { token } = useAuth();

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [selected, setSelected] = useState(null);
  const [typeFilter, setTypeFilter] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const payload = await getPulseData(token, dataKey);
      setData(payload);
      setOffline(false);
    } catch {
      setData(null);
      setOffline(true);
    } finally {
      setLoading(false);
    }
  }, [token, dataKey]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const payload = await getPulseData(token, dataKey);
        if (!cancelled) {
          setData(payload);
          setOffline(false);
        }
      } catch {
        if (!cancelled) {
          setData(null);
          setOffline(true);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, dataKey]);

  useEffect(() => {
    setTypeFilter('');
  }, [dataKey]);

  const rows = useMemo(() => data?.results ?? [], [data?.results]);
  const types = useMemo(() => listRowTypes(rows), [rows]);
  const filteredRows = useMemo(() => {
    if (!typeFilter) return rows;
    return rows.filter((row) => String(row._type) === typeFilter);
  }, [rows, typeFilter]);

  const columns = useMemo(() => {
    if (!filteredRows.length && !rows.length) return [];
    const fieldKeys = resolveColumnFields(dataKey, filteredRows.length ? filteredRows : rows);
    return [
      {
        field: '_actions',
        headerName: '',
        width: 88,
        sortable: false,
        filterable: false,
        renderCell: ({ row }) => {
          const href = buildEvidenceHref(row);
          return (
            <Stack direction="row" spacing={0}>
              <Tooltip title={t('control.pulseData.inspectRecord')}>
                <IconButton
                  size="small"
                  aria-label={t('control.pulseData.inspectRecord')}
                  onClick={(event) => {
                    event.stopPropagation();
                    setSelected(row);
                  }}
                >
                  <VisibilityOutlinedIcon fontSize="small" />
                </IconButton>
              </Tooltip>
              {href ? (
                <Tooltip title={t('control.pulseData.openInEvidence')}>
                  <IconButton
                    size="small"
                    aria-label={t('control.pulseData.openInEvidence')}
                    component={RouterLink}
                    to={href}
                    onClick={(event) => event.stopPropagation()}
                  >
                    <TravelExploreIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              ) : null}
            </Stack>
          );
        },
      },
      {
        field: '_type',
        headerName: t('control.pulseData.colType'),
        width: 140,
        sortable: true,
        renderCell: ({ value }) => <Chip size="small" variant="outlined" label={value} />,
      },
      {
        field: 'scope',
        headerName: t('control.pulseData.colScope'),
        width: 200,
        sortable: false,
        renderCell: ({ row }) => (
          <Typography
            variant="body2"
            sx={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '100%' }}
          >
            {buildScopeLabel(row)}
          </Typography>
        ),
      },
      ...fieldKeys.map((key) => ({
        field: key,
        headerName: key,
        minWidth: 140,
        flex: 1,
        renderCell: (params) => (
          <Typography
            variant="body2"
            sx={{ display: 'block', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '100%' }}
          >
            {formatCellValue(params.row[key])}
          </Typography>
        ),
      })),
    ];
  }, [dataKey, filteredRows, rows, t]);

  return (
    <PageContainer>
      <Stack spacing={1} sx={{ flex: 1, minHeight: 0 }}>
        <Stack direction="row" spacing={1} alignItems="center">
          <Typography variant="h5" fontWeight={700} sx={{ flex: 1 }}>{title}</Typography>
          {data && !offline && (
            <Chip size="small" variant="outlined" label={`${filteredRows.length} / ${data.count} rows`} />
          )}
          <Button
            size="small"
            startIcon={<RefreshIcon />}
            onClick={load}
            disabled={loading}
          >
            {t('control.pulseData.refresh')}
          </Button>
        </Stack>
        {description && (
          <Typography variant="body2" color="text.secondary">
            {description}
          </Typography>
        )}
        {Array.isArray(links) && links.length > 0 ? (
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            {links.map((link) => (
              <Button
                key={link.to}
                size="small"
                component={RouterLink}
                to={link.to}
                variant="outlined"
              >
                {link.label}
              </Button>
            ))}
          </Stack>
        ) : null}

        {types.length > 1 ? (
          <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
            <Chip
              size="small"
              label={t('control.pulseData.allTypes')}
              color={typeFilter === '' ? 'primary' : 'default'}
              variant={typeFilter === '' ? 'filled' : 'outlined'}
              onClick={() => setTypeFilter('')}
            />
            {types.map((typeName) => (
              <Chip
                key={typeName}
                size="small"
                label={typeName}
                color={typeFilter === typeName ? 'primary' : 'default'}
                variant={typeFilter === typeName ? 'filled' : 'outlined'}
                onClick={() => setTypeFilter(typeName)}
              />
            ))}
          </Stack>
        ) : null}

        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
            <CircularProgress size={24} />
          </Box>
        ) : offline || !data ? (
          <Paper variant="outlined" sx={{ p: 4, textAlign: 'center' }}>
            <CloudOffIcon fontSize="large" sx={{ color: 'text.secondary' }} />
            <Typography variant="subtitle1" sx={{ mt: 1 }} fontWeight={600}>
              {t('control.pulseData.dataUnavailable')}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              {t('control.pulseData.offline')}
            </Typography>
          </Paper>
        ) : filteredRows.length === 0 ? (
          <Paper variant="outlined" sx={{ p: 4, textAlign: 'center' }}>
            <Typography variant="subtitle1" fontWeight={600}>{title}</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              {typeFilter ? t('control.pulseData.noRowsOfType', { type: typeFilter }) : emptyHint}
            </Typography>
          </Paper>
        ) : (
          <Paper variant="outlined" sx={{ flex: 1, minHeight: 0 }}>
            <CarbonDataGrid
              columns={columns}
              rows={filteredRows}
              loading={false}
              getRowId={(row) => `${row._type}:${row.id ?? row.conversation_id ?? JSON.stringify(row)}`}
              emptyMessage={emptyHint}
              onRowClick={({ row }) => setSelected(row)}
            />
          </Paper>
        )}
      </Stack>
      <PulseDetailDrawer row={selected} onClose={() => setSelected(null)} />
    </PageContainer>
  );
}

PulseDataPanel.propTypes = {
  title: PropTypes.string.isRequired,
  description: PropTypes.string,
  dataKey: PropTypes.string.isRequired,
  emptyHint: PropTypes.string.isRequired,
  links: PropTypes.arrayOf(
    PropTypes.shape({
      label: PropTypes.string.isRequired,
      to: PropTypes.string.isRequired,
    }),
  ),
};

PulseDataPanel.defaultProps = {
  description: '',
  links: [],
};
