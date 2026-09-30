// Carbon's live cards for the Guide (domain_packs/carbon/guide). Registers `period` and `sources`.
// Counts, names and states only. The server never sends a kilogram, and neither does this file.
import React from 'react';
import PropTypes from 'prop-types';
import { Box, Chip, Stack, Typography } from '@mui/material';
import { useTranslation } from 'react-i18next';

import { registerLiveCard } from '../../components/guide/liveRegistry';
import { FONT } from '../../theme/themeTokens';

function PeriodCard({ live }) {
  const { t } = useTranslation('guide');
  const current = live.current;
  return (
    <Stack spacing={0.5}>
      <Typography sx={{ ...FONT.statLabel, color: 'text.secondary' }}>{t('live.period.title')}</Typography>
      {current ? (
        <Stack direction="row" spacing={1} alignItems="center" useFlexGap flexWrap="wrap">
          <Typography sx={FONT.body2}>{current.name}</Typography>
          <Chip size="small" color={current.status === 'open' ? 'success' : 'default'} label={t(`live.period.status.${current.status}`, { defaultValue: current.status })} sx={FONT.chip} />
          <Typography sx={{ ...FONT.bodySmall, color: 'text.secondary' }}>{current.start_date} – {current.end_date}</Typography>
        </Stack>
      ) : (
        <Typography sx={FONT.body}>{t('live.period.none')}</Typography>
      )}
      <Typography sx={{ ...FONT.bodySmall, color: 'text.secondary' }}>{t('live.period.openCount', { count: live.open_count })}</Typography>
    </Stack>
  );
}

PeriodCard.propTypes = { live: PropTypes.shape({}).isRequired };

function SourcesCard({ live }) {
  const { t } = useTranslation('guide');
  const items = live.items || [];
  if (items.length === 0) {
    return <Typography sx={FONT.body}>{t('live.sources.none')}</Typography>;
  }
  return (
    <Stack spacing={0.75}>
      <Typography sx={{ ...FONT.statLabel, color: 'text.secondary' }}>{t('live.sources.title')}</Typography>
      {items.map((src) => (
        <Box key={src.id} sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
          <Typography sx={{ ...FONT.body2, flex: 1, minWidth: 140 }}>{src.name}</Typography>
          <Chip size="small" variant="outlined" label={t('live.sources.scope', { scope: src.scope })} sx={FONT.chip} />
          <Chip size="small" label={t(`live.sources.status.${src.status}`, { defaultValue: src.status })} sx={FONT.chip} />
          <Typography sx={{ ...FONT.bodySmall, color: 'text.secondary' }}>
            {src.row_count == null ? t('live.sources.notLinked') : t('live.sources.rows', { count: src.row_count })}
          </Typography>
        </Box>
      ))}
    </Stack>
  );
}

SourcesCard.propTypes = { live: PropTypes.shape({}).isRequired };

function BoundaryCard({ live }) {
  const { t } = useTranslation('guide');
  const boundary = live.boundary;
  return (
    <Stack spacing={0.5}>
      <Typography sx={{ ...FONT.statLabel, color: 'text.secondary' }}>{t('live.boundary.title')}</Typography>
      {boundary ? (
        <Stack direction="row" spacing={1} alignItems="center" useFlexGap flexWrap="wrap">
          <Typography sx={FONT.body2}>{boundary.name}</Typography>
          <Chip size="small" label={t(`live.boundary.approach.${boundary.approach}`, { defaultValue: boundary.approach })} sx={FONT.chip} />
        </Stack>
      ) : (
        <Typography sx={FONT.body}>{t('live.boundary.none')}</Typography>
      )}
    </Stack>
  );
}

BoundaryCard.propTypes = { live: PropTypes.shape({}).isRequired };

registerLiveCard('boundary', BoundaryCard);
registerLiveCard('period', PeriodCard);
registerLiveCard('sources', SourcesCard);

export const GUIDE_LIVE_KINDS = ['boundary', 'period', 'sources'];
