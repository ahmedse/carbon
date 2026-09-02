// src/apps/people/EmployeeDetailPage.jsx
// Employee 360 — hero + live-KPI ribbon + 5-tab unified profile.
// Design principles: Rippling/Workday-style hero; tabs are modules not forms;
// data for ALL tabs loaded once (parallel); Pay tab is lazy on first activate.

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  IconButton,
  Tab,
  Tabs,
  Tooltip,
  Typography,
  useTheme,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import WorkHistoryIcon from '@mui/icons-material/WorkHistory';
import EventAvailableIcon from '@mui/icons-material/EventAvailable';
import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet';
import LocalAtmIcon from '@mui/icons-material/LocalAtm';
import BadgeIcon from '@mui/icons-material/Badge';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import { useNotes } from '../../notes/NotesContext';
import { registerEmployeeInspectorTabs } from '../../inspector/tabs/employeeTabs';
import {
  fetchEmployee, fetchEmployees,
  fetchLeaveEntitlements, fetchLeaveRecords,
  fetchEmployeeBenefits, fetchLoans, fetchCertifications,
  fetchEmployeeTimeline,
} from '../../api/people';
import { fetchOrgUnits } from '../../api/orgUnits';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import PageContainer from '../../components/layout/PageContainer';
import EmployeeOverviewTab from './tabs/EmployeeOverviewTab';
import EmployeeTimelineTab from './tabs/EmployeeTimelineTab';
import EmployeeLeaveTab from './tabs/EmployeeLeaveTab';
import EmployeePayTab from './tabs/EmployeePayTab';
import EmployeeCertsTab from './tabs/EmployeeCertsTab';
import { tenureLabel, totalLeaveBalance, expiryUrgency } from './utils';

const STORAGE_KEY = 'carbonEmployee360';
const TAB_KEYS = ['Profile', 'Timeline', 'Leave', 'Pay', 'Certs'];
const TAB_COMPONENTS = [EmployeeOverviewTab, EmployeeTimelineTab, EmployeeLeaveTab, EmployeePayTab, EmployeeCertsTab];

function getInitials(emp) {
  if (emp.name_en_given && emp.name_en_family) {
    return `${emp.name_en_given[0]}${emp.name_en_family[0]}`.toUpperCase();
  }
  const parts = (emp.full_name || '').trim().split(/\s+/);
  if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
  return (emp.full_name || 'EE').slice(0, 2).toUpperCase();
}

function StatKpi({ icon: Icon, label, value, warn }) {
  const theme = useTheme();
  return (
    <Box sx={{
      display: 'flex', alignItems: 'center', gap: 0.75,
      px: 1.25, py: 0.625,
      bgcolor: warn ? `${theme.palette.error.main}14` : 'action.hover',
      borderRadius: 1.5, flexShrink: 0,
    }}>
      <Icon sx={{ fontSize: '0.9375rem', color: warn ? 'error.main' : 'text.secondary' }} />
      <Box>
        <Typography sx={{ fontSize: '0.875rem', fontWeight: 700, lineHeight: 1.1, color: warn ? 'error.main' : 'text.primary' }}>
          {value}
        </Typography>
        <Typography sx={{ fontSize: '0.5rem', color: 'text.disabled', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
          {label}
        </Typography>
      </Box>
    </Box>
  );
}

export default function EmployeeDetailPage() {
  const { t } = useTranslation('people');
  const { t: tCommon } = useTranslation('common');
  const { employeeId } = useParams();
  const navigate = useNavigate();
  const { token } = useAuth();
  const { notify } = useNotification();
  const theme = useTheme();
  useDocumentTitle(t('employeeDetailsTitle'));

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [tabIndex, setTabIndex] = useState(() => {
    const n = parseInt(localStorage.getItem(`${STORAGE_KEY}:tab`) || '0', 10);
    return Number.isFinite(n) ? Math.min(n, TAB_KEYS.length - 1) : 0;
  });

  const loadData = useCallback(async () => {
    if (!employeeId || !token) return;
    try {
      setLoading(true);
      setError(null);
      const [emp, orgUnits, allEmps, leaveEnts, leaveRecs, bens, loans, certs, timeline] = await Promise.all([
        fetchEmployee(employeeId, token),
        fetchOrgUnits(token),
        fetchEmployees(token),
        fetchLeaveEntitlements(token),
        fetchLeaveRecords(token),
        fetchEmployeeBenefits(token),
        fetchLoans(token),
        fetchCertifications(token),
        fetchEmployeeTimeline(employeeId, token).catch(() => []),
      ]);

      const allOrgUnits = Array.isArray(orgUnits) ? orgUnits : [];
      const allEmployees = Array.isArray(allEmps) ? allEmps : (allEmps?.results || []);
      const orgUnitName = allOrgUnits.find(u => u.id === emp.org_unit)?.name || null;
      const manager = allEmployees.find(e => e.id === emp.manager);
      const managerLabel = manager
        ? `${manager.employee_no ?? '—'} — ${manager.full_name ?? ''}`
        : t('managerUnassigned');

      const toArr = v => Array.isArray(v?.results) ? v.results : (Array.isArray(v) ? v : []);

      setData({
        ...emp,
        orgUnitName,
        managerLabel,
        allOrgUnits,
        allEmployees,
        leaveEntitlements: toArr(leaveEnts),
        leaveRecords: toArr(leaveRecs),
        benefits: toArr(bens),
        loans: toArr(loans),
        certifications: toArr(certs),
        timelineEvents: Array.isArray(timeline) ? timeline : [],
        empId: emp.id,
      });
    } catch (err) {
      const msg = err?.message || t('employeesLoadError');
      setError(msg);
      notify({ message: msg, type: 'error' });
    } finally {
      setLoading(false);
    }
  }, [employeeId, token, notify, t]);

  useEffect(() => { loadData(); }, [loadData]);

  // Inspector drawer wiring
  const { setContexts } = useNotes();
  useEffect(() => registerEmployeeInspectorTabs(), []);
  useEffect(() => {
    if (!data) return;
    setContexts([{
      entityType: 'employee', entityId: employeeId, label: data.full_name,
      payload: { entityData: data },
    }]);
    return () => setContexts(null);
  }, [data, employeeId, setContexts]);

  const handleTabChange = (_, v) => {
    setTabIndex(v);
    localStorage.setItem(`${STORAGE_KEY}:tab`, v);
  };

  // --- Live KPIs computed from loaded data ---
  const kpis = useMemo(() => {
    if (!data) return null;
    const today = new Date().toISOString().slice(0, 10);
    const currentYear = new Date().getFullYear();
    const id = data.empId;

    const myEnts = data.leaveEntitlements.filter(e => e.employee === id && e.year === currentYear);
    const leaveBalance = totalLeaveBalance(myEnts);

    const activeBenefits = data.benefits.filter(
      b => b.employee === id && (!b.effective_end || b.effective_end >= today)
    ).length;

    const activeLoans = data.loans.filter(l => l.employee === id && l.status === 'active').length;

    const myCerts = data.certifications.filter(c => c.employee === id);
    const urgentCerts = myCerts.filter(c => {
      const u = expiryUrgency(c.expiry_date);
      return u === 'expired' || u === 'critical' || u === 'warning';
    }).length;

    return {
      tenure: tenureLabel(data.join_date),
      leaveBalance: leaveBalance.toFixed(1),
      activeBenefits,
      activeLoans,
      certsTotal: myCerts.length,
      urgentCerts,
    };
  }, [data]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh' }}>
        <CircularProgress size={32} />
      </Box>
    );
  }

  if (error || !data) {
    return (
      <PageContainer>
        <Alert severity="error" sx={{ mb: 1 }}>{error}</Alert>
        <Button size="small" startIcon={<ArrowBackIcon />} onClick={() => navigate('/people/employees')}>
          {tCommon('back')}
        </Button>
      </PageContainer>
    );
  }

  const TabComponent = TAB_COMPONENTS[tabIndex];
  const arName = [data.name_ar_given, data.name_ar_family].filter(Boolean).join(' ');

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0, bgcolor: 'background.default' }}>

      {/* ── Hero ── */}
      <Box sx={{ bgcolor: 'background.paper', borderBottom: 1, borderColor: 'divider', px: 2, pt: 1.25, pb: 1, flexShrink: 0 }}>
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1.5 }}>
          <IconButton size="small" onClick={() => navigate('/people/employees')} sx={{ mt: 0.375, flexShrink: 0 }}>
            <ArrowBackIcon sx={{ fontSize: '1rem' }} />
          </IconButton>

          {/* Avatar / Photo */}
          {data.photo ? (
            <Box
              component="img"
              src={data.photo}
              alt={data.full_name}
              sx={{
                width: 52, height: 52, borderRadius: '50%', flexShrink: 0,
                objectFit: 'cover',
                boxShadow: `0 0 0 3px ${theme.palette.primary.main}22`,
              }}
            />
          ) : (
            <Box sx={{
              width: 52, height: 52, borderRadius: '50%', flexShrink: 0,
              bgcolor: 'primary.main', color: 'primary.contrastText',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '1.125rem', fontWeight: 700, letterSpacing: '-0.02em',
              boxShadow: `0 0 0 3px ${theme.palette.primary.main}22`,
            }}>
              {getInitials(data)}
            </Box>
          )}

          {/* Identity */}
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
              <Typography sx={{ fontSize: '1rem', fontWeight: 700, lineHeight: 1.25 }}>
                {data.full_name}
              </Typography>
              {arName && (
                <Typography sx={{ fontSize: '0.875rem', color: 'text.secondary', direction: 'rtl', fontStyle: 'italic' }}>
                  {arName}
                </Typography>
              )}
              <Chip
                size="small"
                label={data.is_active ? t('statusActive') : t('statusInactive')}
                color={data.is_active ? 'success' : 'default'}
                sx={{ height: 18, fontSize: '0.6rem' }}
              />
            </Box>
            <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary', mt: 0.125 }}>
              {[data.employee_no, data.employment_type_code || null, data.orgUnitName].filter(Boolean).join(' · ')}
            </Typography>
          </Box>
        </Box>

        {/* ── Stats ribbon ── */}
        {kpis && (
          <Box sx={{ display: 'flex', gap: 0.75, mt: 1.125, flexWrap: 'wrap' }}>
            {kpis.tenure && (
              <StatKpi icon={WorkHistoryIcon} label={t('statsService')} value={kpis.tenure} />
            )}
            <StatKpi icon={EventAvailableIcon} label={t('statsLeave')} value={`${kpis.leaveBalance}d`} />
            <StatKpi icon={AccountBalanceWalletIcon} label={t('statsBenefits')} value={kpis.activeBenefits} />
            <StatKpi icon={LocalAtmIcon} label={t('statsLoans')} value={kpis.activeLoans} />
            <Tooltip title={kpis.urgentCerts > 0 ? t('statsCertsWarn', { count: kpis.urgentCerts }) : ''} placement="top">
              <span>
                <StatKpi
                  icon={BadgeIcon}
                  label={t('statsCerts')}
                  value={kpis.urgentCerts > 0 ? `${kpis.certsTotal} ⚠` : kpis.certsTotal}
                  warn={kpis.urgentCerts > 0}
                />
              </span>
            </Tooltip>
          </Box>
        )}
      </Box>

      {/* ── Tab bar ── */}
      <Box sx={{ bgcolor: 'background.paper', borderBottom: 1, borderColor: 'divider', flexShrink: 0 }}>
        <Tabs value={tabIndex} onChange={handleTabChange} variant="scrollable" scrollButtons="auto">
          {TAB_KEYS.map((k, i) => (
            <Tab
              key={k}
              label={t(`tab${k}`)}
              sx={{ minHeight: 36, fontSize: '0.8125rem', fontWeight: tabIndex === i ? 600 : 400, textTransform: 'none', py: 0.75 }}
            />
          ))}
        </Tabs>
      </Box>

      {/* ── Tab content ── */}
      <Box sx={{ flex: 1, overflow: 'auto', bgcolor: 'background.paper' }}>
        {TabComponent && (
          <TabComponent entityData={data} additionalProps={{ onSaved: loadData, token }} />
        )}
      </Box>
    </Box>
  );
}

