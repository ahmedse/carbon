// src/apps/my/components/SummaryCard.jsx
// Presentational — denser two-zone summary for Team + My detail:
// header (title + status) → identity row → request payload grid → quiet signature.

import React, { useMemo } from 'react';
import PropTypes from 'prop-types';
import { Box, Card, CardContent, Chip, Divider, Stack, Typography } from '@mui/material';
import ReceiptLongIcon from '@mui/icons-material/ReceiptLong';
import { useTranslation } from 'react-i18next';
import { SectionTitle } from './myRequestsCommon';
import {
  STATUS_COLOR,
  STATUS_SUFFIX,
  codeLabel,
  requestTypeLabel,
  payloadRows,
  formatDate,
} from './myRequestsLabels';

function isEmptyValue(value) {
  if (value == null) return true;
  if (typeof value === 'string') {
    const trimmed = value.trim();
    return trimmed === '' || trimmed === '—';
  }
  return false;
}

function Field({ label, value }) {
  return (
    <Box sx={{ minWidth: 0 }}>
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{
          display: 'block',
          fontSize: '0.625rem',
          textTransform: 'uppercase',
          letterSpacing: '0.03em',
          lineHeight: 1.2,
        }}
      >
        {label}
      </Typography>
      <Typography variant="body2" sx={{ overflowWrap: 'anywhere', lineHeight: 1.35 }}>
        {value}
      </Typography>
    </Box>
  );
}

Field.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.node,
};

Field.defaultProps = {
  value: null,
};

export default function SummaryCard({ item }) {
  const { t, i18n } = useTranslation('my');
  const hasSignature = Boolean(item?.signature_ref);

  const identityFields = useMemo(() => {
    const fields = [
      {
        label: t('summaryRequester'),
        value: item?.requester_name || null,
      },
      { label: t('summaryReferenceNo'), value: item?.reference_no || null },
      { label: t('summaryType'), value: requestTypeLabel(t, item) },
      { label: t('summaryCreated'), value: formatDate(item?.created_at, i18n.language) },
      { label: t('summaryUpdated'), value: formatDate(item?.updated_at, i18n.language) },
    ];
    if (item?.resolved_at) {
      fields.push({
        label: t('summaryResolved'),
        value: formatDate(item.resolved_at, i18n.language),
      });
    }
    return fields.filter((f) => !isEmptyValue(f.value));
  }, [item, t, i18n.language]);

  const requestRows = useMemo(
    () => payloadRows(t, item, i18n.language).filter((row) => !isEmptyValue(row.value)),
    [item, t, i18n.language],
  );

  return (
    <Card variant="outlined">
      <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
        <SectionTitle icon={ReceiptLongIcon} title={t('summaryTitle')} />

        {/* Header: title + status */}
        <Stack
          direction="row"
          alignItems="center"
          justifyContent="space-between"
          spacing={1}
          sx={{ mb: 1, minWidth: 0 }}
        >
          <Typography
            variant="subtitle1"
            sx={{ fontWeight: 600, minWidth: 0, overflowWrap: 'anywhere', lineHeight: 1.3 }}
          >
            {item?.title || '—'}
          </Typography>
          <Chip
            size="small"
            variant="outlined"
            color={STATUS_COLOR[item?.status] || 'default'}
            label={codeLabel(t, 'status', STATUS_SUFFIX, item?.status)}
          />
        </Stack>

        {/* Identity zone */}
        {identityFields.length > 0 && (
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: {
                xs: 'repeat(2, minmax(0, 1fr))',
                sm: 'repeat(3, minmax(0, 1fr))',
                md: 'repeat(5, minmax(0, 1fr))',
              },
              gap: 1,
              columnGap: 1.5,
            }}
          >
            {identityFields.map((f) => (
              <Field key={f.label} label={f.label} value={f.value} />
            ))}
          </Box>
        )}

        {/* Request / payload zone */}
        {requestRows.length > 0 && (
          <>
            <Divider sx={{ my: 1 }} />
            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: {
                  xs: 'repeat(2, minmax(0, 1fr))',
                  sm: 'repeat(3, minmax(0, 1fr))',
                },
                gap: 1,
                columnGap: 1.5,
              }}
            >
              {requestRows.map((row, index) => (
                <Field key={`${row.label}-${index}`} label={row.label} value={row.value} />
              ))}
            </Box>
          </>
        )}

        {/* Signature as quiet caption */}
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ display: 'block', mt: 1, fontSize: '0.6875rem' }}
        >
          {t('summarySignature')}
          {': '}
          <Box
            component="span"
            sx={{ color: hasSignature ? 'warning.main' : 'text.secondary' }}
          >
            {hasSignature ? t('summarySignaturePending') : t('summarySignatureNone')}
          </Box>
        </Typography>
      </CardContent>
    </Card>
  );
}

SummaryCard.propTypes = {
  item: PropTypes.object.isRequired,
};
