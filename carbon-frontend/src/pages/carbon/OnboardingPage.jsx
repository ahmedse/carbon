// AASTMT inventory onboarding (benchmark O1).
// The checklist comes from GET carbon/onboarding/o1/ (evaluate_o1).
// This page does not decide the rules and does not write records.

import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Alert, Box, Button, Typography } from '@mui/material';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import AssignmentTurnedInIcon from '@mui/icons-material/AssignmentTurnedIn';
import CalculateIcon from '@mui/icons-material/Calculate';
import EventAvailableIcon from '@mui/icons-material/EventAvailable';
import ScienceIcon from '@mui/icons-material/Science';
import AddCircleOutlineIcon from '@mui/icons-material/AddCircleOutline';
import FactCheckIcon from '@mui/icons-material/FactCheck';
import ChatIcon from '@mui/icons-material/Chat';
import PlaylistAddIcon from '@mui/icons-material/PlaylistAdd';
import { useTranslation } from 'react-i18next';

import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import EmptyState from '../../components/Page/EmptyState';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import WorkflowCard from '../../components/Cards/WorkflowCard';
import { fetchOnboardingO1 } from '../../api/emissions-extended';

const STEPS = [
  { id: 'name_boundary', title: 'onboarding.stepBoundary', hint: 'onboarding.stepBoundaryHint', path: '/carbon/admin/boundaries', icon: <AccountTreeIcon /> },
  { id: 'open_period', title: 'onboarding.stepPeriod', hint: 'onboarding.stepPeriodHint', path: '/carbon/reporting/periods', icon: <EventAvailableIcon /> },
  { id: 'declare_sources', title: 'onboarding.stepSources', hint: 'onboarding.stepSourcesHint', path: '/carbon/admin/inventory-coverage', icon: <PlaylistAddIcon /> },
  { id: 'bind_factors', title: 'onboarding.stepFactors', hint: 'onboarding.stepFactorsHint', path: '/carbon/admin/factors', icon: <ScienceIcon /> },
  { id: 'enter_activity', title: 'onboarding.stepActivity', hint: 'onboarding.stepActivityHint', path: '/carbon/my-data', icon: <AddCircleOutlineIcon /> },
  { id: 'calculate', title: 'onboarding.stepCalculate', hint: 'onboarding.stepCalculateHint', path: '/carbon/calculations', icon: <CalculateIcon /> },
  { id: 'cover_or_exclude', title: 'onboarding.stepCover', hint: 'onboarding.stepCoverHint', path: '/carbon/admin/inventory-coverage', icon: <FactCheckIcon /> },
  { id: 'verify_quote', title: 'onboarding.stepQuote', hint: 'onboarding.stepQuoteHint', path: null, icon: <ChatIcon /> },
];

const COPY = {
  open_period_count: 'onboarding.openPeriodCount',
  open_period_dates: 'onboarding.openPeriodDates',
  open_period_type: 'onboarding.openPeriodType',
  open_period_met: 'onboarding.openPeriodMet',
  boundary_missing: 'onboarding.boundaryMissing',
  boundary_approach: 'onboarding.boundaryApproach',
  boundary_met: 'onboarding.boundaryMet',
  source_missing: 'onboarding.sourceMissing',
  source_no_status: 'onboarding.sourceNoStatus',
  source_excluded: 'onboarding.sourceExcluded',
  source_covered: 'onboarding.sourceCovered',
  source_covered_invalid: 'onboarding.sourceCoveredInvalid',
  source_declared: 'onboarding.sourceDeclared',
  diesel_stream_missing: 'onboarding.dieselStreamMissing',
  diesel_stream_both: 'onboarding.dieselStreamBoth',
  diesel_stream_met: 'onboarding.dieselStreamMet',
  no_calculation: 'onboarding.noCalculation',
  summary_kg: 'onboarding.kgFromSummary',
  not_assured: 'onboarding.notAssured',
  other_campus: 'onboarding.otherCampus',
  other_campus_absent: 'onboarding.otherCampusAbsent',
  other_campus_no_status: 'onboarding.otherCampusNoStatus',
  other_campus_declared: 'onboarding.otherCampusDeclared',
  other_campus_excluded: 'onboarding.otherCampusExcluded',
  other_campus_excluded_notes: 'onboarding.otherCampusExcludedNotes',
  other_campus_not_material: 'onboarding.otherCampusNotMaterial',
  other_campus_covered: 'onboarding.otherCampusCovered',
  factor_missing: 'onboarding.factorMissing',
  factor_inactive: 'onboarding.factorInactive',
  factor_country: 'onboarding.factorCountry',
  factor_source_blank: 'onboarding.factorSourceBlank',
  factor_met: 'onboarding.factorMet',
  coverage_goal_absent: 'onboarding.coverageGoalAbsent',
  coverage_goal_completeness: 'onboarding.coverageGoalCompleteness',
  coverage_goal_tier: 'onboarding.coverageGoalTier',
  coverage_goal_status: 'onboarding.coverageGoalStatus',
  coverage_goal_met: 'onboarding.coverageGoalMet',
};

function blankCountryLabel(language) {
  return language?.startsWith('ar') ? 'فارغ' : 'blank';
}

function displayCountryCode(check, language) {
  const cc = check.country_code;
  if (cc == null || (typeof cc === 'string' && !cc.trim())) {
    return blankCountryLabel(language);
  }
  return cc;
}

function openPeriodDisplayName(period) {
  const name = period?.name;
  if (typeof name === 'string' && name.trim()) return name.trim();
  return String(period?.id ?? '');
}

function checklistItems(checks, t, language) {
  const items = [];
  checks.forEach((check, index) => {
    const keyBase = `${check.id}-${check.code}-${index}`;
    const color = check.met ? 'success.main' : 'warning.main';
    items.push({ key: keyBase, color, text: checkText(t, check, language) });
    if (
      check.code === 'open_period_count'
      && Array.isArray(check.periods)
      && check.periods.length > 0
    ) {
      check.periods.forEach((period, periodIndex) => {
        items.push({
          key: `${keyBase}-period-${period.id ?? periodIndex}`,
          color,
          text: t('onboarding.openPeriodNamed', {
            name: openPeriodDisplayName(period),
            id: period.id,
            period_type: period.period_type,
            start: period.start_date,
            end: period.end_date,
          }),
        });
      });
    }
  });
  return items;
}

function checkText(t, check, language) {
  const key = COPY[check.code];
  if (!key) return check.code;
  const countryForFactor = (check.code === 'factor_met' || check.code === 'factor_country')
    ? displayCountryCode(check, language)
    : check.country_code;
  return t(key, {
    count: check.count,
    name: check.name,
    id: check.record_id != null && check.record_id !== '' ? check.record_id : check.id,
    start: check.start,
    end: check.end,
    type: check.period_type,
    period_type: check.period_type,
    approach: check.approach,
    scope: check.scope,
    reason: check.reason,
    kg: check.kg,
    stream: check.stream,
    status: check.status,
    unit: check.unit,
    country_code: countryForFactor,
    completeness: check.completeness,
    tier: check.tier,
    target_year: check.target_year,
  });
}

export default function OnboardingPage() {
  const { t, i18n } = useTranslation('emissions');
  const { token } = useAuth();
  const navigate = useNavigate();
  useDocumentTitle(t('onboarding.title'));

  const [phase, setPhase] = useState('loading');
  const [error, setError] = useState('');
  const [payload, setPayload] = useState(null);

  const load = useCallback(async () => {
    setPhase('loading');
    setError('');
    try {
      const data = await fetchOnboardingO1(token);
      setPayload(data && typeof data === 'object' ? data : { checks: [] });
      setPhase('loaded');
    } catch (err) {
      setPayload(null);
      setError(err?.message || t('onboarding.loadFailed'));
      setPhase('error');
    }
  }, [token, t]);

  useEffect(() => {
    load();
  }, [load]);

  const checks = Array.isArray(payload?.checks) ? payload.checks : [];
  const openPeriodCountCheck = checks.find((check) => check.code === 'open_period_count');
  const tooManyOpenPeriods = phase === 'loaded'
    && openPeriodCountCheck != null
    && !openPeriodCountCheck.met
    && Number(openPeriodCountCheck.count) > 1;
  const noOpenPeriod = phase === 'loaded' && payload?.open_period_id == null
    && checks.length === 1 && checks[0].code === 'open_period_count' && Number(checks[0].count) === 0;

  return (
    <PageContainer>
      <PageHeader
        icon={AssignmentTurnedInIcon}
        title={t('onboarding.title')}
        subtitle={t('onboarding.subtitle')}
        description={t('onboarding.description')}
        actions={(
          <Button variant="contained" size="small" onClick={load}>
            {t('onboarding.refresh')}
          </Button>
        )}
      />

      {phase === 'loading' && <LoadingSkeleton variant="console" />}

      {phase === 'error' && (
        <Alert
          severity="error"
          action={(
            <Button color="inherit" size="small" onClick={load}>
              {t('common:retry')}
            </Button>
          )}
        >
          {error || t('onboarding.loadFailed')}
        </Alert>
      )}

      {noOpenPeriod && (
        <EmptyState title={t('onboarding.emptyTitle')} description={t('onboarding.emptyDescription')} />
      )}

      {tooManyOpenPeriods && (
        <Alert
          severity="warning"
          sx={{ mb: 1.5 }}
          action={(
            <Button
              color="inherit"
              size="small"
              onClick={() => navigate('/carbon/reporting/periods')}
            >
              {t('onboarding.openPeriods')}
            </Button>
          )}
        >
          {t('onboarding.tooManyOpen')}
          <Typography component="div" sx={{ fontSize: '0.8125rem', mt: 0.5 }}>
            {t('onboarding.tooManyOpenHint')}
          </Typography>
        </Alert>
      )}

      {phase === 'loaded' && !noOpenPeriod && (
        <Box component="ul" sx={{ m: 0, pl: 2.5, display: 'grid', gap: 0.75 }}>
          {checklistItems(checks, t, i18n.language).map((item) => (
            <Typography
              key={item.key}
              component="li"
              sx={{ fontSize: '0.8125rem', color: item.color }}
            >
              {item.text}
            </Typography>
          ))}
        </Box>
      )}

      {phase === 'loaded' && (
        <Box sx={{ display: 'grid', gap: 1, mt: 1.5 }}>
          <Typography sx={{ fontSize: '0.75rem', fontWeight: 600 }}>
            {t('onboarding.stepsTitle')}
          </Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 1 }}>
            {STEPS.map((step) => (
              <WorkflowCard
                key={step.id}
                icon={step.icon}
                title={t(step.title)}
                description={t(step.hint)}
                onClick={step.path ? () => navigate(step.path) : undefined}
              />
            ))}
          </Box>
        </Box>
      )}
    </PageContainer>
  );
}
