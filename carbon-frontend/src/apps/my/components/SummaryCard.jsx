// src/apps/my/components/SummaryCard.jsx
// Presentational — summary of a single correspondence request: title + status
// chip, identity/date fields, a readable leave payload, and a signature seam.

import React from 'react';
import PropTypes from 'prop-types';
import { Card, CardContent, Chip, Divider, Stack, Typography } from '@mui/material';
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
import { FONT } from '../../../theme/themeTokens';

function Field({ label, value }) {
  return (
    <Stack sx={{ minWidth: 120 }}>
      <Typography
        sx={{
          ...FONT.bodySmall,
          color: 'text.secondary',
          textTransform: 'uppercase',
          letterSpacing: '0.03em',
        }}
      >
        {label}
      </Typography>
      <Typography sx={{ ...FONT.body2 }}>{value}</Typography>
    </Stack>
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
  const rows = payloadRows(t, item, i18n.language);

  return (
    <Card variant="outlined">
      <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
        <SectionTitle icon={ReceiptLongIcon} title={t('summaryTitle')} />
        <Stack
          direction="row"
          alignItems="center"
          justifyContent="space-between"
          spacing={1}
          sx={{ mb: 1, minWidth: 0 }}
        >
          <Typography sx={{ ...FONT.heading, minWidth: 0, overflowWrap: 'anywhere' }}>
            {item?.title || '—'}
          </Typography>
          <Chip
            size="small"
            variant="outlined"
            color={STATUS_COLOR[item?.status] || 'default'}
            label={codeLabel(t, 'status', STATUS_SUFFIX, item?.status)}
          />
        </Stack>
        <Stack direction="row" spacing={2} useFlexGap flexWrap="wrap" rowGap={1}>
          <Field label={t('summaryReferenceNo')} value={item?.reference_no || '—'} />
          <Field label={t('summaryType')} value={requestTypeLabel(t, item)} />
          <Field label={t('summaryCreated')} value={formatDate(item?.created_at, i18n.language)} />
          <Field label={t('summaryUpdated')} value={formatDate(item?.updated_at, i18n.language)} />
          <Field label={t('summaryResolved')} value={formatDate(item?.resolved_at, i18n.language)} />
        </Stack>
        {rows.length > 0 && (
          <>
            <Divider sx={{ my: 1 }} />
            <Stack direction="row" spacing={2} useFlexGap flexWrap="wrap" rowGap={1}>
              {rows.map((row, index) => (
                <Field key={`${row.label}-${index}`} label={row.label} value={row.value} />
              ))}
            </Stack>
          </>
        )}
        <Divider sx={{ my: 1 }} />
        <Stack direction="row" alignItems="center" spacing={1}>
          <Typography sx={{ ...FONT.body, color: 'text.secondary' }}>
            {t('summarySignature')}
          </Typography>
          <Typography
            sx={{ ...FONT.body2, color: hasSignature ? 'warning.main' : 'text.secondary' }}
          >
            {hasSignature ? t('summarySignaturePending') : t('summarySignatureNone')}
          </Typography>
        </Stack>
      </CardContent>
    </Card>
  );
}

SummaryCard.propTypes = {
  item: PropTypes.object.isRequired,
};
