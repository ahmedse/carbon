// carbon-frontend/src/pages/dq/tabs/RulesTab.jsx
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Button,
  Chip,
  IconButton,
  MenuItem,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import SystemDialog from '../../../components/SystemDialog';
import ConfirmDialog from '../../../components/ConfirmDialog';
import { Add, DeleteOutline, Visibility, Tune } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../../auth/AuthContext';
import { useNotification } from '../../../components/NotificationProvider';
import CarbonDataGrid from '../../../components/DataGrid/CarbonDataGrid';
import RuleJsonEditor from '../../../components/dq/RuleJsonEditor';
import {
  RULE_TYPES,
  RULE_LEVELS,
  DIMENSION_CODES,
  SEVERITY_VALUES,
  validateDefinitionClient,
  normalizeServerErrors,
} from '../../../components/dq/ruleJsonValidation';
import {
  listDQRules,
  createDQRule,
  updateDQRule,
  deleteDQRule,
  listDQTags,
} from '../../../api/dq';
import { fetchAssetProfiles } from '../../../api/catalog';
import {
  RULE_TYPE_LABELS,
  RULE_LEVEL_LABELS,
  DIMENSION_LABELS,
  SEVERITY_LABELS,
  SEVERITY_COLORS,
} from '../constants';
import { resolveBindings } from '../bindings';

const EMPTY_FILTERS = {
  search: '',
  rule_level: '',
  rule_type: '',
  dimension: '',
  severity: '',
  active: 'active',
  tag: '',
  data_table: '',
  include_archived: false,
};

function RulesTab({ onJobCreated: _onJobCreated, tableFilter }) {
  const { token } = useAuth();
  const navigate = useNavigate();
  const { notify, notifyFromError } = useNotification();

  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [tags, setTags] = useState([]);
  const [filters, setFilters] = useState(() => ({ ...EMPTY_FILTERS, data_table: tableFilter || '' }));
  const [showFilters, setShowFilters] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [definitionText, setDefinitionText] = useState('');
  const [serverErrors, setServerErrors] = useState([]);
  const [saving, setSaving] = useState(false);
  const [tables, setTables] = useState([]);
  const [actionBusyId, setActionBusyId] = useState(null);
  const [filteredTableName, setFilteredTableName] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [selectedRowId, setSelectedRowId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {
        search: filters.search || undefined,
        rule_level: filters.rule_level || undefined,
        rule_type: filters.rule_type || undefined,
        dimension: filters.dimension || undefined,
        severity: filters.severity || undefined,
        is_active: filters.active === 'all' ? undefined : filters.active === 'active',
        tag: filters.tag || undefined,
        data_table: filters.data_table || undefined,
        ...(filters.include_archived ? { include_archived: 1 } : {}),
      };
      const payload = await listDQRules(token, params);
      setRows(Array.isArray(payload) ? payload : payload?.results || []);
    } catch (err) {
      notifyFromError(err, 'Could not load DQ rules');
    } finally {
      setLoading(false);
    }
  }, [token, filters, notifyFromError]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    let active = true;
    listDQTags(token)
      .then((payload) => {
        if (active) setTags(Array.isArray(payload) ? payload : payload?.results || []);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [token]);

  const loadTables = useCallback(async () => {
    try {
      const payload = await fetchAssetProfiles(token);
      const all = Array.isArray(payload) ? payload : payload?.results || [];
      const unique = [];
      const seen = new Set();
      all.forEach((a) => {
        if (a.data_table != null && !a.data_field && !seen.has(a.data_table)) {
          seen.add(a.data_table);
          unique.push(a);
        }
      });
      setTables(unique);
      if (filters.data_table && !filteredTableName) {
        const hit = unique.find((a) => String(a.data_table) === String(filters.data_table));
        if (hit) setFilteredTableName(hit.title);
      }
    } catch (_err) {
      setTables([]);
    }
  }, [token, filters.data_table, filteredTableName]);

  const openCreate = () => {
    setDefinitionText(JSON.stringify(
      {
        schema_version: 1,
        name: '',
        description: '',
        level: 'field',
        dimension: 'completeness',
        type: 'not_null',
        severity: 'error',
        active: true,
        bindings: [{ table: '', field: '' }],
        params: {},
        enforcement: { on_write: false },
      },
      null,
      2
    ));
    setServerErrors([]);
    loadTables();
    setCreateOpen(true);
  };

  const handleCreate = async () => {
    let parsed;
    try {
      parsed = JSON.parse(definitionText);
    } catch (err) {
      setServerErrors([{ field: '_root', code: 'parse', message: `Invalid JSON: ${err.message}` }]);
      return;
    }
    const clientErrors = validateDefinitionClient(parsed);
    if (clientErrors.length) {
      setServerErrors(clientErrors);
      return;
    }
    setSaving(true);
    try {
      const { assignments, errors } = await resolveBindings(parsed, tables, token);
      if (errors.length) {
        setServerErrors(errors);
        return;
      }
      await createDQRule(token, {
        definition: parsed,
        field_assignments_write: assignments,
      });
      notify({ message: 'Rule created', type: 'success' });
      setCreateOpen(false);
      load();
    } catch (err) {
      setServerErrors(normalizeServerErrors(err?.data || err));
    } finally {
      setSaving(false);
    }
  };

  const handleToggleActive = async (rule) => {
    setActionBusyId(`toggle-${rule.id}`);
    try {
      await updateDQRule(token, rule.id, { is_active: !rule.is_active });
      notify({
        message: `"${rule.name}" ${rule.is_active ? 'deactivated' : 'activated'}`,
        type: 'success',
      });
      load();
    } catch (err) {
      notifyFromError(err, 'Could not update rule');
    } finally {
      setActionBusyId(null);
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setActionBusyId(`delete-${deleteTarget.id}`);
    try {
      await deleteDQRule(token, deleteTarget.id);
      notify({ message: `Rule "${deleteTarget.name}" deleted`, type: 'success' });
      setDeleteTarget(null);
      load();
    } catch (err) {
      notifyFromError(err, 'Could not delete rule');
    } finally {
      setActionBusyId(null);
    }
  };

  const columns = useMemo(
    () => [
      {
        field: 'name',
        headerName: 'Rule',
        flex: 1.6,
        minWidth: 220,
        renderCell: ({ row }) => (
          <Stack spacing={0.25}>
            <Typography sx={{ fontWeight: 600 }}>{row.name}</Typography>
            {row.description ? (
              <Typography noWrap sx={{ color: 'text.secondary', maxWidth: 260 }}>
                {row.description}
              </Typography>
            ) : null}
          </Stack>
        ),
      },
      {
        field: 'rule_type',
        headerName: 'Type',
        width: 150,
        // DataGrid v8: valueGetter receives positional (value, row) — v7 ({ row }) object signature was removed
        valueGetter: (_value, row) => RULE_TYPE_LABELS[row.rule_type] || row.rule_type,
      },
      {
        field: 'dimension',
        headerName: 'Dimension',
        width: 140,
        renderCell: ({ row }) =>
          row.dimension ? (
            <Chip size="small" variant="outlined" label={DIMENSION_LABELS[row.dimension] || row.dimension} />
          ) : null,
      },
      {
        field: 'severity',
        headerName: 'Severity',
        width: 110,
        renderCell: ({ row }) => (
          <Chip
            size="small"
            color={SEVERITY_COLORS[row.severity] || 'default'}
            label={SEVERITY_LABELS[row.severity] || row.severity}
          />
        ),
      },
      {
        field: 'level',
        headerName: 'Level',
        width: 130,
        valueGetter: (_value, row) => RULE_LEVEL_LABELS[row.rule_level] || row.rule_level,
      },
      {
        field: 'tables',
        headerName: 'Bound Tables',
        width: 180,
        renderCell: ({ row }) => {
          const names = (row.field_assignments || []).map((a) => a.table_name).filter(Boolean);
          const unique = [...new Set(names)];
          return (
            <Stack direction="row" spacing={0.5} sx={{ overflow: 'hidden' }}>
              {unique.slice(0, 2).map((name) => (
                <Chip key={name} size="small" variant="outlined" label={name} />
              ))}
              {unique.length > 2 ? (
                <Chip size="small" variant="outlined" label={`+${unique.length - 2}`} />
              ) : null}
            </Stack>
          );
        },
      },
      {
        field: 'is_active',
        headerName: 'Active',
        width: 100,
        renderCell: ({ row }) =>
          row.archived ? (
            <Chip size="small" color="default" variant="outlined" label="Archived" />
          ) : (
            <Chip
              size="small"
              color={row.is_active ? 'success' : 'default'}
              label={row.is_active ? 'Active' : 'Inactive'}
            />
          ),
      },
      {
        field: 'version',
        headerName: 'Ver',
        width: 70,
        valueGetter: (_value, row) => row.version,
      },
      {
        field: 'actions',
        headerName: '',
        sortable: false,
        width: 150,
        align: 'right',
        renderCell: ({ row }) => (
          <Stack direction="row" spacing={0}>
            <Tooltip title="Open rule detail">
              <IconButton
                size="small"
                onClick={(e) => {
                  e.stopPropagation();
                  navigate(`/dq/rules/${row.id}`);
                }}
              >
                <Visibility fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title={row.is_active ? 'Deactivate' : 'Activate'}>
              <span>
                <IconButton
                  size="small"
                  disabled={actionBusyId === `toggle-${row.id}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    handleToggleActive(row);
                  }}
                >
                  {row.is_active ? <Tune fontSize="small" color="disabled" /> : <Tune fontSize="small" color="primary" />}
                </IconButton>
              </span>
            </Tooltip>
            <Tooltip title="Delete / archive">
              <span>
                <IconButton
                  size="small"
                  disabled={actionBusyId === `delete-${row.id}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    setDeleteTarget(row);
                  }}
                >
                  <DeleteOutline fontSize="small" />
                </IconButton>
              </span>
            </Tooltip>
          </Stack>
        ),
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [navigate, actionBusyId]
  );

  return (
    <Box>
      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" sx={{ mb: 2 }}>
        <TextField
          size="small"
          placeholder="Search rules…"
          value={filters.search}
          onChange={(e) => setFilters((f) => ({ ...f, search: e.target.value }))}
          sx={{ width: 240 }}
        />
        <Button
          variant="outlined"
          size="small"
          startIcon={<Tune />}
          onClick={() => setShowFilters((v) => !v)}
        >
          Filters
        </Button>
        {filters.data_table ? (
          <Chip
            size="small"
            variant="outlined"
            color="primary"
            label={`Table: ${filteredTableName || `#${filters.data_table}`}`}
            onDelete={() => setFilters((f) => ({ ...f, data_table: '' }))}
          />
        ) : null}
        <Box sx={{ flexGrow: 1 }} />
        <Button variant="contained" size="small" startIcon={<Add />} onClick={openCreate}>
          New Rule
        </Button>
      </Stack>

      {showFilters ? (
        <Stack direction="row" spacing={1} flexWrap="wrap" sx={{ mb: 2 }}>
          <TextField
            select
            size="small"
            label="Level"
            value={filters.rule_level}
            onChange={(e) => setFilters((f) => ({ ...f, rule_level: e.target.value }))}
            sx={{ minWidth: 160 }}
          >
            <MenuItem value="">All</MenuItem>
            {RULE_LEVELS.map((l) => (
              <MenuItem key={l} value={l}>
                {RULE_LEVEL_LABELS[l] || l}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            select
            size="small"
            label="Type"
            value={filters.rule_type}
            onChange={(e) => setFilters((f) => ({ ...f, rule_type: e.target.value }))}
            sx={{ minWidth: 170 }}
          >
            <MenuItem value="">All</MenuItem>
            {RULE_TYPES.map((t) => (
              <MenuItem key={t} value={t}>
                {RULE_TYPE_LABELS[t] || t}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            select
            size="small"
            label="Dimension"
            value={filters.dimension}
            onChange={(e) => setFilters((f) => ({ ...f, dimension: e.target.value }))}
            sx={{ minWidth: 160 }}
          >
            <MenuItem value="">All</MenuItem>
            {DIMENSION_CODES.map((d) => (
              <MenuItem key={d} value={d}>
                {DIMENSION_LABELS[d] || d}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            select
            size="small"
            label="Severity"
            value={filters.severity}
            onChange={(e) => setFilters((f) => ({ ...f, severity: e.target.value }))}
            sx={{ minWidth: 130 }}
          >
            <MenuItem value="">All</MenuItem>
            {SEVERITY_VALUES.map((s) => (
              <MenuItem key={s} value={s}>
                {SEVERITY_LABELS[s] || s}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            select
            size="small"
            label="State"
            value={filters.active}
            onChange={(e) => setFilters((f) => ({ ...f, active: e.target.value }))}
            sx={{ minWidth: 120 }}
          >
            <MenuItem value="active">Active</MenuItem>
            <MenuItem value="inactive">Inactive</MenuItem>
            <MenuItem value="all">All</MenuItem>
          </TextField>
          <TextField
            select
            size="small"
            label="Tag"
            value={filters.tag}
            onChange={(e) => setFilters((f) => ({ ...f, tag: e.target.value }))}
            sx={{ minWidth: 140 }}
          >
            <MenuItem value="">All</MenuItem>
            {tags.map((t) => (
              <MenuItem key={t.id} value={t.id}>
                {t.name}
              </MenuItem>
            ))}
          </TextField>
          <Button
            size="small"
            color="inherit"
            onClick={() => setFilters((f) => ({ ...f, include_archived: !f.include_archived }))}
            variant={filters.include_archived ? 'contained' : 'outlined'}
          >
            Include archived
          </Button>
        </Stack>
      ) : null}

      <CarbonDataGrid
        columns={columns}
        rows={rows}
        loading={loading}
        getRowId={(row) => row.id}
        emptyMessage="No rules match the current filters"
        onRowClick={({ row }) => setSelectedRowId(row.id === selectedRowId ? null : row.id)}
        highlightRow={(row) => row.id === selectedRowId}
      />

      {/* New rule — JSON-first authoring (no rule-builder form) */}
      <SystemDialog
        open={createOpen}
        title="New DQ Rule"
        onClose={() => setCreateOpen(false)}
        onCancel={() => setCreateOpen(false)}
        cancelLabel="Cancel"
        width={820}
        height={620}
        minWidth={640}
        minHeight={480}
        maxWidth="calc(100vw - 32px)"
        maxHeight="calc(100vh - 32px)"
        actions={
          <Button variant="contained" size="small" onClick={handleCreate} disabled={saving}>
            {saving ? 'Creating…' : 'Create Rule'}
          </Button>
        }
      >
        <Box px={2} py={1}>
          <Typography sx={{ color: 'text.secondary', mb: 1.5 }}>
            Author the rule definition as schema v1 JSON. Tables are matched by name to assets in
            your scope; fields are resolved against the live schema.
          </Typography>
          <RuleJsonEditor
            value={definitionText}
            onChange={setDefinitionText}
            serverErrors={serverErrors}
            tables={tables}
            disabled={saving}
          />
        </Box>
      </SystemDialog>

      {/* Delete confirmation (ConfirmDialog — no window.confirm) */}
      <ConfirmDialog
        open={!!deleteTarget}
        title="Delete rule?"
        message={
          deleteTarget
            ? `Delete "${deleteTarget.name}"? It will be archived if results exist.`
            : ''
        }
        confirmLabel="Delete"
        destructive
        onConfirm={confirmDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </Box>
  );
}

RulesTab.propTypes = {
  onJobCreated: PropTypes.func,
};

export default RulesTab;
