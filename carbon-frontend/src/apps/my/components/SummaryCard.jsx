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
  subjectTypeLabel,
  leaveTypeLabel,
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
  const payload = item?.payload && typeof item.payload === 'object' ? item.payload : {};
  const hasSignature = Boolean(item?.signature_ref);

  return (
    <Card variant="outlined">
      <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
        <SectionTitle icon={ReceiptLongIcon} title={t('summaryTitle')} />
        <Stack
          direction="row"
          alignItems="center"
          justifyContent="space-between"
          spacing={1}
          sx={{ mb: 1 }}
        >
          <Typography sx={{ ...FONT.heading }}>
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
          <Field label={t('summaryType')} value={subjectTypeLabel(t, item?.subject_type)} />
          <Field label={t('summaryCreated')} value={formatDate(item?.created_at, i18n.language)} />
          <Field label={t('summaryUpdated')} value={formatDate(item?.updated_at, i18n.language)} />
          <Field label={t('summaryResolved')} value={formatDate(item?.resolved_at, i18n.language)} />
        </Stack>
        <Divider sx={{ my: 1 }} />
        <Stack direction="row" spacing={2} useFlexGap flexWrap="wrap" rowGap={1}>
          <Field label={t('summaryLeaveType')} value={leaveTypeLabel(t, payload.leave_type)} />
          <Field label={t('summaryStart')} value={formatDate(payload.start_date, i18n.language)} />
          <Field label={t('summaryEnd')} value={formatDate(payload.end_date, i18n.language)} />
          <Field label={t('summaryDays')} value={payload.days != null ? String(payload.days) : '—'} />
          <Field label={t('summaryNote')} value={payload.note || '—'} />
        </Stack>
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
