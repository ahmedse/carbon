// View page for a People ledger row that may be an employee request.
// The eye on the list navigates here. A linked request continues to the
// Team request page, which is where audit, void, and reopen live.

import React, { useEffect, useState } from 'react';
import { Button, Stack, Typography } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useTheme } from '@mui/material/styles';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import {
  fetchAttendancePermission,
  fetchLeaveRecord,
  fetchLoan,
} from '../../api/people';
import { formatAmount, formatDate, refCode, refLabel, statusLabelKey } from './utils';

const ROUTES = {
  leave: {
    param: 'recordId',
    back: '/people/leave',
    backKey: 'backToPeopleLeave',
    from: 'people-leave',
    load: fetchLeaveRecord,
  },
  loan: {
    param: 'loanId',
    back: '/people/loans',
    backKey: 'backToPeopleLoans',
    from: 'people-loans',
    load: fetchLoan,
  },
  permission: {
    param: 'permissionId',
    back: '/people/attendance',
    backKey: 'backToPeopleAttendance',
    from: 'people-attendance',
    load: fetchAttendancePermission,
  },
};

function employeeLine(record) {
  const name = record.employee_name;
  const no = record.employee_no;
  if (name && no) return `${name} (${no})`;
  return name || no || (record.employee != null ? String(record.employee) : '—');
}

function statusText(t, status) {
  const key = statusLabelKey(status);
  if (key) return t(key);
  if (status === 'active') return t('statusActive');
  if (status === 'paid_off') return t('statusPaidOff');
  return status || '—';
}

function factsFor(kind, record, t) {
  if (kind === 'leave') {
    return [
      { label: t('colEmployee'), value: employeeLine(record) },
      { label: t('colLeaveType'), value: record.leave_type_label || record.leave_type || '—' },
      { label: t('colStartDate'), value: formatDate(record.start_date) },
      { label: t('colEndDate'), value: formatDate(record.end_date) },
      { label: t('colDays'), value: record.days != null ? String(record.days) : '—' },
      { label: t('colStatus'), value: statusText(t, record.status) },
    ];
  }
  if (kind === 'loan') {
    return [
      { label: t('colEmployee'), value: employeeLine(record) },
      { label: t('colLoanType'), value: refLabel(record.loan_type) || refCode(record.loan_type) || '—' },
      { label: t('colPrincipal'), value: formatAmount(record.principal) },
      { label: t('colInterestRate'), value: record.interest_rate != null ? `${record.interest_rate}%` : '—' },
      { label: t('colTermMonths'), value: record.term_months != null ? String(record.term_months) : '—' },
      { label: t('colStartDate'), value: formatDate(record.start_date) },
      { label: t('colStatus'), value: statusText(t, record.status) },
      { label: t('colNotes'), value: record.notes || '—' },
    ];
  }
  return [
    { label: t('colEmployee'), value: employeeLine(record) },
    { label: t('colDate'), value: formatDate(record.date) },
    { label: t('colPermissionType'), value: record.permission_type || '—' },
    { label: t('colHours'), value: record.hours != null ? String(record.hours) : '—' },
    { label: t('colApproved'), value: record.approved ? t('yes') : t('no') },
    { label: t('colNotes'), value: record.notes || '—' },
  ];
}

export default function RequestRecordPage({ kind }) {
  const route = ROUTES[kind];
  const params = useParams();
  const recordId = params[route.param];
  const { t } = useTranslation('people');
  const { t: tTeam } = useTranslation('team');
  const theme = useTheme();
  const isRtl = theme.direction === 'rtl';
  const navigate = useNavigate();
  const { token } = useAuth();
  const [record, setRecord] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);
  useDocumentTitle(t('requestFactsTitle'));

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    route.load(recordId, token)
      .then((data) => {
        if (cancelled) return;
        if (data?.correspondence_id) {
          navigate(`/team/${data.correspondence_id}`, {
            replace: true,
            state: { from: route.from },
          });
          return;
        }
        setRecord(data);
        setLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err?.message || t('actionError'));
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [recordId, token, navigate, route, t, reloadKey]);

  const back = (
    <Button
      size="small"
      variant="outlined"
      startIcon={<ArrowBackIcon sx={isRtl ? { transform: 'scaleX(-1)' } : undefined} />}
      onClick={() => navigate(route.back)}
    >
      {tTeam(route.backKey)}
    </Button>
  );

  return (
    <PageContainer>
      <PageHeader title={record?.reference_no || t('requestFactsTitle')} actions={back} />
      {loading ? (
        <LoadingSkeleton variant="console" />
      ) : error ? (
        <ErrorAlert message={error} onRetry={() => setReloadKey((n) => n + 1)} />
      ) : (
        <Stack spacing={1.25}>
          {factsFor(kind, record, t).map((fact) => (
            <Stack key={fact.label} direction="row" spacing={2} justifyContent="space-between">
              <Typography variant="body2" color="text.secondary">{fact.label}</Typography>
              <Typography variant="body2" sx={{ textAlign: 'end' }}>{fact.value || '—'}</Typography>
            </Stack>
          ))}
          <Typography variant="body2" color="text.secondary" sx={{ pt: 1 }}>
            {t('requestNoWorkflow')}
          </Typography>
        </Stack>
      )}
    </PageContainer>
  );
}
