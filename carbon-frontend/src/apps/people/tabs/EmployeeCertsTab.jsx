// src/apps/people/tabs/EmployeeCertsTab.jsx
// Per-employee certifications with expiry urgency badges.
// Sorted: expired first, then soonest-expiring, then no-expiry.

import React from 'react';
import {
  Box, Paper, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, Typography,
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import EmptyState from '../../../components/Page/EmptyState';
import CertExpiryChip, { CertExpiryLegend } from '../components/CertExpiryChip';
import { daysUntilExpiry, expiryUrgency, formatDate, refCode, refLabel } from '../utils';

export default function EmployeeCertsTab({ entityData }) {
  const { t } = useTranslation('people');
  const emp = entityData || {};
  const empId = emp.empId ?? emp.id;

  const myCerts = (emp.certifications || [])
    .filter((c) => c.employee === empId)
    .sort((a, b) => {
      const da = daysUntilExpiry(a.expiry_date) ?? Infinity;
      const db = daysUntilExpiry(b.expiry_date) ?? Infinity;
      return da - db;
    });

  return (
    <Box sx={{ p: 2 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.25 }}>
        <Typography variant="subtitle2">{t('certificationsTitle')}</Typography>
        <Typography variant="caption" color="text.secondary">
          {t('certsTabCount', { count: myCerts.length })}
        </Typography>
      </Box>

      {myCerts.length === 0 ? (
        <EmptyState title={t('certsTabEmpty')} description={t('certsTabEmptyDesc')} />
      ) : (
        <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 2 }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                {[t('colCertType'), t('colCertNumber'), t('colIssuedDate'), t('colExpiryDate'), t('colStatus')].map((h) => (
                  <TableCell key={h}>{h}</TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {myCerts.map((cert) => {
                const urg = expiryUrgency(cert.expiry_date);
                const isUrgent = urg === 'expired' || urg === 'critical';
                return (
                  <TableRow key={cert.id} hover sx={{ bgcolor: isUrgent ? 'error.50' : undefined }}>
                    <TableCell sx={{ fontWeight: isUrgent ? 600 : 400 }}>
                      {refLabel(cert.cert_type) || refCode(cert.cert_type) || '—'}
                    </TableCell>
                    <TableCell sx={{ fontFamily: 'monospace' }}>
                      {cert.number || '—'}
                    </TableCell>
                    <TableCell sx={{ fontVariantNumeric: 'tabular-nums' }}>
                      {formatDate(cert.issued_date)}
                    </TableCell>
                    <TableCell sx={{ fontVariantNumeric: 'tabular-nums' }}>
                      {cert.expiry_date ? formatDate(cert.expiry_date) : (
                        <Typography component="span" variant="caption" color="text.disabled">
                          {t('certsTabNoExpiry')}
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell>
                      <CertExpiryChip expiryDate={cert.expiry_date} />
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {myCerts.length > 0 && <CertExpiryLegend />}
    </Box>
  );
}
