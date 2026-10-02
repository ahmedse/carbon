// src/pages/carbon/coverageTargetsShared.jsx
// Shared atoms for the two-layer Coverage targets UI (layer 1 · TARGETS).
// Counts and the measured ratio are shown, but Coverage STREAMS stay the only
// reporter of Missing / Entered / Excluded — nothing here relabels a stream
// state as a target state, and the ratio never reads as coverage complete.
// RULE 8 tokens, ADR-0037 (no page-local fontSize / hex), ADR-0018 (bdi for a
// domain term that stays English in an RTL sentence).
/* eslint-disable react-refresh/only-export-components */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import { Box, Chip, Stack, TextField, Typography } from '@mui/material';
import { SearchSelect } from '../../components/Form';
import { useAuth } from '../../auth/AuthContext';
import {
  fetchCoverageCampusOptions,
  fetchCoverageOrgUnitOptions,
  fetchCoverageOwnerOptions,
} from '../../api/emissions-extended';

/** Isolate a domain term that stays English inside an RTL sentence. */
export function Ltr({ children }) {
  return <bdi dir="ltr">{children}</bdi>;
}

Ltr.propTypes = { children: PropTypes.node };

export function formatDate(value) {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleDateString();
  } catch {
    return '—';
  }
}

const TIER_META = {
  1: { label: 'T1 Audited', color: 'success' },
  2: { label: 'T2 Verified', color: 'info' },
  3: { label: 'T3 Calculated', color: 'primary' },
  4: { label: 'T4 Estimated', color: 'warning' },
  5: { label: 'T5 Proxy', color: 'error' },
};

export function TierChip({ value }) {
  if (value == null) {
    return <Typography variant="body2" color="text.secondary">—</Typography>;
  }
  const meta = TIER_META[value] || { label: String(value), color: 'default' };
  return (
    <Chip
      size="small"
      label={<Ltr>{meta.label}</Ltr>}
      color={meta.color === 'default' ? undefined : meta.color}
    />
  );
}

TierChip.propTypes = { value: PropTypes.oneOfType([PropTypes.number, PropTypes.string]) };

const TARGET_STATUS_COLORS = { draft: 'warning', active: 'success', archived: 'default' };

export function TargetStatusChip({ value, t }) {
  const key = {
    draft: 'coverageTargets.statusDraft',
    active: 'coverageTargets.statusActive',
    archived: 'coverageTargets.statusArchived',
  }[value];
  const color = TARGET_STATUS_COLORS[value] || 'default';
  return (
    <Chip
      size="small"
      label={key ? t(key) : (value || '—')}
      color={color === 'default' ? undefined : color}
    />
  );
}

TargetStatusChip.propTypes = { value: PropTypes.string, t: PropTypes.func.isRequired };

const TASK_STATUS_COLORS = {
  open: 'info', in_progress: 'primary', done: 'success', blocked: 'error',
};

export function TaskStatusChip({ value, t }) {
  const key = {
    open: 'coverageTargets.taskOpen',
    in_progress: 'coverageTargets.taskInProgress',
    done: 'coverageTargets.taskDone',
    blocked: 'coverageTargets.taskBlocked',
  }[value];
  const color = TASK_STATUS_COLORS[value] || 'default';
  return (
    <Chip
      size="small"
      label={key ? t(key) : (value || '—')}
      color={color === 'default' ? undefined : color}
      variant="filled"
    />
  );
}

TaskStatusChip.propTypes = { value: PropTypes.string, t: PropTypes.func.isRequired };

export function TaskTypeChip({ value, t }) {
  const key = {
    bind_data_product: 'coverageTargets.taskTypeBindDataProduct',
    complete_rows: 'coverageTargets.taskTypeCompleteRows',
    fill_gap: 'coverageTargets.taskTypeFillGap',
    secure_factor: 'coverageTargets.taskTypeSecureFactor',
    other: 'coverageTargets.taskTypeOther',
  }[value];
  return <Chip size="small" variant="outlined" label={key ? t(key) : (value || '—')} />;
}

TaskTypeChip.propTypes = { value: PropTypes.string, t: PropTypes.func.isRequired };

export function EvidenceBadge({ evidence, t }) {
  const met = Boolean(evidence && evidence.met);
  return (
    <Chip
      size="small"
      color={met ? 'success' : 'default'}
      variant={met ? 'filled' : 'outlined'}
      label={met ? t('coverageTargets.evidenceMet') : t('coverageTargets.evidenceWaiting')}
    />
  );
}

EvidenceBadge.propTypes = {
  evidence: PropTypes.shape({ met: PropTypes.bool, codes: PropTypes.array }),
  t: PropTypes.func.isRequired,
};

/** Human label for a target goal (percent or absolute + unit). */
export function goalLabel(target) {
  if (!target) return '—';
  const value = target.goal_value ?? '';
  if (target.goal_kind === 'absolute') {
    return `${value} ${target.goal_unit || ''}`.trim() || '—';
  }
  return `${value}%`;
}

/** Human label for a target scope (+ scope 3 category). */
export function scopeLabel(target) {
  if (!target) return '—';
  const base = target.scope_display || (target.scope ? `Scope ${target.scope}` : '—');
  return target.scope3_category != null ? `${base} · Cat ${target.scope3_category}` : base;
}

/** One-line goal summary used as a WorkflowCard description. */
export function goalSummary(t, target) {
  if (!target) return '';
  const campus = target.campus_name || target.org_unit_name || '—';
  const scope = scopeLabel(target);
  const goal = goalLabel(target);
  return t('coverageTargets.summary', { campus, scope, goal });
}

const SCOPE_VALUES = ['1', '2', '3', '1+2', '1+2+3'];

export function emptyTargetForm() {
  return {
    name: '',
    campus: '',
    org_unit: '',
    scope: '1+2',
    scope3_category: '',
    goal_kind: 'percent',
    goal_value: '',
    goal_unit: '',
    min_quality_tier: '',
    due_date: '',
    owner: '',
    status: 'draft',
    notes: '',
  };
}

export function targetToForm(target) {
  if (!target) return emptyTargetForm();
  return {
    name: target.name ?? '',
    campus: target.campus != null ? String(target.campus) : '',
    org_unit: target.org_unit != null ? String(target.org_unit) : '',
    scope: target.scope ?? '1+2',
    scope3_category: target.scope3_category != null ? String(target.scope3_category) : '',
    goal_kind: target.goal_kind ?? 'percent',
    goal_value: target.goal_value != null ? String(target.goal_value) : '',
    goal_unit: target.goal_unit ?? '',
    min_quality_tier: target.min_quality_tier != null ? String(target.min_quality_tier) : '',
    due_date: target.due_date ?? '',
    owner: target.owner != null ? String(target.owner) : '',
    status: target.status ?? 'draft',
    notes: target.notes ?? '',
  };
}

export function formToTargetPayload(form) {
  return {
    name: form.name.trim(),
    campus: form.campus ? Number(form.campus) : null,
    org_unit: form.org_unit ? Number(form.org_unit) : null,
    scope: form.scope,
    scope3_category: form.scope3_category ? Number(form.scope3_category) : null,
    goal_kind: form.goal_kind,
    goal_value: form.goal_value !== '' ? Number(form.goal_value) : null,
    goal_unit: form.goal_kind === 'absolute' ? (form.goal_unit || '').trim() : '',
    min_quality_tier: form.min_quality_tier ? Number(form.min_quality_tier) : null,
    due_date: form.due_date || null,
    owner: form.owner ? Number(form.owner) : null,
    status: form.status,
    notes: form.notes || '',
  };
}

/**
 * Load the REAL options the target form depends on:
 *  - campuses  : mdm.OrgUnit with org_type='campus' (carbon scope)
 *  - org units : the selected campus's real descendants (refreshed on change)
 *  - owners    : real people (accounts.User)
 * Every list carries an honest loading / error state; failures never fabricate
 * options. Nothing is cached across tokens.
 */
export function useCoverageLookups(token) {
  const [campuses, setCampuses] = useState([]);
  const [campusesState, setCampusesState] = useState({ loading: true, error: '' });
  const [orgUnits, setOrgUnits] = useState([]);
  const [orgUnitsState, setOrgUnitsState] = useState({ loading: false, error: '' });
  const [owners, setOwners] = useState([]);
  const [ownersState, setOwnersState] = useState({ loading: true, error: '' });

  const loadCampuses = useCallback(async () => {
    setCampusesState({ loading: true, error: '' });
    try {
      const rows = await fetchCoverageCampusOptions(token);
      setCampuses(Array.isArray(rows) ? rows : (rows?.results ?? []));
      setCampusesState({ loading: false, error: '' });
    } catch (err) {
      setCampuses([]);
      setCampusesState({ loading: false, error: err?.message || 'error' });
    }
  }, [token]);

  const loadOwners = useCallback(async (q = '') => {
    setOwnersState((prev) => ({ ...prev, loading: true, error: '' }));
    try {
      const data = await fetchCoverageOwnerOptions({ q, pageSize: 200 }, token);
      setOwners(Array.isArray(data?.results) ? data.results : []);
      setOwnersState({ loading: false, error: '' });
    } catch (err) {
      setOwners((prev) => (q ? prev : []));
      setOwnersState({ loading: false, error: err?.message || 'error' });
    }
  }, [token]);

  const loadOrgUnits = useCallback(async (campusId) => {
    if (!campusId) {
      setOrgUnits([]);
      setOrgUnitsState({ loading: false, error: '' });
      return;
    }
    setOrgUnitsState({ loading: true, error: '' });
    try {
      const data = await fetchCoverageOrgUnitOptions({ campus: campusId }, token);
      setOrgUnits(Array.isArray(data?.results) ? data.results : []);
      setOrgUnitsState({ loading: false, error: '' });
    } catch (err) {
      setOrgUnits([]);
      setOrgUnitsState({ loading: false, error: err?.message || 'error' });
    }
  }, [token]);

  useEffect(() => {
    loadCampuses();
    loadOwners();
  }, [loadCampuses, loadOwners]);

  return {
    campuses, campusesState, loadCampuses,
    orgUnits, orgUnitsState, loadOrgUnits,
    owners, ownersState, loadOwners,
  };
}

/** Human label for a campus / org unit option that may carry an English code. */
function unitLabel(unit, { isCampus = false, wholeLabel = '' } = {}) {
  if (!unit) return '';
  // Only show a code when it adds information (real departments often store the
  // name as their code, which would just echo the label).
  const hasDistinctCode = unit.code && unit.code !== unit.name;
  const base = hasDistinctCode ? `${unit.name} · ${unit.code}` : unit.name;
  return isCampus ? `${base} · ${wholeLabel}` : base;
}

/** Target create / edit form body (render inside a SystemDialog). */
export function TargetForm({ values, onField, t }) {
  const { token } = useAuth();
  const lookups = useCoverageLookups(token);
  const set = (name) => (event) => onField(name, event.target.value);
  const isAbsolute = values.goal_kind === 'absolute';
  const needsCategory = String(values.scope || '').includes('3');

  // Child org units follow the selected campus — reload (and the page clears the
  // stale selection) whenever campus changes.
  const { loadOrgUnits } = lookups;
  useEffect(() => {
    loadOrgUnits(values.campus || '');
  }, [values.campus, loadOrgUnits]);

  const campusOptions = useMemo(
    () => lookups.campuses.map((c) => ({ value: String(c.id), label: unitLabel(c) })),
    [lookups.campuses],
  );

  const orgUnitOptions = useMemo(
    () => lookups.orgUnits.map((u) => ({
      value: String(u.id),
      label: unitLabel(u, { isCampus: Boolean(u.is_campus), wholeLabel: t('coverageTargets.wholeCampus') }),
    })),
    [lookups.orgUnits, t],
  );

  const ownerOptions = useMemo(() => {
    const list = lookups.owners.map((o) => ({
      value: String(o.id),
      label: o.label || o.full_name || o.username || String(o.id),
    }));
    // Keep the current owner selectable even before/while it is not in the list.
    if (values.owner && !list.some((o) => o.value === String(values.owner))) {
      list.unshift({ value: String(values.owner), label: values.owner_name || String(values.owner) });
    }
    return list;
  }, [lookups.owners, values.owner, values.owner_name]);

  const campusHasNoChildren = Boolean(values.campus)
    && !lookups.orgUnitsState.loading
    && !lookups.orgUnitsState.error
    && lookups.orgUnits.length <= 1;

  return (
    <Stack spacing={2} sx={{ pt: 1 }}>
      <TextField label={t('coverageTargets.targetName')} value={values.name} onChange={set('name')} required fullWidth size="small" />
      <SearchSelect
        label={t('coverageTargets.campus')}
        options={campusOptions}
        value={values.campus}
        onChange={(option) => onField('campus', option?.value ?? '')}
        loading={lookups.campusesState.loading}
        error={lookups.campusesState.error ? t('coverageTargets.campusLoadError') : undefined}
        onRetry={lookups.loadCampuses}
        helperText={t('coverageTargets.campusHint')}
        placeholder={t('coverageTargets.campusSearch')}
        noOptionsText={t('coverageTargets.campusEmpty')}
        required
      />
      <SearchSelect
        label={t('coverageTargets.orgUnit')}
        options={orgUnitOptions}
        value={values.org_unit}
        onChange={(option) => onField('org_unit', option?.value ?? '')}
        loading={lookups.orgUnitsState.loading}
        error={lookups.orgUnitsState.error ? t('coverageTargets.orgUnitLoadError') : undefined}
        onRetry={() => lookups.loadOrgUnits(values.campus || '')}
        disabled={!values.campus}
        helperText={
          !values.campus
            ? t('coverageTargets.orgUnitPickCampus')
            : (campusHasNoChildren ? t('coverageTargets.orgUnitNoChildren') : t('coverageTargets.orgUnitHint'))
        }
        placeholder={t('coverageTargets.orgUnitSearch')}
        noOptionsText={t('coverageTargets.orgUnitEmpty')}
        clearable={false}
        required
      />
      <SearchSelect
        label={t('coverageTargets.scope')}
        options={SCOPE_VALUES.map((v) => ({ value: v, label: `Scope ${v}` }))}
        value={values.scope}
        onChange={(option) => onField('scope', option?.value ?? '')}
        clearable={false}
      />
      {needsCategory && (
        <TextField
          label={t('coverageTargets.scope3Category')}
          value={values.scope3_category}
          onChange={set('scope3_category')}
          type="number"
          fullWidth
          size="small"
          helperText={t('coverageTargets.scope3CategoryHint')}
          inputProps={{ min: 1, max: 15 }}
        />
      )}
      <SearchSelect
        label={t('coverageTargets.goalKind')}
        options={[
          { value: 'percent', label: t('coverageTargets.goalPercent') },
          { value: 'absolute', label: t('coverageTargets.goalAbsolute') },
        ]}
        value={values.goal_kind}
        onChange={(option) => onField('goal_kind', option?.value ?? 'percent')}
        clearable={false}
      />
      <TextField
        label={t('coverageTargets.goalValue')}
        value={values.goal_value}
        onChange={set('goal_value')}
        type="number"
        required
        fullWidth
        size="small"
        inputProps={isAbsolute ? { min: 0 } : { min: 0, max: 100 }}
      />
      {isAbsolute && (
        <TextField label={t('coverageTargets.goalUnit')} value={values.goal_unit} onChange={set('goal_unit')} required fullWidth size="small" helperText={t('coverageTargets.goalUnitHint')} />
      )}
      <SearchSelect
        label={t('coverageTargets.qualityFloor')}
        options={[
          { value: '', label: t('coverageTargets.qualityFloorNone') },
          ...[1, 2, 3, 4, 5].map((n) => ({ value: String(n), label: TIER_META[n].label })),
        ]}
        value={values.min_quality_tier}
        onChange={(option) => onField('min_quality_tier', option?.value ?? '')}
        clearable={false}
      />
      <TextField label={t('coverageTargets.dueDate')} value={values.due_date} onChange={set('due_date')} type="date" fullWidth size="small" InputLabelProps={{ shrink: true }} />
      <SearchSelect
        label={t('coverageTargets.owner')}
        options={ownerOptions}
        value={values.owner}
        onChange={(option) => onField('owner', option?.value ?? '')}
        loading={lookups.ownersState.loading}
        error={lookups.ownersState.error ? t('coverageTargets.ownerLoadError') : undefined}
        onRetry={() => lookups.loadOwners()}
        helperText={t('coverageTargets.ownerHint')}
        placeholder={t('coverageTargets.ownerSearch')}
        noOptionsText={t('coverageTargets.ownerEmpty')}
      />
      <SearchSelect
        label={t('coverageTargets.colStatus')}
        options={[
          { value: 'draft', label: t('coverageTargets.statusDraft') },
          { value: 'active', label: t('coverageTargets.statusActive') },
          { value: 'archived', label: t('coverageTargets.statusArchived') },
        ]}
        value={values.status}
        onChange={(option) => onField('status', option?.value ?? 'draft')}
        clearable={false}
      />
      <TextField label={t('coverageTargets.notes')} value={values.notes} onChange={set('notes')} multiline rows={3} fullWidth size="small" />
    </Stack>
  );
}

TargetForm.propTypes = {
  values: PropTypes.object.isRequired,
  onField: PropTypes.func.isRequired,
  t: PropTypes.func.isRequired,
};

/** Read-only key/value line for the Target section. */
export function FieldRow({ label, value }) {
  return (
    <Stack direction="row" spacing={1} sx={{ alignItems: 'baseline', minWidth: 0 }}>
      <Typography variant="body2" color="text.secondary" sx={{ minWidth: 120 }}>
        {label}
      </Typography>
      <Box sx={{ minWidth: 0 }}>
        <Typography variant="body2" component="div">
          {value}
        </Typography>
      </Box>
    </Stack>
  );
}

FieldRow.propTypes = { label: PropTypes.node, value: PropTypes.node };

// Kept for tests that import the enum option list.
export { SCOPE_VALUES };
