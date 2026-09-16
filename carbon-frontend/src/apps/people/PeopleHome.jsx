// src/apps/people/PeopleHome.jsx
// People (Nibras HR & Payroll) — ops landing for go-live modules.
// Links to Employees, Leave, Payroll, Policies, Loans.
// NSR-6A Path H: Attendance omitted (routes may still deep-link; not go-live).
// Optional soft counts via existing list APIs (never blocks the page).
// RULE_9: no in-page breadcrumbs (shell owns the trail).

import React, { useEffect, useState } from 'react';
import {
  Box,
  Card,
  CardActionArea,
  CardContent,
  Grid,
  Typography,
} from '@mui/material';
import PeopleIcon from '@mui/icons-material/People';
import GroupsIcon from '@mui/icons-material/Groups';
import EventAvailableIcon from '@mui/icons-material/EventAvailable';
import PaymentsIcon from '@mui/icons-material/Payments';
import PolicyIcon from '@mui/icons-material/Policy';
import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import {
  fetchEmployees,
  fetchLeaveRecords,
  fetchPayrollRuns,
  fetchLeavePolicies,
  fetchLoans,
} from '../../api/people';

/** Go-live ops modules only — NSR-6A Path H (no Attendance/Rotation). */
export const PEOPLE_HOME_MODULES = [
  {
    id: 'employees',
    path: '/people/employees',
    icon: GroupsIcon,
    titleKey: 'employeesTitle',
    subtitleKey: 'employeesSubtitle',
    countKey: 'employees',
  },
  {
    id: 'leave',
    path: '/people/leave',
    icon: EventAvailableIcon,
    titleKey: 'leaveTitle',
    subtitleKey: 'leaveSubtitle',
    countKey: 'leave',
  },
  {
    id: 'payroll',
    path: '/people/payroll',
    icon: PaymentsIcon,
    titleKey: 'payrollTitle',
    subtitleKey: 'payrollSubtitle',
    countKey: 'payroll',
  },
  {
    id: 'policies',
    path: '/people/policies',
    icon: PolicyIcon,
    titleKey: 'policiesTitle',
    subtitleKey: 'policiesSubtitle',
    countKey: 'policies',
  },
  {
    id: 'loans',
    path: '/people/loans',
    icon: AccountBalanceWalletIcon,
    titleKey: 'loansTitle',
    subtitleKey: 'loansSubtitle',
    countKey: 'loans',
  },
];

function listCount(data) {
  if (data == null) return null;
  if (typeof data.count === 'number') return data.count;
  const list = Array.isArray(data) ? data : data.results;
  return Array.isArray(list) ? list.length : null;
}

function ModuleCard({ module, count, onOpen, t }) {
  const Icon = module.icon;
  return (
    <Card
      variant="outlined"
      sx={{
        height: '100%',
        borderColor: 'divider',
        '&:hover': { borderColor: 'primary.main', bgcolor: 'action.hover' },
      }}
    >
      <CardActionArea
        onClick={() => onOpen(module.path)}
        aria-label={t(module.titleKey)}
        data-testid={`people-home-${module.id}`}
        sx={{ height: '100%', alignItems: 'stretch' }}
      >
        <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.75 }}>
            <Icon sx={{ fontSize: '1.25rem', color: 'primary.main' }} aria-hidden="true" />
            <Typography variant="subtitle2" fontWeight={600} noWrap>
              {t(module.titleKey)}
            </Typography>
            {count != null && (
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ ml: 'auto', fontFamily: 'monospace' }}
              >
                {t('homeCount', { count })}
              </Typography>
            )}
          </Box>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
            {t(module.subtitleKey)}
          </Typography>
        </CardContent>
      </CardActionArea>
    </Card>
  );
}

export default function PeopleHome() {
  const { t } = useTranslation('people');
  const { t: tc } = useTranslation('common');
  const navigate = useNavigate();
  const { token } = useAuth();
  useDocumentTitle(tc('peopleTitle'));

  const [counts, setCounts] = useState({});

  useEffect(() => {
    if (!token) return undefined;
    let cancelled = false;

    (async () => {
      const jobs = [
        ['employees', fetchEmployees],
        ['leave', fetchLeaveRecords],
        ['payroll', fetchPayrollRuns],
        ['policies', fetchLeavePolicies],
        ['loans', fetchLoans],
      ];
      const settled = await Promise.allSettled(
        jobs.map(([, fetchFn]) => fetchFn(token)),
      );
      if (cancelled) return;

      const next = {};
      settled.forEach((result, index) => {
        if (result.status !== 'fulfilled') return;
        const n = listCount(result.value);
        if (n != null) next[jobs[index][0]] = n;
      });
      setCounts(next);
    })();

    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <PageContainer>
      <PageHeader
        icon={PeopleIcon}
        title={tc('peopleTitle')}
        subtitle={tc('peopleSubtitle')}
        description={tc('peopleDescription')}
      />
      <Grid container spacing={1.5} sx={{ mt: 0.5 }}>
        {PEOPLE_HOME_MODULES.map((module) => (
          <Grid key={module.id} size={{ xs: 12, sm: 6, md: 4 }}>
            <ModuleCard
              module={module}
              count={counts[module.countKey]}
              onOpen={navigate}
              t={t}
            />
          </Grid>
        ))}
      </Grid>
    </PageContainer>
  );
}
