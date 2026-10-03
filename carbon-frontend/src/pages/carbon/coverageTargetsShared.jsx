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
import { Alert, Box, Button, Stack, TextField, Tooltip, Typography } from '@mui/material';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import { useNavigate } from 'react-router-dom';
import { SearchSelect } from '../../components/Form';
import StatusChip from '../../components/StatusChip';
import NumericText from '../../components/NumericText';
import LtrText from '../../components/LtrText';
import { useAuth } from '../../auth/AuthContext';
import { formatDisplayDate } from '../../utils/dateUtils';
import { formatNumber, formatPercent } from '../../utils/formatNumber';
import {
  fetchCoverageCampusOptions,
  fetchCoverageOrgUnitOptions,
  fetchCoverageOwnerOptions,
} from '../../api/emissions-extended';

/** Isolate a domain term that stays English inside an RTL sentence. */
export { LtrText as Ltr };

export function formatDate(value) {
  if (!value) return '—';
  return formatDisplayDate(value) || '—';
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
  const meta = TIER_META[value];
  return (
    <StatusChip
      value={value}
      label={<LtrText>{meta ? meta.label : String(value)}</LtrText>}
      color={meta?.color}
    />
  );
}

TierChip.propTypes = { value: PropTypes.oneOfType([PropTypes.number, PropTypes.string]) };

const TARGET_STATUS_COLORS = { draft: 'warning', active: 'success', archived: 'default' };
const TARGET_STATUS_KEYS = {
  draft: 'coverageTargets.statusDraft',
  active: 'coverageTargets.statusActive',
  archived: 'coverageTargets.statusArchived',
};

export function TargetStatusChip({ value, t }) {
  return (
    <StatusChip
      value={value}
      label={TARGET_STATUS_KEYS[value] ? t(TARGET_STATUS_KEYS[value]) : (value || '—')}
      color={TARGET_STATUS_COLORS[value]}
    />
  );
}

TargetStatusChip.propTypes = { value: PropTypes.string, t: PropTypes.func.isRequired };

const TASK_STATUS_COLORS = {
  open: 'info', in_progress: 'primary', done: 'success', blocked: 'error',
};
const TASK_STATUS_KEYS = {
  open: 'coverageTargets.taskOpen',
  in_progress: 'coverageTargets.taskInProgress',
  done: 'coverageTargets.taskDone',
  blocked: 'coverageTargets.taskBlocked',
};

export function TaskStatusChip({ value, t }) {
  return (
    <StatusChip
      value={value}
      label={TASK_STATUS_KEYS[value] ? t(TASK_STATUS_KEYS[value]) : (value || '—')}
      color={TASK_STATUS_COLORS[value]}
    />
  );
}

TaskStatusChip.propTypes = { value: PropTypes.string, t: PropTypes.func.isRequired };

const TASK_TYPE_KEYS = {
  bind_data_product: 'coverageTargets.taskTypeBindDataProduct',
  complete_rows: 'coverageTargets.taskTypeCompleteRows',
  fill_gap: 'coverageTargets.taskTypeFillGap',
  secure_factor: 'coverageTargets.taskTypeSecureFactor',
  other: 'coverageTargets.taskTypeOther',
};

export function TaskTypeChip({ value, t }) {
  return (
    <StatusChip
      value={value}
      variant="outlined"
      label={TASK_TYPE_KEYS[value] ? t(TASK_TYPE_KEYS[value]) : (value || '—')}
    />
  );
}

TaskTypeChip.propTypes = { value: PropTypes.string, t: PropTypes.func.isRequired };

export function EvidenceBadge({ evidence, t }) {
  const met = Boolean(evidence && evidence.met);
  return (
    <StatusChip
      color={met ? 'success' : undefined}
      variant={met ? 'filled' : 'outlined'}
      label={met ? t('coverageTargets.evidenceMet') : t('coverageTargets.evidenceWaiting')}
    />
  );
}

EvidenceBadge.propTypes = {
  evidence: PropTypes.shape({ met: PropTypes.bool, codes: PropTypes.array }),
  t: PropTypes.func.isRequired,
};

/* ── Measurement payload · honest progress (no conflated percent) ───────────
 * The backend reports SEPARATE ratios — `measured_pct` (settled WITH a real
 * kilogram), `excluded_pct` (formal exclusions, reported apart) and
 * `settled_at_target_pct` (measured AND at/above the floor, the met gate). The
 * UI never blends them into one figure. `settled_pct` is transparency-only and
 * is deliberately not shown. Everything below reads the payload fields
 * verbatim; nothing here re-derives a number.
 */

// `state` is the target's own declared-goal gate, not a coverage-complete claim.
const TARGET_STATE_META = {
  met: { label: 'coverageTargets.stateMet', color: 'success' },
  short: { label: 'coverageTargets.stateShort', color: 'warning' },
  empty: { label: 'coverageTargets.stateEmpty', color: 'default' },
  invalid_unit: { label: 'coverageTargets.stateInvalidUnit', color: 'error' },
};

export function TargetStateChip({ value, t }) {
  const meta = TARGET_STATE_META[value];
  return (
    <StatusChip
      value={value}
      variant="outlined"
      color={meta?.color}
      label={meta ? t(meta.label) : (value || '—')}
    />
  );
}

TargetStateChip.propTypes = { value: PropTypes.string, t: PropTypes.func.isRequired };

/** An absolute goal is an EMISSIONS-VALUE target, not a coverage KPI. */
export function isEmissionsValueTarget(progress) {
  if (!progress) return false;
  if (progress.metric) return progress.metric === 'absolute_emissions';
  if (progress.goal_concept) return progress.goal_concept === 'emissions_value';
  return progress.goal_kind === 'absolute';
}

/** Human label for the measured value in the goal's own unit, or absent (—). */
export function measuredValueText(t, progress) {
  const unit = (progress?.measured_unit || '').trim();
  const raw = progress?.measured_value;
  if (raw === null || raw === undefined || raw === '') {
    return { value: '—', absent: true, unit };
  }
  const value = formatNumber(raw);
  return { value: unit ? `${value} ${unit}` : value, absent: false, unit };
}

/**
 * Measured and excluded, shown as two separate labelled figures. The measured
 * figure is the settled-WITH-kg ratio; exclusions never inflate it.
 */
export function MeasuredExcludedRatio({ progress, t, emphasis = 'body2' }) {
  return (
    <Stack spacing={0.25} sx={{ alignItems: 'flex-end', minWidth: 0 }}>
      <Stack direction="row" spacing={0.5} sx={{ alignItems: 'baseline' }}>
        <Typography variant="caption" color="text.secondary" noWrap>
          {t('coverageTargets.measuredPctLabel')}
        </Typography>
        <Tooltip title={t('coverageTargets.measuredPctHint')} arrow>
          <span>
            <NumericText variant={emphasis}>{formatPercent(progress?.measured_pct)}</NumericText>
          </span>
        </Tooltip>
      </Stack>
      <Stack direction="row" spacing={0.5} sx={{ alignItems: 'baseline' }}>
        <Typography variant="caption" color="text.secondary" noWrap>
          {t('coverageTargets.excludedPctLabel')}
        </Typography>
        <Tooltip title={t('coverageTargets.excludedPctHint')} arrow>
          <span>
            <NumericText variant="caption">{formatPercent(progress?.excluded_pct)}</NumericText>
          </span>
        </Tooltip>
      </Stack>
    </Stack>
  );
}

MeasuredExcludedRatio.propTypes = {
  progress: PropTypes.object,
  t: PropTypes.func.isRequired,
  emphasis: PropTypes.string,
};

MeasuredExcludedRatio.defaultProps = { progress: null, emphasis: 'body2' };

/**
 * Quality-floor flags: a below-floor or tier-unknown stream must never look
 * like a settled-at-target one. Rendered with the shared StatusChip only.
 */
export function QualityFloorFlags({ progress, t }) {
  const counts = progress?.counts || {};
  const below = counts.below_floor || 0;
  const unknown = counts.tier_unknown || 0;
  if (!below && !unknown) return null;
  return (
    <Stack
      direction="row"
      spacing={0.5}
      sx={{ flexWrap: 'wrap', gap: 0.5, justifyContent: 'flex-end' }}
    >
      {below > 0 && (
        <Tooltip title={t('coverageTargets.belowFloorHint')} arrow>
          <span>
            <StatusChip
              color="warning"
              variant="outlined"
              label={t('coverageTargets.belowFloor', { count: below })}
            />
          </span>
        </Tooltip>
      )}
      {unknown > 0 && (
        <Tooltip title={t('coverageTargets.tierUnknownHint')} arrow>
          <span>
            <StatusChip
              color="info"
              variant="outlined"
              label={t('coverageTargets.tierUnknown', { count: unknown })}
            />
          </span>
        </Tooltip>
      )}
    </Stack>
  );
}

QualityFloorFlags.propTypes = { progress: PropTypes.object, t: PropTypes.func.isRequired };
QualityFloorFlags.defaultProps = { progress: null };

const FINDING_META = {
  no_declared_sources: {
    label: 'coverageTargets.findingNoDeclaredSources',
    short: 'coverageTargets.findingNoDeclaredSourcesShort',
    severity: 'warning',
  },
  goal_unit_not_co2e: {
    label: 'coverageTargets.findingGoalUnitNotCo2e',
    short: 'coverageTargets.findingGoalUnitNotCo2eShort',
    severity: 'error',
  },
};

export function findingCodes(progress) {
  return (progress?.findings || []).map((f) => f.code).filter(Boolean);
}

export function hasFinding(progress, code) {
  return findingCodes(progress).includes(code);
}

/** Compact, headlined labels for a grid cell (full sentences live in Alerts). */
export function FindingChips({ progress, t }) {
  const findings = progress?.findings || [];
  if (!findings.length) return null;
  return (
    <Stack direction="row" spacing={0.5} sx={{ flexWrap: 'wrap', gap: 0.5, justifyContent: 'flex-end' }}>
      {findings.map((f, i) => {
        const meta = FINDING_META[f.code];
        return (
          <StatusChip
            key={f.code || i}
            color={meta?.severity}
            variant="outlined"
            label={t(meta ? meta.short : 'coverageTargets.findingGeneric')}
          />
        );
      })}
    </Stack>
  );
}

FindingChips.propTypes = { progress: PropTypes.object, t: PropTypes.func.isRequired };
FindingChips.defaultProps = { progress: null };

/* ── Compact grid progress (design note · 3 Oct 2026) ──────────────────────
 * The grid is a SCANNABLE SUMMARY: ONE measured figure + at most ONE status
 * chip per row. The breakdown (excluded share, quality floor, findings and — for
 * an absolute goal — the measured value) lives behind ONE Tooltip here and, in
 * full, on the DETAIL page. Grid rows carry no action buttons: the deliberate
 * `Open target` action and the full gap set live on the detail page.
 */
export function ProgressBreakdown({ progress, t }) {
  const counts = progress?.counts || {};
  const empty = progress?.state === 'empty' || !counts.required;
  const emissions = isEmissionsValueTarget(progress);
  const measuredValue = measuredValueText(t, progress);
  const findings = progress?.findings || [];
  const below = counts.below_floor || 0;
  const unknown = counts.tier_unknown || 0;
  return (
    <Stack spacing={0.25} sx={{ py: 0.25, maxWidth: 300 }}>
      {!empty && (
        <Typography variant="body2">
          {`${t('coverageTargets.measuredPctLabel')}: `}
          <NumericText>{formatPercent(progress?.measured_pct)}</NumericText>
        </Typography>
      )}
      {!empty && (
        <Typography variant="body2">
          {`${t('coverageTargets.excludedPctLabel')}: `}
          <NumericText>{formatPercent(progress?.excluded_pct)}</NumericText>
        </Typography>
      )}
      {emissions && (
        <Typography variant="body2">
          {measuredValue.absent
            ? t('coverageTargets.measuredValueAbsent')
            : t('coverageTargets.measuredValue', { value: measuredValue.value })}
        </Typography>
      )}
      {below > 0 && (
        <Typography variant="body2">{t('coverageTargets.belowFloor', { count: below })}</Typography>
      )}
      {unknown > 0 && (
        <Typography variant="body2">{t('coverageTargets.tierUnknown', { count: unknown })}</Typography>
      )}
      {findings.map((finding, i) => {
        const meta = FINDING_META[finding.code];
        return (
          <Typography variant="body2" key={finding.code || i}>
            {t(meta ? meta.label : 'coverageTargets.findingGeneric')}
          </Typography>
        );
      })}
      <Typography variant="caption" color="text.secondary">
        {t('coverageTargets.measuredNotClaimed')}
      </Typography>
    </Stack>
  );
}

ProgressBreakdown.propTypes = {
  progress: PropTypes.object,
  t: PropTypes.func.isRequired,
};

ProgressBreakdown.defaultProps = { progress: null };

/** The grid's ONE compact progress signal: a measured figure + one status. */
export function CompactProgressCell({ progress, t }) {
  const counts = progress?.counts || {};
  const empty = progress?.state === 'empty' || !counts.required;
  const emissions = isEmissionsValueTarget(progress);
  const measuredValue = measuredValueText(t, progress);
  let figure = '—';
  if (!empty) {
    // An absolute goal reports its measured value in the goal's own unit;
    // a percent goal reports the measured (with kg) ratio.
    figure = emissions
      ? (measuredValue.absent ? '—' : measuredValue.value)
      : formatPercent(progress?.measured_pct);
  }
  return (
    <Tooltip title={<ProgressBreakdown progress={progress} t={t} />} arrow>
      <Stack
        direction="row"
        spacing={0.75}
        sx={{
          alignItems: 'center',
          justifyContent: 'flex-end',
          minWidth: 0,
          width: '100%',
          overflow: 'hidden',
        }}
      >
        <NumericText>{figure}</NumericText>
        {hasFinding(progress, 'no_declared_sources') ? (
          <StatusChip
            color="warning"
            variant="outlined"
            label={t('coverageTargets.findingNoDeclaredSourcesShort')}
          />
        ) : (
          <TargetStateChip value={progress?.state} t={t} />
        )}
      </Stack>
    </Tooltip>
  );
}

CompactProgressCell.propTypes = {
  progress: PropTypes.object,
  t: PropTypes.func.isRequired,
};

CompactProgressCell.defaultProps = { progress: null };

/** Full, explicit findings — a headlined finding, never a blank row. */
export function FindingsAlerts({ progress, t }) {
  const findings = progress?.findings || [];
  if (!findings.length) return null;
  return (
    <Stack spacing={1} sx={{ mb: 1.5 }}>
      {findings.map((f, i) => {
        const meta = FINDING_META[f.code];
        return (
          <Alert key={f.code || i} severity={meta?.severity || 'warning'} variant="outlined">
            <Typography component="span" variant="body2" sx={{ fontWeight: 600, mr: 0.5 }}>
              {t('coverageTargets.findingHeadline')}
            </Typography>
            {t(meta ? meta.label : 'coverageTargets.findingGeneric')}
          </Alert>
        );
      })}
    </Stack>
  );
}

FindingsAlerts.propTypes = { progress: PropTypes.object, t: PropTypes.func.isRequired };
FindingsAlerts.defaultProps = { progress: null };

/** Human label for a target goal (percent or absolute + unit). */
export function goalLabel(target) {
  if (!target) return '—';
  if (target.goal_value === null || target.goal_value === undefined || target.goal_value === '') {
    return '—';
  }
  if (target.goal_kind === 'absolute') {
    const unit = (target.goal_unit || '').trim();
    const value = formatNumber(target.goal_value);
    return unit ? `${value} ${unit}` : value;
  }
  return formatPercent(target.goal_value);
}

/**
 * Human label for a target scope (+ scope 3 category) as a plain string.
 *
 * ADR-0018 / audit M4: the translatable word ("Scope" / "Cat") is localized,
 * while the GHG scope code is a Latin domain value that stays as-is. Use
 * ``ScopeLabel`` when rendering into the page so only the Latin code is
 * bdi-isolated; use this string form for filter options and i18n interpolation.
 */
export function scopeLabel(t, target) {
  if (!target) return '—';
  const code = target.scope != null && target.scope !== '' ? String(target.scope) : null;
  const base = code
    ? t('coverageTargets.scopeValue', { code })
    : (target.scope_display || '—');
  return target.scope3_category != null
    ? `${base} · ${t('coverageTargets.scopeCategoryValue', { category: target.scope3_category })}`
    : base;
}

/**
 * Rendered scope label: the localized word stays in the sentence direction and
 * only the Latin GHG code / category is wrapped in the shared bdi primitive.
 */
export function ScopeLabel({ target, t }) {
  if (!target) return '—';
  const code = target.scope != null && target.scope !== '' ? String(target.scope) : null;
  const base = code ? (
    <>
      {t('coverageTargets.scopeWord')}
      {' '}
      <LtrText>{code}</LtrText>
    </>
  ) : (
    <LtrText>{target.scope_display || '—'}</LtrText>
  );
  if (target.scope3_category == null) return base;
  return (
    <>
      {base}
      {' · '}
      {t('coverageTargets.scopeCategoryWord')}
      {' '}
      <LtrText>{String(target.scope3_category)}</LtrText>
    </>
  );
}

ScopeLabel.propTypes = {
  target: PropTypes.object,
  t: PropTypes.func.isRequired,
};

ScopeLabel.defaultProps = { target: null };

/**
 * Shared progress summary line for board and detail. Composed from the SAME
 * keys the board's ratio uses (`measuredPctLabel` / `excludedPctLabel`), so the
 * detail line and the board never drift into different words for one concept.
 */
export function progressSummaryText(t, progress) {
  const counts = progress?.counts || {};
  if (!counts.required) {
    return hasFinding(progress, 'no_declared_sources')
      ? t('coverageTargets.findingNoDeclaredSourcesShort')
      : t('coverageTargets.emptyProgress');
  }
  return `${t('coverageTargets.measuredPctLabel')}: ${formatPercent(progress?.measured_pct)} · `
    + `${t('coverageTargets.excludedPctLabel')}: ${formatPercent(progress?.excluded_pct)}`;
}

/* ── Next actions · the live gap set, each naming its verb and its stream ───
 * Derived server-side from the real stream states (`progress.next_actions`).
 * Nothing here is hardcoded per target: the stream ids come from the payload,
 * and the CTA prefills the real intake verb for the affected stream.
 */
const GAP_META = {
  no_declared_sources: {
    label: 'coverageTargets.gapNoDeclaredSources',
    verb: 'coverageTargets.verbDeclareSources',
  },
  missing: { label: 'coverageTargets.gapMissing', verb: 'coverageTargets.verbEnterStream' },
  in_progress: { label: 'coverageTargets.gapInProgress', verb: 'coverageTargets.verbCompleteEntry' },
  awaiting_factor: { label: 'coverageTargets.gapAwaitingFactor', verb: 'coverageTargets.verbSecureFactor' },
  below_floor: { label: 'coverageTargets.gapBelowFloor', verb: 'coverageTargets.verbImproveQuality' },
  tier_unknown: { label: 'coverageTargets.gapTierUnknown', verb: 'coverageTargets.verbDeclareTier' },
};

/** Localized name for a completeness gap code (falls back to the raw code). */
export function gapLabel(t, code) {
  const meta = GAP_META[code];
  return meta ? t(meta.label) : (code || '—');
}

export function NextActions({ progress, t, dense = false }) {
  const navigate = useNavigate();
  // A legacy payload without the field shows nothing; a live empty array means
  // the gap set is genuinely clear.
  if (!Array.isArray(progress?.next_actions)) return null;
  const actions = progress.next_actions;
  if (!actions.length) {
    return dense ? null : (
      <Typography variant="body2" color="text.secondary">
        {t('coverageTargets.nextActionsClear')}
      </Typography>
    );
  }
  const shown = dense ? actions.slice(0, 1) : actions;
  return (
    <Stack spacing={0.5} sx={{ alignItems: 'flex-start', width: '100%' }}>
      {shown.map((action) => {
        const meta = GAP_META[action.code];
        const first = action.streams && action.streams[0];
        return (
          <Stack
            key={action.code}
            direction="row"
            spacing={0.5}
            sx={{ alignItems: 'center', flexWrap: 'wrap', gap: 0.5 }}
          >
            <StatusChip
              color="info"
              variant="outlined"
              label={t('coverageTargets.nextActionGap', {
                gap: gapLabel(t, action.code),
                count: action.count,
              })}
            />
            <Typography variant="caption" color="text.secondary">
              {meta ? t(meta.verb) : action.verb}
            </Typography>
            {first ? (
              <Button
                size="small"
                variant="outlined"
                endIcon={<OpenInNewIcon fontSize="small" />}
                onClick={() => navigate(`/carbon/onboarding/intake?source=${first.inventory_source_id}`)}
              >
                {t('coverageTargets.nextActionOpenStream', { name: first.source_name })}
              </Button>
            ) : (
              <Button
                size="small"
                variant="outlined"
                endIcon={<OpenInNewIcon fontSize="small" />}
                onClick={() => navigate('/carbon/admin/inventory-coverage')}
              >
                {t('coverageTargets.nextActionDeclareSources')}
              </Button>
            )}
            {!dense && action.streams && action.streams.length > 1 && (
              <Typography variant="caption" color="text.secondary">
                {t('coverageTargets.nextActionMore', { count: action.streams.length - 1 })}
              </Typography>
            )}
          </Stack>
        );
      })}
    </Stack>
  );
}

NextActions.propTypes = {
  progress: PropTypes.object,
  t: PropTypes.func.isRequired,
  dense: PropTypes.bool,
};

NextActions.defaultProps = { progress: null, dense: false };

/* ── Task closure · what a task declares it closes and whether it did ───────
 * `closes` is derived server-side: evidence met AND the declared gap really
 * changed. A done task whose data did not move reads `open`, never closed.
 */
const CLOSURE_META = {
  closed: { label: 'coverageTargets.taskClosureClosed', color: 'success' },
  open: { label: 'coverageTargets.taskClosureOpen', color: 'warning' },
  awaiting_evidence: { label: 'coverageTargets.taskClosureAwaiting', color: 'default' },
};

export function TaskClosureBadge({ closes, t }) {
  if (!closes) return null;
  const meta = CLOSURE_META[closes.state];
  return (
    <StatusChip
      color={meta?.color}
      variant={closes.state === 'closed' ? 'filled' : 'outlined'}
      label={meta ? t(meta.label) : (closes.state || '—')}
    />
  );
}

TaskClosureBadge.propTypes = {
  closes: PropTypes.shape({
    state: PropTypes.string,
    gap: PropTypes.string,
    gap_changed: PropTypes.bool,
    evidence_met: PropTypes.bool,
  }),
  t: PropTypes.func.isRequired,
};

TaskClosureBadge.defaultProps = { closes: null };

/** One-line goal summary used as a WorkflowCard description. */
export function goalSummary(t, target) {
  if (!target) return '';
  const campus = target.campus_name || target.org_unit_name || '—';
  const scope = scopeLabel(t, target);
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
