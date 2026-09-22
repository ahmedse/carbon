// MyLoansCard — employee self-service loan list (QA B6 / NSR-3B).
// Data: GET people/me/loan/ via fetchMyLoans. Theme tokens only; i18n via `my`.

import React from 'react';
import {
  Alert,
  Button,
  Card,
  CardContent,
  Chip,
  Skeleton,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet';
import { useTranslation } from 'react-i18next';
import ResponsiveList from '../../../components/layout/ResponsiveList';
import { FONT } from '../../../theme/themeTokens';

/** Nested governed value or plain string → display text. */
function loanTypeLabel(value) {
  if (value == null || value === '') return '—';
  if (typeof value === 'object') return value.label || value.code || '—';
  return String(value);
}

function SectionTitle({ icon: Icon, title }) {
  return (
    <Stack direction="row" alignItems="center" spacing={0.5} sx={{ mb: 1 }}>
      {Icon && <Icon sx={{ fontSize: '1rem', color: 'primary.main' }} />}
      <Typography
        sx={{
          ...FONT.cardTitle,
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
          color: 'text.secondary',
        }}
      >
        {title}
      </Typography>
    </Stack>
  );
}

function InlineError({ message, onRetry }) {
  const { t } = useTranslation('my');
  return (
    <Alert
      severity="error"
      action={
        onRetry ? (
          <Button color="inherit" size="small" onClick={onRetry}>
            {t('retry')}
          </Button>
        ) : null
      }
    >
      {message}
    </Alert>
  );
}

function loanStatusColor(status) {
  switch (status) {
    case 'active':
    case 'approved':
      return 'success';
    case 'paid_off':
      return 'info';
    case 'cancelled':
    case 'rejected':
      return 'warning';
    case 'submitted':
    case 'in_review':
    case 'sent_back':
      return 'info';
    case 'draft':
      return 'default';
    default:
      return 'default';
  }
}

function loanStatusLabel(status, t) {
  switch (status) {
    case 'active':
      return t('loanStatusActive');
    case 'paid_off':
      return t('loanStatusPaidOff');
    case 'cancelled':
      return t('loanStatusCancelled');
    case 'rejected':
      return t('statusRejected', { defaultValue: 'Rejected' });
    case 'submitted':
      return t('statusSubmitted', { defaultValue: 'Submitted' });
    case 'in_review':
      return t('statusInReview', { defaultValue: 'In review' });
    case 'sent_back':
      return t('statusSentBack', { defaultValue: 'Sent back' });
    case 'approved':
      return t('statusApproved', { defaultValue: 'Approved' });
    case 'draft':
      return t('loanStatusDraft');
    default:
      return status ?? '—';
  }
}

/** Prefer serializer remapped status (corr for in-flight drafts). */
function loanDisplayStatus(loan) {
  return loan?.status || loan?.correspondence_status || 'draft';
}

function formatAmount(amount) {
  const value = Number(amount);
  if (Number.isNaN(value)) return '—';
  return value.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 3,
  });
}

/**
 * @param {{ loans: Array, loading: boolean, error: string|null, onRetry?: Function }} props
 */
export default function MyLoansCard({ loans, loading, error, onRetry }) {
  const { t } = useTranslation('my');

  if (loading) {
    return (
      <Card variant="outlined" data-testid="my-loans-card">
        <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
          <SectionTitle icon={AccountBalanceWalletIcon} title={t('loansTitle')} />
          <Stack spacing={0.5} aria-label={t('loading')}>
            <Skeleton />
            <Skeleton width="70%" />
            <Skeleton width="85%" />
          </Stack>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card variant="outlined" data-testid="my-loans-card">
        <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
          <SectionTitle icon={AccountBalanceWalletIcon} title={t('loansTitle')} />
          <InlineError message={error} onRetry={onRetry} />
        </CardContent>
      </Card>
    );
  }

  if (!loans || loans.length === 0) {
    return (
      <Card variant="outlined" data-testid="my-loans-card">
        <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
          <SectionTitle icon={AccountBalanceWalletIcon} title={t('loansTitle')} />
          <Typography sx={{ ...FONT.body2, color: 'text.secondary' }}>
            {t('loansEmpty')}
          </Typography>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card variant="outlined" data-testid="my-loans-card">
      <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
        <SectionTitle icon={AccountBalanceWalletIcon} title={t('loansTitle')} />
        <ResponsiveList
          items={loans}
          getKey={(loan) => loan.id}
          emptyLabel={t('loansEmpty')}
          renderCard={(loan) => {
            const st = loanDisplayStatus(loan);
            return {
              title: loanTypeLabel(loan.loan_type),
              status: loanStatusLabel(st, t),
              statusColor: loanStatusColor(st),
              meta: formatAmount(loan.principal),
            };
          }}
          table={
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ ...FONT.body, fontWeight: 600 }}>
                      {t('loansType')}
                    </TableCell>
                    <TableCell align="right" sx={{ ...FONT.body, fontWeight: 600 }}>
                      {t('loansPrincipal')}
                    </TableCell>
                    <TableCell align="right" sx={{ ...FONT.body, fontWeight: 600 }}>
                      {t('loansTerm')}
                    </TableCell>
                    <TableCell sx={{ ...FONT.body, fontWeight: 600 }}>
                      {t('loansStartDate')}
                    </TableCell>
                    <TableCell sx={{ ...FONT.body, fontWeight: 600 }}>
                      {t('loansStatus')}
                    </TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {loans.map((loan) => (
                    <TableRow key={loan.id} hover>
                      <TableCell sx={{ ...FONT.body2 }}>
                        {loanTypeLabel(loan.loan_type)}
                      </TableCell>
                      <TableCell
                        align="right"
                        sx={{ ...FONT.body2, fontVariantNumeric: 'tabular-nums' }}
                        dir="ltr"
                      >
                        {formatAmount(loan.principal)}
                      </TableCell>
                      <TableCell align="right" sx={{ ...FONT.body2 }} dir="ltr">
                        {loan.term_months ?? '—'}
                      </TableCell>
                      <TableCell sx={{ ...FONT.body2 }} dir="ltr">
                        {loan.start_date ? String(loan.start_date).slice(0, 10) : '—'}
                      </TableCell>
                      <TableCell>
                        <Chip
                          size="small"
                          variant="outlined"
                          color={loanStatusColor(loanDisplayStatus(loan))}
                          label={loanStatusLabel(loanDisplayStatus(loan), t)}
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          }
        />
      </CardContent>
    </Card>
  );
}
