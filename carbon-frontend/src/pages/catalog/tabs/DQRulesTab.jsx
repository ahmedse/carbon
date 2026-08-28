// src/pages/catalog/tabs/DQRulesTab.jsx
// DQ rules ASSIGNED to this table. Rules are authored and run in the DQ Workspace;
// this tab only manages assignments — attach, detach, toggle, and view status.
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Box, Button, Table, TableHead, TableBody, TableRow, TableCell,
  IconButton, Chip, CircularProgress, Alert, Typography, Tooltip, Stack,
  TextField, FormControl, InputLabel, Select, MenuItem, List, ListItemButton,
  ListItemText, ListItemIcon, Radio, InputAdornment, FormHelperText,
} from '@mui/material';
import SystemDialog from '../../../components/SystemDialog';
import ConfirmDialog from '../../../components/ConfirmDialog';
import AddIcon from '@mui/icons-material/Add';
import LinkOffIcon from '@mui/icons-material/LinkOff';
import ToggleOnIcon from '@mui/icons-material/ToggleOn';
import ToggleOffIcon from '@mui/icons-material/ToggleOff';
import SearchIcon from '@mui/icons-material/Search';
import { useAuth } from '../../../auth/AuthContext';
import { useNotification } from '../../../components/NotificationProvider';
import { DetailTabContent } from '../../../components/detail/DetailMainPanel';
import {
  listDQRules, getDQRule, updateDQRule, getDQResults,
} from '../../../api/dq';
import { fetchDataSchemaFields } from '../../../api/dataschema';
import {
  RULE_TYPE_LABELS,
  SEVERITY_COLORS, RESULT_STATUS_COLORS,
  RULE_FIELD_TYPE_COMPAT, isRuleCompatibleWithField,
  DIMENSION_LABEL_KEYS,
  ruleTypeLabel, dimensionLabel, severityLabel, fieldTypeLabel,
} from '../../dq/constants';

function unwrap(data) {
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.results)) return data.results;
  return [];
}

export default function DQRulesTab({ tableId, fields: fieldsProp = [] }) {
  const { token } = useAuth();
  const { notify } = useNotification();
  const { t } = useTranslation('catalog');
  // DQ label helpers resolve keys in the `dq` namespace.
  const { t: tDq } = useTranslation('dq');

  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionBusyId, setActionBusyId] = useState(null);
  const [latestByRule, setLatestByRule] = useState({});

  // ── Attach-rule modal state ──
  const [attachOpen, setAttachOpen] = useState(false);
  const [candidates, setCandidates] = useState([]);
  const [candidatesLoading, setCandidatesLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [dimensionFilter, setDimensionFilter] = useState('');
  const [scopeFilter, setScopeFilter] = useState('all');
  const [selectedFieldId, setSelectedFieldId] = useState('');
  const [selectedRuleId, setSelectedRuleId] = useState(null);
  const [attaching, setAttaching] = useState(false);
  const [detachTarget, setDetachTarget] = useState(null);

  // Table fields — passed by SchemaDetailPage, with a defensive fetch fallback.
  const [fields, setFields] = useState(fieldsProp);
  useEffect(() => { setFields(fieldsProp); }, [fieldsProp]);
  useEffect(() => {
    if (fieldsProp.length > 0 || !tableId) return;
    let cancelled = false;
    fetchDataSchemaFields(token, tableId, null, null)
      .then((data) => { if (!cancelled) setFields(Array.isArray(data) ? data : data?.results || []); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [fieldsProp, token, tableId]);

  const loadRules = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listDQRules(token, { data_table: tableId });
      setRules(unwrap(data));
    } catch (err) {
      setError(err.message || t('failedToLoadRules'));
      notify({ message: err.message || t('failedToLoadRules'), type: 'error' });
    } finally {
      setLoading(false);
    }
  }, [token, tableId, notify, t]);

  // Latest run status per applied rule (Status column).
  const loadLatestResults = useCallback(async () => {
    try {
      const data = await getDQResults({ data_table_id: tableId }, token);
      const results = unwrap(data);
      const map = {};
      results.forEach((r) => { if (r.rule != null && !map[r.rule]) map[r.rule] = r; });
      setLatestByRule(map);
    } catch (_err) {
      setLatestByRule({});
    }
  }, [token, tableId]);

  useEffect(() => {
    loadRules();
    loadLatestResults();
  }, [loadRules, loadLatestResults]);

  // This table's bindings for a rule (drives the Scope column).
  const tableAssignments = useCallback(
    (rule) => (rule.field_assignments || []).filter((a) => String(a.data_table) === String(tableId)),
    [tableId],
  );

  const fieldLabel = (id) => {
    const f = fields.find((x) => String(x.id) === String(id));
    return f ? f.label || f.name : id;
  };

  const statusLabel = (s) => ({
    passed: t('passed'),
    failed: t('failed'),
    skipped_unavailable: t('skipped'),
  })[s] || s;

  const openAttach = async () => {
    setAttachOpen(true);
    setSearch('');
    setDimensionFilter('');
    setScopeFilter('all');
    setSelectedFieldId('');
    setSelectedRuleId(null);
    setCandidatesLoading(true);
    try {
      const data = await listDQRules(token); // all rules (authored in the DQ workspace)
      const all = unwrap(data);
      const appliedIds = new Set(rules.map((r) => r.id));
      // Both scopes are attached here: business rules apply once per table,
      // field-validation rules attach per field — exclude what is already applied.
      setCandidates(all.filter((r) => !appliedIds.has(r.id)));
    } catch (err) {
      notify({ message: err.message || t('failedToLoadAvailableRules'), type: 'error' });
      setCandidates([]);
    } finally {
      setCandidatesLoading(false);
    }
  };

  const selectedRule = useMemo(
    () => candidates.find((r) => r.id === selectedRuleId) || null,
    [candidates, selectedRuleId],
  );

  const filteredCandidates = useMemo(() => {
    const q = search.trim().toLowerCase();
    return candidates.filter((r) => {
      if (scopeFilter === 'table' && r.rule_level !== 'business_rule') return false;
      if (scopeFilter === 'field' && r.rule_level !== 'field_validation') return false;
      if (dimensionFilter && r.dimension !== dimensionFilter) return false;
      if (q) {
        const hay = `${r.name} ${r.description || ''} ${RULE_TYPE_LABELS[r.rule_type] || ''}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [candidates, search, dimensionFilter, scopeFilter]);

  const handleAttach = async () => {
    if (!selectedRule) return;
    setAttaching(true);
    try {
      const detail = await getDQRule(token, selectedRule.id); // fresh assignments (rule may have been re-bound elsewhere)
      const existing = (detail.field_assignments || []).map((a) => ({
        data_table: a.data_table,
        data_field: a.data_field,
      }));
      const isBusiness = selectedRule.rule_level === 'business_rule';
      const dataField = isBusiness ? null : selectedFieldId || null;
      const duplicate = existing.some((a) =>
        String(a.data_table) === String(tableId) &&
        (isBusiness || String(a.data_field) === String(dataField)),
      );
      if (duplicate) {
        notify({
          message: isBusiness ? t('ruleAlreadyOnTable') : t('ruleAlreadyOnField'),
          type: 'warning',
        });
        setAttachOpen(false);
        return;
      }
      const next = [
        ...existing,
        { data_table: tableId, data_field: dataField }, // business → whole table, field → specific field
      ];
      await updateDQRule(token, selectedRule.id, { field_assignments_write: next });
      notify({
        message: isBusiness
          ? t('ruleAppliedToTable', { name: selectedRule.name })
          : t('ruleAppliedToField', { name: selectedRule.name, field: fieldLabel(dataField) }),
        type: 'success',
      });
      setAttachOpen(false);
      loadRules();
      loadLatestResults();
    } catch (err) {
      notify({ message: err?.message || t('couldNotApplyRule'), type: 'error' });
    } finally {
      setAttaching(false);
    }
  };

  const handleToggleActive = async (rule) => {
    setActionBusyId(`toggle-${rule.id}`);
    const next = !rule.is_active;
    try {
      // DQRule.save() re-syncs is_active from definition.active — patch both together.
      const payload = { is_active: next };
      if (rule.definition && typeof rule.definition === 'object') {
        payload.definition = { ...rule.definition, active: next };
      }
      await updateDQRule(token, rule.id, payload);
      notify({ message: next ? t('ruleActivated', { name: rule.name }) : t('ruleDeactivated', { name: rule.name }), type: 'success' });
      loadRules();
    } catch (err) {
      notify({ message: err?.message || t('couldNotUpdateRule'), type: 'error' });
    } finally {
      setActionBusyId(null);
    }
  };

  const confirmDetach = async () => {
    if (!detachTarget) return;
    setActionBusyId(`detach-${detachTarget.id}`);
    try {
      const detail = await getDQRule(token, detachTarget.id);
      const next = (detail.field_assignments || [])
        .filter((a) => String(a.data_table) !== String(tableId))
        .map((a) => ({ data_table: a.data_table, data_field: a.data_field }));
      // Detach is a deliberate, confirmed action — replace_assignments confirms the
      // drop so the serializer's drift guard doesn't block removing the last binding.
      await updateDQRule(token, detachTarget.id, {
        field_assignments_write: next,
        replace_assignments: true,
      });
      notify({ message: t('ruleRemovedFromTable', { name: detachTarget.name }), type: 'success' });
      setDetachTarget(null);
      loadRules();
      loadLatestResults();
    } catch (err) {
      notify({ message: err?.message || t('couldNotDetachRule'), type: 'error' });
    } finally {
      setActionBusyId(null);
    }
  };

  if (loading) {
    return (
      <DetailTabContent>
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}><CircularProgress /></Box>
      </DetailTabContent>
    );
  }

  return (
    <DetailTabContent>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
        <Typography variant="h6">{t('assignedRules')}</Typography>
        <Stack direction="row" spacing={1}>
          <Button variant="contained" startIcon={<AddIcon />} onClick={openAttach}>
            {t('assignRule')}
          </Button>
        </Stack>
      </Box>

      <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary', mb: 1.5 }}>
        {t('dqAssignmentsHint')}
      </Typography>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {rules.length === 0 ? (
        <Alert severity="info">{t('noRulesAssigned')}</Alert>
      ) : (
        <Box sx={{ overflowX: 'auto' }}>
          <Table size="small">
            <TableHead>
              <TableRow sx={{ bgcolor: 'grey.100' }}>
                <TableCell sx={{ fontWeight: 600 }}>{t('rule')}</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>{t('type')}</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>{t('dimension')}</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>{t('scope')}</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>{t('severity')}</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>{t('status')}</TableCell>
                <TableCell sx={{ fontWeight: 600 }} align="right">{t('runs')}</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>{t('active')}</TableCell>
                <TableCell sx={{ fontWeight: 600 }} align="right">{t('actions')}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {rules.map((rule) => {
                const latest = latestByRule[rule.id];
                const mine = tableAssignments(rule);
                const fieldNames = mine.map((a) => a.field_name || (a.data_field ? `#${a.data_field}` : '')).filter(Boolean);
                return (
                  <TableRow key={rule.id} sx={{ '&:hover': { bgcolor: 'grey.50' } }}>
                    <TableCell sx={{ fontWeight: 500 }}>{rule.name || '—'}</TableCell>
                    <TableCell>
                      <Chip label={ruleTypeLabel(tDq, rule.rule_type)} size="small" variant="outlined" />
                    </TableCell>
                    <TableCell>
                      {rule.dimension
                        ? <Chip label={dimensionLabel(tDq, rule.dimension)} size="small" variant="outlined" />
                        : '—'}
                    </TableCell>
                    <TableCell>
                      <Stack direction="row" spacing={0.5} alignItems="center" flexWrap="wrap">
                        <Chip
                          label={rule.rule_level === 'business_rule' ? t('table') : t('field')}
                          size="small"
                          variant="outlined"
                          color={rule.rule_level === 'business_rule' ? 'secondary' : 'info'}
                        />
                        {rule.rule_level !== 'business_rule' && fieldNames.length > 0 && (
                          <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary' }}>
                            {fieldNames.join(', ')}
                          </Typography>
                        )}
                      </Stack>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={severityLabel(tDq, rule.severity)}
                        size="small"
                        color={SEVERITY_COLORS[rule.severity] || 'default'}
                        variant="outlined"
                      />
                    </TableCell>
                    <TableCell>
                      {latest ? (
                        <Stack direction="row" spacing={0.5} alignItems="center">
                          <Chip
                            label={statusLabel(latest.status)}
                            size="small"
                            color={RESULT_STATUS_COLORS[latest.status] || 'default'}
                          />
                          {latest.score != null && (
                            <Typography sx={{ fontSize: '0.7rem', color: 'text.secondary' }}>
                              {latest.score}%
                            </Typography>
                          )}
                        </Stack>
                      ) : (
                        <Typography sx={{ fontSize: '0.75rem', color: 'text.disabled' }}>{t('neverRun')}</Typography>
                      )}
                    </TableCell>
                    <TableCell align="right">{rule.results_count ?? 0}</TableCell>
                    <TableCell>
                      <Chip
                        label={rule.is_active ? t('active') : t('inactive')}
                        size="small"
                        color={rule.is_active ? 'success' : 'default'}
                      />
                    </TableCell>
                    <TableCell align="right">
                      <Tooltip title={rule.is_active ? t('deactivate') : t('activate')}>
                        <span>
                          <IconButton size="small" disabled={actionBusyId === `toggle-${rule.id}`} onClick={() => handleToggleActive(rule)}>
                            {rule.is_active ? <ToggleOnIcon fontSize="small" color="success" /> : <ToggleOffIcon fontSize="small" />}
                          </IconButton>
                        </span>
                      </Tooltip>
                      <Tooltip title={t('removeFromTable')}>
                        <span>
                          <IconButton size="small" disabled={actionBusyId === `detach-${rule.id}`} onClick={() => setDetachTarget(rule)}>
                            <LinkOffIcon fontSize="small" />
                          </IconButton>
                        </span>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </Box>
      )}

      {/* ── Assign DQ Rule — pick an existing rule (business or field-validation) from the DQ workspace ── */}
      <SystemDialog
        open={attachOpen}
        title={t('assignDqRule')}
        onClose={() => { if (!attaching) setAttachOpen(false); }}
        onCancel={() => { if (!attaching) setAttachOpen(false); }}
        cancelLabel={t('common:cancel')}
        width={640}
        height={520}
        minWidth={520}
        minHeight={400}
        maxWidth="calc(100vw - 32px)"
        maxHeight="calc(100vh - 32px)"
        actions={
          <Button
            variant="contained"
            size="small"
            onClick={handleAttach}
            disabled={attaching || !selectedRule || (selectedRule.rule_level === 'field_validation' && !selectedFieldId)}
          >
            {attaching
              ? t('assigning')
              : selectedRule?.rule_level === 'business_rule'
                ? t('assignToTable')
                : t('assignToField')}
          </Button>
        }
      >
        <Stack spacing={1.5}>
          <Typography variant="caption" color="text.secondary">
            {t('pickRuleHint')}
          </Typography>
          <TextField
            size="small"
            fullWidth
            placeholder={t('searchRulesPlaceholder')}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            InputProps={{
              startAdornment: (<InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment>),
            }}
          />
          <Stack direction="row" spacing={1}>
            <FormControl size="small" fullWidth>
              <InputLabel>{t('scope')}</InputLabel>
              <Select
                label={t('scope')}
                value={scopeFilter}
                onChange={(e) => { setScopeFilter(e.target.value); setSelectedFieldId(''); }}
              >
                <MenuItem value="all">{t('allScopes')}</MenuItem>
                <MenuItem value="table">{t('tableBusinessRule')}</MenuItem>
                <MenuItem value="field">{t('fieldValidation')}</MenuItem>
              </Select>
            </FormControl>
            <FormControl size="small" fullWidth>
              <InputLabel>{t('dimension')}</InputLabel>
              <Select label={t('dimension')} value={dimensionFilter} onChange={(e) => setDimensionFilter(e.target.value)}>
                <MenuItem value="">{t('allDimensions')}</MenuItem>
                {Object.entries(DIMENSION_LABEL_KEYS).map(([v, key]) => <MenuItem key={v} value={v}>{tDq(key)}</MenuItem>)}
              </Select>
            </FormControl>
          </Stack>

          {candidatesLoading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}><CircularProgress size={24} /></Box>
          ) : filteredCandidates.length === 0 ? (
            <Alert severity="info">{t('noMatchingRules')}</Alert>
          ) : (
            <List dense sx={{ maxHeight: 200, overflowY: 'auto', border: 1, borderColor: 'divider', borderRadius: 1 }}>
              {filteredCandidates.map((r) => (
                <ListItemButton
                  key={r.id}
                  selected={r.id === selectedRuleId}
                  onClick={() => { setSelectedRuleId(r.id); setSelectedFieldId(''); }}
                >
                  <ListItemIcon sx={{ minWidth: 36 }}>
                    <Radio size="small" checked={r.id === selectedRuleId} />
                  </ListItemIcon>
                  <ListItemText
                    primary={r.name}
                    secondaryTypographyProps={{ component: 'div' }}
                    secondary={(
                      <Stack direction="row" spacing={0.5} flexWrap="wrap">
                        <Chip
                          label={r.rule_level === 'business_rule' ? t('table') : t('field')}
                          size="small"
                          variant="outlined"
                          color={r.rule_level === 'business_rule' ? 'secondary' : 'info'}
                        />
                        <Chip label={ruleTypeLabel(tDq, r.rule_type)} size="small" variant="outlined" />
                        {r.dimension ? <Chip label={dimensionLabel(tDq, r.dimension)} size="small" variant="outlined" /> : null}
                        <Chip label={severityLabel(tDq, r.severity)} size="small" color={SEVERITY_COLORS[r.severity] || 'default'} variant="outlined" />
                      </Stack>
                    )}
                  />
                </ListItemButton>
              ))}
            </List>
          )}

          {selectedRule && selectedRule.rule_level === 'field_validation' && (
            <FormControl size="small" fullWidth>
              <InputLabel>{t('field')}</InputLabel>
              <Select
                label={t('field')}
                value={selectedFieldId}
                onChange={(e) => setSelectedFieldId(e.target.value)}
              >
                {fields.map((f) => {
                  const compatible = isRuleCompatibleWithField(selectedRule.rule_type, f.type);
                  return (
                    <MenuItem key={f.id} value={f.id} disabled={!compatible}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center', gap: 2 }}>
                        <span>{f.label || f.name || f.id}</span>
                        <Typography component="span" variant="caption" color="text.secondary">
                          {fieldTypeLabel(tDq, f.type)}{compatible ? '' : ` · ${t('incompatible')}`}
                        </Typography>
                      </Box>
                    </MenuItem>
                  );
                })}
              </Select>
              <FormHelperText>
                {(() => {
                  const allowed = RULE_FIELD_TYPE_COMPAT[selectedRule.rule_type];
                  const typeLabel = ruleTypeLabel(tDq, selectedRule.rule_type);
                  const target = !allowed
                    ? t('anyFieldType')
                    : allowed.map((ft) => fieldTypeLabel(tDq, ft)).join(', ');
                  return t('rulesApplyTo', { type: typeLabel, target });
                })()}
              </FormHelperText>
            </FormControl>
          )}
        </Stack>
      </SystemDialog>

      {/* ── Remove-from-table confirmation ── */}
      <ConfirmDialog
        open={!!detachTarget}
        title={t('removeRuleTitle')}
        message={detachTarget ? t('removeRuleMessage', { name: detachTarget.name }) : ''}
        confirmLabel={t('remove')}
        destructive
        onConfirm={confirmDetach}
        onCancel={() => setDetachTarget(null)}
      />
    </DetailTabContent>
  );
}
