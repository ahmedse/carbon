import React, { useEffect } from 'react';
import PropTypes from 'prop-types';
import { Alert, Box, Button, Chip, LinearProgress, Stack, Typography } from '@mui/material';
import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { FONT } from '../../theme/themeTokens';
import EmptyState from '../Page/EmptyState';
import LoadingSkeleton from '../Page/LoadingSkeleton';
import ErrorAlert from '../Page/ErrorAlert';
import LessonCoach from './LessonCoach';
import useGuide from '../../hooks/useGuide';

const PHASES = ['gather', 'close'];
const STATE_COLOR = { done: 'success', started: 'primary', snoozed: 'default', offered: 'default' };

function LessonRow({ lesson, selected, onOpen }) {
  const { t } = useTranslation('guide');
  return (
    <Box
      role="button"
      tabIndex={0}
      onClick={() => onOpen(lesson.id)}
      onKeyDown={(event) => { if (event.key === 'Enter') onOpen(lesson.id); }}
      data-testid={`guide-lesson-${lesson.id}`}
      sx={{
        display: 'flex', alignItems: 'center', gap: 1, p: 1, borderRadius: 1, cursor: 'pointer',
        border: 1, borderColor: selected ? 'primary.main' : 'divider',
        bgcolor: selected ? 'action.selected' : 'background.paper',
      }}
    >
      <Typography sx={{ ...FONT.body2, flex: 1, minWidth: 0 }}>{lesson.title}</Typography>
      {lesson.is_next && <Chip size="small" color="primary" label={t('hub.next')} sx={FONT.chip} />}
      {lesson.blocker && <Chip size="small" color="warning" variant="outlined" label={t('hub.blocked')} sx={FONT.chip} />}
      <Chip size="small" color={STATE_COLOR[lesson.state] || 'default'} variant={lesson.state === 'done' ? 'filled' : 'outlined'} label={t(`state.${lesson.state}`)} sx={FONT.chip} />
      <Typography sx={{ ...FONT.caption, color: 'text.secondary' }}>{t('hub.minutes', { count: lesson.minutes })}</Typography>
    </Box>
  );
}

LessonRow.propTypes = {
  lesson: PropTypes.shape({}).isRequired,
  selected: PropTypes.bool.isRequired,
  onOpen: PropTypes.func.isRequired,
};

/** A person's guide for one domain app: tracks, lessons grouped gathering-first, and the coach. */
export default function GuideHub({ appId, lessonId, onOpen, onClose }) {
  const { t } = useTranslation('guide');
  const { phase, data, reload, lang } = useGuide(appId);
  const [params] = useSearchParams();
  const stayOnHub = params.get('list') === '1';

  useEffect(() => {
    if (phase !== 'loaded' || lessonId || stayOnHub || !data?.resume?.id) return;
    onOpen(data.resume.id, { replace: true });
  }, [phase, lessonId, stayOnHub, data, onOpen]);

  if (phase === 'loading') return <LoadingSkeleton variant="card" />;
  if (phase === 'error') return <ErrorAlert message={t('hub.loadFailed')} onRetry={reload} />;
  const lessons = data?.lessons || [];
  if (lessons.length === 0) {
    return <EmptyState title={t('hub.emptyTitle')} description={t('hub.emptyBody')} />;
  }
  const next = lessons.find((l) => l.id === data.next_id);
  const nextAfter = (id) => {
    const index = lessons.findIndex((l) => l.id === id);
    const found = lessons.slice(index + 1).find((l) => ['offered', 'started'].includes(l.state) && !l.blocker);
    return found ? () => onOpen(found.id) : undefined;
  };

  return (
    <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', md: 'minmax(280px, 1fr) minmax(360px, 1.4fr)' }, alignItems: 'start' }}>
      <Stack spacing={2}>
        <Stack spacing={1}>
          {(data.tracks || []).map((track) => (
            <Box key={track.id} data-testid={`guide-track-${track.id}`}>
              <Stack direction="row" justifyContent="space-between">
                <Typography sx={FONT.cardTitle}>
                  {track.title || track.id}
                  {data.recommended_track === track.id && (
                    <Chip size="small" color="primary" label={t('hub.recommended')} sx={{ ...FONT.chip, marginInlineStart: 1 }} />
                  )}
                </Typography>
                <Typography sx={{ ...FONT.caption, color: 'text.secondary' }}>{t('hub.progress', { done: track.done, total: track.total })}</Typography>
              </Stack>
              {track.blurb && <Typography sx={{ ...FONT.bodySmall, color: 'text.secondary' }}>{track.blurb}</Typography>}
              <LinearProgress variant="determinate" value={track.total ? (100 * track.done) / track.total : 0} sx={{ mt: 0.5, height: 4, borderRadius: 2 }} />
            </Box>
          ))}
        </Stack>

        {next && !lessonId && (
          <Alert severity="info" action={<Button color="inherit" size="small" onClick={() => onOpen(next.id)}>{t('hub.start')}</Button>}>
            {t('hub.nextUp', { title: next.title })}
          </Alert>
        )}

        {(data.tracks || []).map((track) => (
          <Box key={`list-${track.id}`}>
            {PHASES.map((phaseId) => {
              const rows = lessons.filter((l) => l.track === track.id && l.phase === phaseId);
              if (rows.length === 0) return null;
              return (
                <Stack key={phaseId} spacing={0.75} sx={{ mb: 1.5 }}>
                  <Typography sx={{ ...FONT.sectionTitle, color: 'text.secondary' }}>
                    {(track.title || track.id)} · {t(`hub.phase.${phaseId}`)}
                  </Typography>
                  {rows.map((lesson) => (
                    <LessonRow key={lesson.id} lesson={lesson} selected={lesson.id === lessonId} onOpen={onOpen} />
                  ))}
                </Stack>
              );
            })}
          </Box>
        ))}
      </Stack>

      <Box>
        {lessonId ? (
          <LessonCoach
            appId={appId}
            lessonId={lessonId}
            lang={lang}
            onChanged={reload}
            onNext={nextAfter(lessonId)}
            onExit={onClose}
          />
        ) : (
          <EmptyState title={t('hub.pickTitle')} description={t('hub.pickBody')} />
        )}
      </Box>
    </Box>
  );
}

GuideHub.propTypes = {
  appId: PropTypes.string.isRequired,
  lessonId: PropTypes.string,
  onOpen: PropTypes.func.isRequired,
  onClose: PropTypes.func.isRequired,
};

GuideHub.defaultProps = { lessonId: undefined };
