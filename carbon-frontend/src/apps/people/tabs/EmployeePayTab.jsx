// src/apps/people/tabs/EmployeePayTab.jsx
// Compensation ledger (primary) + payroll runs / payslip lines (secondary).
// Ledger: current active lines grouped Earnings/Deductions with totals, history
// accordion, and manage-gated "Add Component" SystemDialog.

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Accordion, AccordionDetails, AccordionSummary,
  Alert, Box, Button, Chip, CircularProgress, Divider, LinearProgress,
  MenuItem, Paper, Select, Skeleton, Stack,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  TextField, Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ReceiptLongIcon from '@mui/icons-material/ReceiptLong';
import VerifiedIcon from '@mui/icons-material/Verified';
import { useTranslation } from 'react-i18next';
import EmptyState from '../../../components/Page/EmptyState';
import SystemDialog from '../../../components/SystemDialog';
import { useNotification } from '../../../components/NotificationProvider';
import {
  createCompensationLine,
  fetchCompensationComponents,
  fetchCompensationLedger,
  fetchPayrollRuns,
  fetchPayslipLines,
} from '../../../api/people';
import { useAuth } from '../../../auth/AuthContext';
import { PEOPLE_MANAGE } from '../../../capabilities';
import { formatAmount, formatDate, statusColor, statusLabelKey } from '../utils';

// ─── payslip-line helpers (payroll runs section) ─────────────────────────────

// Payslip `line_type` values are canonical free-text codes. Direction is
// derived from the known deduction codes; everything else (except the explicit
// gross/net lines) is an earning. The compensation *ledger* uses the API's
// `component_direction` field instead — never a client-side classifier.
const PAYSLIP_DEDUCTION_TYPES = ['gosi', 'deduction', 'loan', 'tax', 'wps'];

function payslipLineDirection(lineType) {
  const lt = String(lineType || '').toLowerCase();
  if (lt === 'gross' || lt === 'net') return lt;
  return PAYSLIP_DEDUCTION_TYPES.includes(lt) ? 'deduction' : 'earning';
}

function PaylineRow({ line, secondary }) {
  return (
    <TableRow hover>
      <TableCell sx={{ textTransform: 'capitalize', color: secondary ? 'text.secondary' : 'text.primary', py: 0.5 }}>
        {(line.line_type || '').replace(/_/g, ' ')}
      </TableCell>
      <TableCell align="right" sx={{ fontVariantNumeric: 'tabular-nums', py: 0.5 }} dir="ltr">
        {secondary ? `(${formatAmount(line.amount)})` : formatAmount(line.amount)}
      </TableCell>
      {line.rule_id && (
        <TableCell sx={{ color: 'text.disabled', py: 0.5 }}>
          <Typography component="span" variant="caption">
            {line.rule_id} v{line.rule_version}
          </Typography>
        </TableCell>
      )}
    </TableRow>
  );
}

// ─── small badge components (theme chip variants — no inline height/fontSize) ─

function VerifiedBadge({ isVerified }) {
  const { t } = useTranslation('people');
  if (isVerified) {
    return <Chip size="small" color="success" icon={<VerifiedIcon />} label={t('compVerified')} />;
  }
  return <Chip size="small" label={t('compPending')} />;
}

function DirectionChip({ direction }) {
  const { t } = useTranslation('people');
  const earning = direction === 'earning';
  return (
    <Chip
      size="small"
      color={earning ? 'success' : 'error'}
      label={earning ? t('compEarning') : t('compDeduction')}
    />
  );
}

function HistoryStatusChip({ line }) {
  const { t } = useTranslation('people');
  if (line.is_verified) {
    return <Chip size="small" color="success" icon={<VerifiedIcon />} label={t('compVerified')} />;
  }
  if (!line.effective_end) {
    return <Chip size="small" color="info" label={t('compOpen')} />;
  }
  return <Chip size="small" label={t('compClosed')} />;
}

// ─── LedgerSection ────────────────────────────────────────────────────────────

function LedgerSection({ title, lines, total, totalLabel }) {
  return (
    <Paper variant="outlined" sx={{ p: 1.5 }}>
      <Typography
        variant="caption"
        sx={{ fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'text.secondary', display: 'block', mb: 1 }}
      >
        {title}
      </Typography>
      <TableContainer>
        <Table size="small" sx={{ '& td, & th': { border: 0 } }}>
          <TableBody>
            {lines.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} sx={{ color: 'text.disabled' }}>—</TableCell>
              </TableRow>
            ) : lines.map((line) => (
              <TableRow key={line.id} hover>
                <TableCell sx={{ color: 'text.primary' }}>
                  {line.component_name}
                  {line.component_code && (
                    <Typography component="span" variant="caption" sx={{ color: 'text.disabled', ml: 0.5 }} dir="ltr">
                      ({line.component_code})
                    </Typography>
                  )}
                </TableCell>
                <TableCell align="right" sx={{ fontVariantNumeric: 'tabular-nums' }} dir="ltr">
                  {formatAmount(line.amount)}&nbsp;{line.currency}
                </TableCell>
                <TableCell sx={{ color: 'text.secondary' }}>{line.frequency}</TableCell>
                <TableCell sx={{ color: 'text.secondary' }} dir="ltr">
                  {formatDate(line.effective_start)}
                  {line.effective_end ? ` → ${formatDate(line.effective_end)}` : ''}
                </TableCell>
                <TableCell><VerifiedBadge isVerified={line.is_verified} /></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      {lines.length > 0 && (
        <>
          <Divider sx={{ my: 0.75 }} />
          <Box sx={{ display: 'flex', justifyContent: 'space-between', px: 0.5 }}>
            <Typography variant="body1" sx={{ fontWeight: 700 }}>{totalLabel}</Typography>
            <Typography variant="h5" sx={{ fontWeight: 700, fontVariantNumeric: 'tabular-nums' }} dir="ltr">
              {formatAmount(total)}
            </Typography>
          </Box>
        </>
      )}
    </Paper>
  );
}

// ─── HistoryAccordion ─────────────────────────────────────────────────────────

const HISTORY_COLUMNS = ['colComponent', 'colDirection', 'colAmount', 'colPeriod', 'colStatus'];

function HistoryAccordion({ history }) {
  const { t } = useTranslation('people');
  return (
    <Accordion disableGutters elevation={0} variant="outlined" sx={{ mt: 1.5 }}>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        <Typography variant="body1" sx={{ fontWeight: 600 }}>
          {t('compHistory')} ({history.length})
        </Typography>
      </AccordionSummary>
      <AccordionDetails sx={{ p: 0 }}>
        {history.length === 0 ? (
          <Box sx={{ p: 1.5, textAlign: 'center' }}>
            <Typography variant="body2" sx={{ color: 'text.secondary' }}>{t('compNoHistory')}</Typography>
          </Box>
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  {HISTORY_COLUMNS.map((key) => (
                    <TableCell key={key}>{t(key)}</TableCell>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {history.map((line) => (
                  <TableRow key={line.id} hover>
                    <TableCell>{line.component_name}</TableCell>
                    <TableCell><DirectionChip direction={line.component_direction} /></TableCell>
                    <TableCell align="right" sx={{ fontVariantNumeric: 'tabular-nums' }} dir="ltr">{formatAmount(line.amount)}&nbsp;{line.currency}</TableCell>
                    <TableCell dir="ltr">
                      {formatDate(line.effective_start)}
                      {line.effective_end ? ` → ${formatDate(line.effective_end)}` : ' →'}
                    </TableCell>
                    <TableCell><HistoryStatusChip line={line} /></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </AccordionDetails>
    </Accordion>
  );
}

// ─── AddCompLineDialog (SystemDialog) ────────────────────────────────────────

const EMPTY_COMP_FORM = {
  component: '',
  amount: '',
  currency: 'KWD',
  frequency: 'monthly',
  effective_start: '',
  reason_note: '',
};

const CURRENCIES = ['KWD', 'USD', 'EUR', 'SAR', 'AED', 'EGP'];

function AddCompLineDialog({ open, onClose, empId, token, onSuccess }) {
  const { t } = useTranslation('people');
  const { notify } = useNotification();
  const [components, setComponents] = useState([]);
  const [componentsLoading, setComponentsLoading] = useState(false);
  const [form, setForm] = useState(EMPTY_COMP_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState(null);

  // Lazy-load the component catalog only when the dialog opens.
  useEffect(() => {
    if (!open) return;
    let active = true;
    setComponentsLoading(true);
    fetchCompensationComponents(token)
      .then((data) => {
        if (!active) return;
        const list = Array.isArray(data?.results) ? data.results : (Array.isArray(data) ? data : []);
        setComponents(list);
      })
      .catch(() => { if (active) setComponents([]); })
      .finally(() => { if (active) setComponentsLoading(false); });
    return () => { active = false; };
  }, [open, token]);

  const handleChange = useCallback(
    (field) => (e) => {
      setForm((prev) => ({ ...prev, [field]: e.target.value }));
      setFormError(null);
    },
    [],
  );

  const handleCloseRequest = useCallback(() => {
    if (submitting) return;
    onClose();
  }, [submitting, onClose]);

  const handleSubmit = async () => {
    if (!form.component || !form.amount || !form.effective_start) {
      setFormError(t('compRequiredFields'));
      return;
    }
    setSubmitting(true);
    setFormError(null);
    try {
      await createCompensationLine(empId, {
        component: Number(form.component),
        amount: form.amount,
        currency: form.currency,
        frequency: form.frequency,
        effective_start: form.effective_start,
        reason_note: form.reason_note,
      }, token);
      notify({ message: t('compAdded'), type: 'success' });
      setForm({ ...EMPTY_COMP_FORM });
      onSuccess();
      onClose();
    } catch (err) {
      setFormError(err?.message || t('compAddFailed'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <SystemDialog
      open={open}
      title={t('compAddTitle')}
      onClose={handleCloseRequest}
      onCancel={handleCloseRequest}
      cancelLabel={t('compCancel')}
      actions={
        <Button
          variant="contained"
          onClick={handleSubmit}
          disabled={submitting}
          startIcon={submitting ? <CircularProgress size={12} color="inherit" /> : null}
        >
          {t('compAdd')}
        </Button>
      }
    >
      <Stack spacing={1.5}>
        <TextField
          select
          label={t('colComponent')}
          value={form.component}
          onChange={handleChange('component')}
          fullWidth
          required
          disabled={componentsLoading || submitting}
        >
          <MenuItem value="" disabled>{t('colComponent')}</MenuItem>
          {components.map((c) => (
            <MenuItem key={c.id} value={c.id}>
              {c.name}&nbsp;({c.code})
            </MenuItem>
          ))}
        </TextField>
        <TextField
          label={t('colAmount')}
          type="number"
          value={form.amount}
          onChange={handleChange('amount')}
          fullWidth
          required
          slotProps={{ htmlInput: { min: 0, step: '0.001' } }}
        />
        <TextField
          select
          label={t('compCurrency')}
          value={form.currency}
          onChange={handleChange('currency')}
          fullWidth
          disabled={submitting}
        >
          {CURRENCIES.map((c) => <MenuItem key={c} value={c}>{c}</MenuItem>)}
        </TextField>
        <TextField
          select
          label={t('compFrequency')}
          value={form.frequency}
          onChange={handleChange('frequency')}
          fullWidth
          disabled={submitting}
        >
          <MenuItem value="monthly">{t('compMonthly')}</MenuItem>
          <MenuItem value="annual">{t('compAnnual')}</MenuItem>
        </TextField>
        <TextField
          label={t('colEffectiveStart')}
          type="date"
          value={form.effective_start}
          onChange={handleChange('effective_start')}
          fullWidth
          required
          slotProps={{ inputLabel: { shrink: true } }}
        />
        <TextField
          label={t('compReasonNote')}
          multiline
          rows={2}
          value={form.reason_note}
          onChange={handleChange('reason_note')}
          fullWidth
        />
        {formError && (
          <Alert severity="error" role="alert">{formError}</Alert>
        )}
      </Stack>
    </SystemDialog>
  );
}

// ─── LedgerSkeleton ───────────────────────────────────────────────────────────

function LedgerSkeleton() {
  return (
    <Box>
      <Skeleton variant="text" width="40%" sx={{ mb: 1 }} />
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 1.5, mb: 1.5 }}>
        {[0, 1].map((i) => (
          <Paper key={i} variant="outlined" sx={{ p: 1.5 }}>
            <Skeleton variant="text" />
            <Skeleton variant="text" />
            <Skeleton variant="text" />
          </Paper>
        ))}
      </Box>
      <Paper variant="outlined" sx={{ p: 1.5 }}>
        <Skeleton variant="rectangular" height={40} />
      </Paper>
    </Box>
  );
}

// ─── CompensationLedger ───────────────────────────────────────────────────────

function CompensationLedger({ empId, token, canManage }) {
  const { t } = useTranslation('people');
  const [ledger, setLedger] = useState(null);
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState(null);
  const [partial, setPartial] = useState(false);
  const [stale, setStale] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const hasLoadedRef = useRef(false);

  const loadLedger = useCallback(async () => {
    if (!empId || !token) return;
    if (hasLoadedRef.current) {
      setStale(true);
    } else {
      setStatus('loading');
    }
    setError(null);
    setPartial(false);
    try {
      const data = await fetchCompensationLedger(empId, token);
      setLedger(data);
      const currentOk = Array.isArray(data?.current);
      const historyOk = Array.isArray(data?.history);
      const totalsOk = data?.totals && typeof data.totals === 'object';
      setPartial(!(currentOk && historyOk && totalsOk));
      hasLoadedRef.current = true;
      setStatus('loaded');
    } catch (err) {
      if (err?.status === 403) {
        setStatus('forbidden');
      } else {
        setError(err?.message || t('compLoadError'));
        setStatus('error');
      }
    } finally {
      setStale(false);
    }
  }, [empId, token, t]);

  useEffect(() => {
    loadLedger();
  }, [loadLedger, refreshKey]);

  const handleAdded = useCallback(() => setRefreshKey((k) => k + 1), []);
  const openDialog = useCallback(() => setDialogOpen(true), []);
  const closeDialog = useCallback(() => setDialogOpen(false), []);

  const current = Array.isArray(ledger?.current) ? ledger.current : [];
  const history = Array.isArray(ledger?.history) ? ledger.history : [];
  const totals = ledger?.totals || {};
  const earnings = useMemo(() => current.filter((l) => l.component_direction === 'earning'), [current]);
  const deductions = useMemo(() => current.filter((l) => l.component_direction === 'deduction'), [current]);

  if (status === 'idle' || status === 'loading') {
    return <LedgerSkeleton />;
  }

  if (status === 'forbidden') {
    return (
      <Paper variant="outlined" sx={{ p: 3, textAlign: 'center' }}>
        <ReceiptLongIcon fontSize="large" sx={{ color: 'text.disabled', mb: 1 }} />
        <Typography variant="h6" sx={{ color: 'text.secondary' }}>
          {t('compProtected')}
        </Typography>
      </Paper>
    );
  }

  if (status === 'error') {
    return (
      <Alert
        severity="error"
        action={
          <Button color="inherit" size="small" onClick={loadLedger}>
            {t('compRetry')}
          </Button>
        }
      >
        {error}
      </Alert>
    );
  }

  const isEmpty = current.length === 0 && history.length === 0;

  return (
    <Box>
      {stale && <LinearProgress sx={{ mb: 1 }} />}
      {partial && (
        <Alert severity="warning" sx={{ mb: 1.5 }}>{t('compPartialWarning')}</Alert>
      )}

      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
        <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1 }}>
          <Typography variant="h5" sx={{ fontWeight: 700 }}>{t('compLedger')}</Typography>
          {ledger?.as_of && (
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
              {t('compAsOf')} {formatDate(ledger.as_of)}
            </Typography>
          )}
        </Box>
        {canManage && !isEmpty && (
          <Button
            size="small"
            variant="outlined"
            startIcon={<AddIcon />}
            onClick={openDialog}
          >
            {t('compAddComponent')}
          </Button>
        )}
      </Box>

      {isEmpty ? (
        <EmptyState
          icon={<ReceiptLongIcon />}
          title={t('compEmpty')}
          description={t('compEmptyDesc')}
          actionLabel={canManage ? t('compAddFirstComponent') : undefined}
          onAction={canManage ? openDialog : undefined}
        />
      ) : (
        <>
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 1.5, mb: 1.5 }}>
            <LedgerSection
              title={t('payTabEarnings')}
              lines={earnings}
              total={totals.monthly_earnings}
              totalLabel={t('compGrossMonthly')}
            />
            <LedgerSection
              title={t('payTabDeductions')}
              lines={deductions}
              total={totals.monthly_deductions}
              totalLabel={t('compTotalDeductions')}
            />
          </Box>

          {/* Net Monthly totals bar */}
          <Paper variant="outlined" sx={{ p: 1.5, mb: 0.5 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Box sx={{ display: 'flex', gap: 3 }}>
                <Box>
                  <Typography variant="caption" sx={{ textTransform: 'uppercase', letterSpacing: '0.05em', display: 'block' }}>
                    {t('compGrossMonthly')}
                  </Typography>
                  <Typography variant="h6" sx={{ fontVariantNumeric: 'tabular-nums' }} dir="ltr">
                    {formatAmount(totals.monthly_earnings)}
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="caption" sx={{ textTransform: 'uppercase', letterSpacing: '0.05em', display: 'block' }}>
                    {t('payTabDeductions')}
                  </Typography>
                  <Typography variant="h6" sx={{ color: 'error.main', fontVariantNumeric: 'tabular-nums' }} dir="ltr">
                    ({formatAmount(totals.monthly_deductions)})
                  </Typography>
                </Box>
              </Box>
              <Box sx={{ textAlign: 'right' }}>
                <Typography variant="caption" sx={{ textTransform: 'uppercase', letterSpacing: '0.05em', display: 'block' }}>
                  {t('compNetMonthly')}
                </Typography>
                <Typography variant="h2" sx={{ color: 'primary.main', fontVariantNumeric: 'tabular-nums' }} dir="ltr">
                  {formatAmount(totals.net_monthly)}
                </Typography>
              </Box>
            </Box>
          </Paper>
        </>
      )}

      <HistoryAccordion history={history} />

      <AddCompLineDialog
        open={dialogOpen}
        onClose={closeDialog}
        empId={empId}
        token={token}
        onSuccess={handleAdded}
      />
    </Box>
  );
}

// ─── PayrollRunsSection (existing payroll runs + payslip lines) ───────────────

function PayrollRunsSection({ empId, token }) {
  const { t } = useTranslation('people');
  const [runs, setRuns] = useState(null);
  const [allLines, setAllLines] = useState([]);
  const [selectedRunId, setSelectedRunId] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const loadedRef = useRef(false);

  // Lazy load on first mount
  useEffect(() => {
    if (loadedRef.current || !empId || !token) return;
    loadedRef.current = true;
    setLoading(true);
    setError(null);
    Promise.all([fetchPayrollRuns(token), fetchPayslipLines({}, token)])
      .then(([runsData, linesData]) => {
        const allRuns = Array.isArray(runsData?.results) ? runsData.results : (Array.isArray(runsData) ? runsData : []);
        const empLines = (Array.isArray(linesData?.results) ? linesData.results : (Array.isArray(linesData) ? linesData : []))
          .filter(l => l.employee === empId);
        setAllLines(empLines);
        setRuns(allRuns);
        const myRunIds = new Set(empLines.map(l => l.payroll_run));
        const latest = allRuns.find(r => myRunIds.has(r.id));
        if (latest) setSelectedRunId(String(latest.id));
      })
      .catch((err) => setError(err?.message || t('payslipLoadError')))
      .finally(() => setLoading(false));
  }, [empId, token, t]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', py: 4 }}>
        <CircularProgress size={24} />
      </Box>
    );
  }

  if (error) {
    return <Alert severity="error">{error}</Alert>;
  }

  if (!runs) return null;

  const myRunIds = new Set(allLines.map((l) => l.payroll_run));
  const myRuns = runs.filter((r) => myRunIds.has(r.id)).slice(0, 6);

  if (myRuns.length === 0) {
    return (
      <Box sx={{ py: 1 }}>
        <EmptyState title={t('payTabNoData')} description={t('payslipEmptyDesc')} />
      </Box>
    );
  }

  const currentLines = allLines.filter((l) => l.payroll_run === Number(selectedRunId));
  const selectedRun = runs.find((r) => r.id === Number(selectedRunId));

  const earnings = currentLines.filter(
    (l) => payslipLineDirection(l.line_type) === 'earning',
  );
  const deductions = currentLines.filter(
    (l) => payslipLineDirection(l.line_type) === 'deduction',
  );
  const grossLine = currentLines.find((l) => l.line_type === 'gross');
  const netLine = currentLines.find((l) => l.line_type === 'net');

  const grossTotal = grossLine
    ? Number(grossLine.amount)
    : earnings.reduce((s, l) => s + Number(l.amount), 0);
  const netTotal = netLine
    ? Number(netLine.amount)
    : grossTotal - deductions.reduce((s, l) => s + Number(l.amount), 0);

  return (
    <Box sx={{ p: 2 }}>
      {/* Run selector */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
        <Typography variant="h5">{t('payTabLatestSlip')}</Typography>
        <Select
          size="small"
          value={selectedRunId}
          onChange={(e) => setSelectedRunId(e.target.value)}
          sx={{ minWidth: (theme) => theme.spacing(25) }}
        >
          {myRuns.map((r) => (
            <MenuItem key={r.id} value={String(r.id)}>
              {formatDate(r.period_start)} → {formatDate(r.period_end)}
            </MenuItem>
          ))}
        </Select>
      </Box>

      {selectedRun && (
        <Box sx={{ display: 'flex', gap: 1, mb: 1.5, flexWrap: 'wrap', alignItems: 'center' }}>
          <Chip
            size="small"
            variant="outlined"
            color={statusColor(selectedRun.status)}
            label={statusLabelKey(selectedRun.status) ? t(statusLabelKey(selectedRun.status)) : selectedRun.status}
          />
          {selectedRun.committed_at && (
            <Typography variant="body2">
              {t('statusCommitted')} {formatDate(selectedRun.committed_at)}
            </Typography>
          )}
        </Box>
      )}

      {currentLines.length === 0 ? (
        <Box sx={{ py: 2, textAlign: 'center' }}>
          <Typography variant="body1" sx={{ color: 'text.secondary' }}>{t('payslipEmpty')}</Typography>
        </Box>
      ) : (
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 1.5, mb: 2 }}>
          {/* Earnings */}
          <Paper variant="outlined" sx={{ p: 1.5 }}>
            <Typography variant="caption" sx={{ fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', display: 'block', mb: 1 }}>
              {t('payTabEarnings')}
            </Typography>
            <TableContainer>
              <Table size="small" sx={{ '& td': { border: 0 } }}>
                <TableBody>
                  {earnings.map((l) => <PaylineRow key={l.id} line={l} />)}
                  {!earnings.length && (
                    <TableRow><TableCell sx={{ color: 'text.disabled' }}>—</TableCell></TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
            <Divider sx={{ my: 0.75 }} />
            <Box sx={{ display: 'flex', justifyContent: 'space-between', px: 0.5 }}>
              <Typography variant="body1" sx={{ fontWeight: 700 }}>{t('grossTotal')}</Typography>
              <Typography variant="h5" sx={{ fontWeight: 700, fontVariantNumeric: 'tabular-nums' }} dir="ltr">
                {formatAmount(grossTotal)}
              </Typography>
            </Box>
          </Paper>

          {/* Deductions + Net */}
          <Paper variant="outlined" sx={{ p: 1.5 }}>
            <Typography variant="caption" sx={{ fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', display: 'block', mb: 1 }}>
              {t('payTabDeductions')}
            </Typography>
            <TableContainer>
              <Table size="small" sx={{ '& td': { border: 0 } }}>
                <TableBody>
                  {deductions.map((l) => <PaylineRow key={l.id} line={l} secondary />)}
                  {!deductions.length && (
                    <TableRow><TableCell sx={{ color: 'text.disabled' }}>—</TableCell></TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
            <Divider sx={{ my: 0.75 }} />
            <Box sx={{ display: 'flex', justifyContent: 'space-between', px: 0.5 }}>
              <Typography variant="body1" sx={{ fontWeight: 700 }}>{t('netTotal')}</Typography>
              <Typography variant="h5" sx={{ fontWeight: 700, color: 'primary.main', fontVariantNumeric: 'tabular-nums' }} dir="ltr">
                {formatAmount(netTotal)}
              </Typography>
            </Box>
          </Paper>
        </Box>
      )}

      {/* Payroll history mini-table */}
      {myRuns.length > 1 && (
        <>
          <Typography variant="h5" sx={{ mb: 0.75 }}>{t('payTabHistory')}</Typography>
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  {[t('colPeriodStart'), t('colPeriodEnd'), t('colStatus')].map((h) => (
                    <TableCell key={h}>{h}</TableCell>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {myRuns.map((r) => (
                  <TableRow
                    key={r.id}
                    hover
                    selected={String(r.id) === selectedRunId}
                    onClick={() => setSelectedRunId(String(r.id))}
                    sx={{ cursor: 'pointer' }}
                  >
                    <TableCell sx={{ fontVariantNumeric: 'tabular-nums', py: 0.5 }} dir="ltr">{formatDate(r.period_start)}</TableCell>
                    <TableCell sx={{ fontVariantNumeric: 'tabular-nums', py: 0.5 }} dir="ltr">{formatDate(r.period_end)}</TableCell>
                    <TableCell sx={{ py: 0.5 }}>
                      <Chip
                        size="small"
                        label={statusLabelKey(r.status) ? t(statusLabelKey(r.status)) : r.status}
                        color={statusColor(r.status)}
                        variant="outlined"
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </>
      )}
    </Box>
  );
}

// ─── EmployeePayTab (root export) ────────────────────────────────────────────

export default function EmployeePayTab({ entityData, additionalProps }) {
  const token = additionalProps?.token;
  const emp = entityData || {};
  const empId = emp.empId ?? emp.id;
  const { isGlobalAdminFlag, userCapabilities } = useAuth();
  const caps = Array.isArray(userCapabilities) ? userCapabilities : [];
  const canManage = isGlobalAdminFlag === true || caps.includes(PEOPLE_MANAGE);

  return (
    <Box sx={{ p: 2 }}>
      <CompensationLedger empId={empId} token={token} canManage={canManage} />
      <Divider sx={{ my: 2 }} />
      <PayrollRunsSection empId={empId} token={token} />
    </Box>
  );
}
