import React from 'react';
import PropTypes from 'prop-types';
import { Box, Chip, Stack, Typography } from '@mui/material';
import { useTranslation } from 'react-i18next';

import { FONT } from '../../theme/themeTokens';
import { getLiveCard, registerLiveCard } from './liveRegistry';

// Apps register their own kinds by shipping apps/<id>/guideLive.jsx.
import.meta.glob('../../apps/*/guideLive.jsx', { eager: true });

function IdentityCard({ live }) {
  const { t } = useTranslation('guide');
  const caps = live.capabilities || [];
  const units = live.org_units || [];
  return (
    <Stack spacing={1}>
      <Box>
        <Typography sx={{ ...FONT.statLabel, color: 'text.secondary' }}>{t('live.identity.capabilities')}</Typography>
        <Stack direction="row" spacing={0.5} useFlexGap flexWrap="wrap" sx={{ mt: 0.5 }}>
          {caps.length === 0 && <Typography sx={FONT.body}>{t('live.identity.none')}</Typography>}
          {caps.map((cap) => (
            <Chip key={cap} size="small" variant="outlined" label={cap.includes(':') ? cap.split(':')[1] : cap} sx={FONT.chip} />
          ))}
        </Stack>
      </Box>
      <Box>
        <Typography sx={{ ...FONT.statLabel, color: 'text.secondary' }}>{t('live.identity.orgUnits')}</Typography>
        <Typography sx={FONT.body}>{units.length ? units.join(', ') : t('live.identity.none')}</Typography>
      </Box>
    </Stack>
  );
}

IdentityCard.propTypes = { live: PropTypes.shape({}).isRequired };
registerLiveCard('identity', IdentityCard);

/** Renders the live object for a lesson, or nothing when no card is registered for its kind. */
export default function LiveCard({ live }) {
  const Card = live ? getLiveCard(live.kind) : null;
  if (!Card) return null;
  return (
    <Box
      data-testid="guide-live"
      sx={{ border: 1, borderColor: 'divider', borderRadius: 1.5, p: 1.5, bgcolor: 'action.hover' }}
    >
      <Card live={live} />
    </Box>
  );
}

LiveCard.propTypes = { live: PropTypes.shape({ kind: PropTypes.string }) };
LiveCard.defaultProps = { live: null };
