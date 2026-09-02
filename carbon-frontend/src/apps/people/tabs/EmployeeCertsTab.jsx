// src/apps/people/tabs/EmployeeCertsTab.jsx
// Per-employee certifications with expiry urgency badges.
// Sorted: expired first, then soonest-expiring, then no-expiry.

import React from 'react';
import {
  Box, Chip, Paper, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, Tooltip, Typography,
} from '@mui/material';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import { useTranslation } from 'react-i18next';
import EmptyState from '../../../components/Page/EmptyState';
import BadgeIcon from '@mui/icons-material/Badge';
import { daysUntilExpiry, expiryUrgency, formatDate } from '../utils';

function urgencyChip(expiryDate, t) {
  const u = expiryUrgency(expiryDate);
  if (!u) return null;
  const days = daysUntilExpiry(expiryDate);
  if (u === 'expired') return <Chip size="small" icon={<WarningAmberIcon />} label={t('certsTabExpired')} color="error" sx={{ height: 18, fontSize: '0.5625rem' }} />;
  if (u === 'critical') return <Chip size="small" icon={<WarningAmberIcon />} label={t('certsTabDaysLeft', { days })} color="error" sx={{ height: 18, fontSize: '0.5625rem' }} />;
  if (u === 'warning') return <Chip size="small" icon={<WarningAmberIcon />} label={t('certsTabDaysLeft', { days })} color="warning" sx={{ height: 18, fontSize: '0.5625rem' }} />;
  if (u === 'notice') return <Chip size="small" label={t('certsTabDaysLeft', { days })} color="info" variant="outlined" sx={{ height: 18, fontSize: '0.5625rem' }} />;
  return null;
}

export default function EmployeeCertsTab({ entityData }) {
  const { t } = useTranslation('people');
  const emp = entityData || {};
  const empId = emp.empId ?? emp.id;

  const myCerts = (emp.certifications || [])
    .filter(c => c.employee === empId)
    .sort((a, b) => {
      // expired/critical/warning first; then by expiry ascending; no-expiry last
      const da = daysUntilExpiry(a.expiry_date) ?? Infinity;
      const db = daysUntilExpiry(b.expiry_date) ?? Infinity;
      return da - db;
    });

  return (
    <Box sx={{ p: 2 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.25 }}>
        <Typography sx={{ fontSize: '0.875rem', fontWeight: 600 }}>{t('certificationsTitle')}</Typography>
        <Typography sx={{ fontSize: '0.6875rem', color: 'text.secondary' }}>
          {myCerts.length} {myCerts.length === 1 ? 'credential' : 'credentials'}
        </Typography>
      </Box>

      {myCerts.length === 0 ? (
        <EmptyState title={t('certsTabEmpty')} description={t('certsTabEmptyDesc')} />
      ) : (
        <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 2 }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                {[t('colCertType'), t('colCertNumber'), t('colIssuedDate'), t('colExpiryDate'), t('colStatus')].map(h => (
                  <TableCell key={h} sx={{ fontWeight: 700, fontSize: '0.625rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'text.secondary', py: 0.75 }}>
                    {h}
                  </TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {myCerts.map(cert => {
                const urg = expiryUrgency(cert.expiry_date);
                const isUrgent = urg === 'expired' || urg === 'critical';
                return (
                  <TableRow key={cert.id} hover sx={{ bgcolor: isUrgent ? 'error.50' : undefined }}>
                    <TableCell sx={{ fontSize: '0.75rem', fontWeight: isUrgent ? 600 : 400, py: 0.625 }}>
                      {cert.cert_type ?? '—'}
                    </TableCell>
                    <TableCell sx={{ fontSize: '0.75rem', fontFamily: 'monospace', py: 0.625 }}>
                      {cert.number || '—'}
                    </TableCell>
                    <TableCell sx={{ fontSize: '0.75rem', fontVariantNumeric: 'tabular-nums', py: 0.625 }}>
                      {formatDate(cert.issued_date)}
                    </TableCell>
                    <TableCell sx={{ fontSize: '0.75rem', fontVariantNumeric: 'tabular-nums', py: 0.625 }}>
                      {cert.expiry_date ? formatDate(cert.expiry_date) : (
                        <Typography component="span" sx={{ fontSize: '0.6875rem', color: 'text.disabled' }}>
                          {t('certsTabNoExpiry')}
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell sx={{ py: 0.625 }}>
                      {urgencyChip(cert.expiry_date, t) || (
                        <Chip size="small" label="Valid" color="success" variant="outlined" sx={{ height: 16, fontSize: '0.5625rem' }} />
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {myCerts.length > 0 && (
        <Box sx={{ mt: 1, display: 'flex', gap: 0.75, flexWrap: 'wrap' }}>
          {[
            { color: 'error', label: 'Expired / Critical (≤7d)' },
            { color: 'warning', label: 'Expiring soon (≤30d)' },
            { color: 'info', label: 'Notice (≤90d)' },
            { color: 'success', label: 'Valid' },
          ].map(({ color, label }) => (
            <Box key={color} sx={{ display: 'flex', alignItems: 'center', gap: 0.375 }}>
              <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: `${color}.main` }} />
              <Typography sx={{ fontSize: '0.5625rem', color: 'text.disabled' }}>{label}</Typography>
            </Box>
          ))}
        </Box>
      )}
    </Box>
  );
}
