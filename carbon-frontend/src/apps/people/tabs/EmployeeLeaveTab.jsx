// src/apps/people/tabs/EmployeeLeaveTab.jsx
// Per-employee leave balance (visual progress bars per leave type) + recent records.
// Year selector defaults to current year; balance is computed client-side from
// entityData.leaveEntitlements (loaded in EmployeeDetailPage on mount).

import React, { useState } from 'react';
import {
  Box, Chip, MenuItem, Paper, Select, Stack,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Typography,
} from '@mui/material';
import EventAvailableIcon from '@mui/icons-material/EventAvailable';
import { useTranslation } from 'react-i18next';
import EmptyState from '../../../components/Page/EmptyState';
import { formatDate, leaveBalanceByType, statusColor, statusLabelKey } from '../utils';

// ── Leave balance bar ──────────────────────────────────────────

function LeaveBar({ type, entitled, used, balance }) {
  const pct = entitled > 0 ? Math.min(100, (used / entitled) * 100) : 0;
  const isOver = used > entitled;
  const isLow = !isOver && balance < 3;
  const barColor = isOver ? 'error.main' : isLow ? 'warning.main' : 'primary.main';

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.25 }}>
        <Typography sx={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'capitalize' }}>
          {type.replace(/_/g, ' ')}
        </Typography>
        <Typography sx={{ fontSize: '0.6875rem', color: 'text.secondary' }}>
          {used}d used / {entitled}d entitled
        </Typography>
      </Box>
      <Box sx={{ height: 5, bgcolor: 'action.hover', borderRadius: 1, overflow: 'hidden' }}>
        <Box sx={{ height: '100%', width: `${pct}%`, bgcolor: barColor, borderRadius: 1, transition: 'width 0.45s ease' }} />
      </Box>
      <Typography sx={{ fontSize: '0.5625rem', color: isOver ? 'error.main' : isLow ? 'warning.main' : 'text.disabled', textAlign: 'right', mt: 0.125 }}>
        {balance > 0 ? `${balance.toFixed(1)}d remaining` : balance === 0 ? 'None remaining' : `${Math.abs(balance).toFixed(1)}d over`}
      </Typography>
    </Box>
  );
}

// ── Main component ─────────────────────────────────────────────

export default function EmployeeLeaveTab({ entityData }) {
  const { t } = useTranslation('people');
  const emp = entityData || {};
  const empId = emp.empId ?? emp.id;
  const currentYear = new Date().getFullYear();

  const [year, setYear] = useState(currentYear);

  // Filter entitlements + records for this employee
  const myEnts = (emp.leaveEntitlements || []).filter(e => e.employee === empId && e.year === year);
  const myRecords = (emp.leaveRecords || [])
    .filter(r => r.employee === empId)
    .filter(r => {
      const yr = new Date(r.start_date || r.end_date || '').getFullYear();
      return yr === year || yr === year - 1;
    })
    .slice(0, 15);

  const byType = leaveBalanceByType(myEnts);
  const yearOptions = [currentYear, currentYear - 1, currentYear - 2];

  return (
    <Box sx={{ p: 2 }}>

      {/* Header + year selector */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
        <Typography sx={{ fontSize: '0.875rem', fontWeight: 600 }}>{t('leaveTabBalance')}</Typography>
        <Select
          size="small"
          value={year}
          onChange={e => setYear(Number(e.target.value))}
          sx={{ fontSize: '0.75rem', minWidth: 90, height: 28 }}
        >
          {yearOptions.map(y => (
            <MenuItem key={y} value={y} sx={{ fontSize: '0.75rem' }}>{y}</MenuItem>
          ))}
        </Select>
      </Box>

      {/* Balance bars */}
      {byType.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, mb: 2 }}>
          <Typography sx={{ fontSize: '0.75rem', color: 'text.secondary', textAlign: 'center' }}>
            {t('leaveTabNoEnts', { year })}
          </Typography>
        </Paper>
      ) : (
        <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2, mb: 2 }}>
          <Stack spacing={1.5}>
            {byType.map(item => (
              <LeaveBar
                key={item.type}
                type={item.type}
                entitled={item.entitled}
                used={item.used}
                balance={item.balance}
              />
            ))}
          </Stack>
        </Paper>
      )}

      {/* Recent leave records */}
      <Typography sx={{ fontSize: '0.875rem', fontWeight: 600, mb: 0.75 }}>{t('leaveTabRecords')}</Typography>
      {myRecords.length === 0 ? (
        <EmptyState title={t('leaveEmpty')} description={t('leaveEmptyDesc')} />
      ) : (
        <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 2 }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                {['colLeaveType', 'colStartDate', 'colEndDate', 'colDays', 'colStatus'].map(k => (
                  <TableCell key={k} sx={{ fontWeight: 700, fontSize: '0.625rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'text.secondary', py: 0.75 }}>
                    {t(k)}
                  </TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {myRecords.map(r => (
                <TableRow key={r.id} hover>
                  <TableCell sx={{ fontSize: '0.75rem', textTransform: 'capitalize', py: 0.625 }}>
                    {r.leave_type?.replace(/_/g, ' ') ?? '—'}
                  </TableCell>
                  <TableCell sx={{ fontSize: '0.75rem', fontVariantNumeric: 'tabular-nums', py: 0.625 }}>{formatDate(r.start_date)}</TableCell>
                  <TableCell sx={{ fontSize: '0.75rem', fontVariantNumeric: 'tabular-nums', py: 0.625 }}>{formatDate(r.end_date)}</TableCell>
                  <TableCell sx={{ fontSize: '0.75rem', fontVariantNumeric: 'tabular-nums', py: 0.625 }}>{r.days ?? '—'}</TableCell>
                  <TableCell sx={{ py: 0.625 }}>
                    <Chip
                      size="small"
                      label={statusLabelKey(r.status) ? t(statusLabelKey(r.status)) : r.status}
                      color={statusColor(r.status)}
                      variant="outlined"
                      sx={{ height: 16, fontSize: '0.5625rem' }}
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

    </Box>
  );
}
