// src/apps/my/components/RequestTimeline.jsx
// Presentational — an ordered list (<ol>) of correspondence events in `seq`
// order. Each item shows the actor, localized event type, status transition,
// timestamp, and any comment.

import React, { useMemo } from 'react';
import PropTypes from 'prop-types';
import { Box, Card, CardContent, Stack, Typography } from '@mui/material';
import HistoryIcon from '@mui/icons-material/History';
import { useTranslation } from 'react-i18next';
import { SectionTitle } from './myRequestsCommon';
import {
  codeLabel,
  EVENT_SUFFIX,
  STATUS_SUFFIX,
  formatDateTime,
} from './myRequestsLabels';
import { FONT } from '../../../theme/themeTokens';

export default function RequestTimeline({ events }) {
  const { t, i18n } = useTranslation('my');

  const sorted = useMemo(() => {
    const list = Array.isArray(events) ? events : [];
    return [...list].sort((a, b) => Number(a.seq ?? 0) - Number(b.seq ?? 0));
  }, [events]);

  return (
    <Card variant="outlined">
      <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
        <SectionTitle icon={HistoryIcon} title={t('timelineTitle')} />
        {sorted.length === 0 ? (
          <Typography sx={{ ...FONT.body2, color: 'text.secondary' }}>
            {t('timelineEmpty')}
          </Typography>
        ) : (
          <Box component="ol" sx={{ listStyle: 'none', m: 0, p: 0 }}>
            {sorted.map((event, index) => {
              const actor = event.actor_name || t('timelineSystem');
              const eventLabel = codeLabel(t, 'event', EVENT_SUFFIX, event.event_type);
              const comment =
                event.payload && typeof event.payload === 'object' ? event.payload.comment : null;

              const transitionParts = [];
              if (event.from_status) {
                transitionParts.push(codeLabel(t, 'status', STATUS_SUFFIX, event.from_status));
              }
              if (event.to_status) {
                transitionParts.push(codeLabel(t, 'status', STATUS_SUFFIX, event.to_status));
              }

              return (
                <Box
                  component="li"
                  key={event.id}
                  sx={{ display: 'flex', gap: 1, pb: index === sorted.length - 1 ? 0 : 1.25 }}
                >
                  <Box
                    sx={{
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                    }}
                    aria-hidden="true"
                  >
                    <Box
                      sx={{
                        width: 8,
                        height: 8,
                        borderRadius: '50%',
                        bgcolor: 'primary.main',
                        mt: 0.375,
                        flexShrink: 0,
                      }}
                    />
                    {index < sorted.length - 1 && (
                      <Box sx={{ width: 1, flex: 1, minHeight: 12, bgcolor: 'divider' }} />
                    )}
                  </Box>
                  <Box sx={{ minWidth: 0, pt: 0.125 }}>
                    <Stack
                      direction="row"
                      alignItems="center"
                      spacing={0.75}
                      useFlexGap
                      flexWrap="wrap"
                    >
                      <Typography sx={{ ...FONT.cardTitle }}>
                        {eventLabel}
                      </Typography>
                      <Typography sx={{ ...FONT.body, color: 'text.secondary' }}>
                        {actor}
                      </Typography>
                      <Typography sx={{ ...FONT.body, color: 'text.secondary' }}>
                        {formatDateTime(event.created_at, i18n.language)}
                      </Typography>
                    </Stack>
                    {transitionParts.length > 0 && (
                      <Typography sx={{ ...FONT.body, color: 'text.secondary' }}>
                        {transitionParts.join(' → ')}
                      </Typography>
                    )}
                    {comment && (
                      <Typography sx={{ ...FONT.body, color: 'text.primary' }}>
                        {comment}
                      </Typography>
                    )}
                  </Box>
                </Box>
              );
            })}
          </Box>
        )}
      </CardContent>
    </Card>
  );
}

RequestTimeline.propTypes = {
  events: PropTypes.array.isRequired,
};
