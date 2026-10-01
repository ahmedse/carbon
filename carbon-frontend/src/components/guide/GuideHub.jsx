import React, { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Accordion, AccordionDetails, AccordionSummary, Alert, Box, Button, Chip, LinearProgress, Paper, Stack, Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
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

function LessonRow({ lesson, selected, onOpen, quiet }) {
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
        border: 1,
        borderColor: selected && !quiet ? 'primary.main' : 'divider',
        bgcolor: selected && !quiet ? 'action.selected' : 'background.paper',
      }}
    >
      <Typography sx={{ ...FONT.body2, flex: 1, minWidth: 0, color: quiet ? 'text.secondary' : 'text.primary' }}>{lesson.title}</Typography>
      {!quiet && lesson.is_next && <Chip size="small" color="primary" label={t('hub.next')} sx={FONT.chip} />}
      {lesson.blocker && <Chip size="small" color={quiet ? 'default' : 'warning'} variant="outlined" label={t('hub.blocked')} sx={FONT.chip} />}
      <Chip
        size="small"
        color={quiet ? 'default' : (STATE_COLOR[lesson.state] || 'default')}
        variant={lesson.state === 'done' && !quiet ? 'filled' : 'outlined'}
        label={t(`state.${lesson.state}`)}
        sx={FONT.chip}
      />
      <Typography sx={{ ...FONT.caption, color: 'text.secondary' }}>{t('hub.minutes', { count: lesson.minutes })}</Typography>
    </Box>
  );
}

LessonRow.propTypes = {
  lesson: PropTypes.shape({}).isRequired,
  selected: PropTypes.bool.isRequired,
  onOpen: PropTypes.func.isRequired,
  quiet: PropTypes.bool,
};

LessonRow.defaultProps = { quiet: false };

/** First unfinished live lesson, in catalog order. */
export function pickEntryLesson(entry) {
  const open = entry.filter((lesson) => lesson.state !== 'done' && lesson.state !== 'snoozed');
  return (open[0] || entry[0] || {}).id || null;
}

function nextUnfinished(pool, id, onOpen) {
  const index = pool.findIndex((lesson) => lesson.id === id);
  const found = pool.slice(index + 1).find((lesson) => ['offered', 'started'].includes(lesson.state) && !lesson.blocker);
  return found ? () => onOpen(found.id) : undefined;
}

/** Data-entry lessons in front. Every other lesson stays, collapsed and quiet. */
function StageGuide({ appId, lessons, tracks, lessonId, lang, onOpen, onClose, onChanged }) {
  const { t } = useTranslation('guide');
  const entry = lessons.filter((lesson) => lesson.stage);
  const later = lessons.filter((lesson) => !lesson.stage);
  const selected = lessons.find((lesson) => lesson.id === lessonId);
  const selectedLater = Boolean(selected && !selected.stage);
  const [laterOpen, setLaterOpen] = useState(false);

  useEffect(() => {
    if (selectedLater) setLaterOpen(true);
  }, [selectedLater]);

  const done = entry.filter((lesson) => lesson.state === 'done').length;

  return (
    <Box
      data-testid="guide-stage"
      sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', md: 'minmax(420px, 1.5fr) minmax(260px, 0.85fr)' }, alignItems: 'start' }}
    >
      <Box>
        {lessonId ? (
          <LessonCoach
            appId={appId}
            lessonId={lessonId}
            lang={lang}
            variant={selected?.stage ? 'class' : 'steps'}
            onChanged={onChanged}
            onNext={nextUnfinished(selected?.stage ? entry : later, lessonId, onOpen)}
            onExit={onClose}
          />
        ) : (
          <EmptyState title={t('hub.pickTitle')} description={t('hub.pickBody')} />
        )}
      </Box>

      <Stack spacing={1.5}>
        <Paper variant="outlined" data-testid="guide-entry" sx={{ p: 1.5 }}>
          <Stack direction="row" justifyContent="space-between" alignItems="baseline" sx={{ mb: 1 }}>
            <Typography sx={FONT.cardTitle}>{t('hub.entry.title')}</Typography>
            <Typography sx={{ ...FONT.caption, color: 'text.secondary' }}>{t('hub.progress', { done, total: entry.length })}</Typography>
          </Stack>
          <Stack spacing={0.75}>
            {entry.map((lesson) => (
              <LessonRow key={lesson.id} lesson={lesson} selected={lesson.id === lessonId} onOpen={onOpen} />
            ))}
          </Stack>
        </Paper>

        {later.length > 0 && (
          <Accordion
            expanded={laterOpen}
            onChange={(_, open) => setLaterOpen(open)}
            disableGutters
            elevation={0}
            data-testid="guide-later"
            sx={{ border: 1, borderColor: 'divider', borderRadius: 1, bgcolor: 'transparent', '&:before': { display: 'none' } }}
          >
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Box>
                <Typography sx={{ ...FONT.body2, color: 'text.secondary' }}>{t('hub.entry.later')}</Typography>
                <Typography sx={{ ...FONT.caption, color: 'text.secondary' }}>{t('hub.entry.laterHint')}</Typography>
              </Box>
            </AccordionSummary>
            <AccordionDetails>
              {tracks.map((track) => {
                const members = later.filter((lesson) => lesson.track === track.id);
                if (members.length === 0) return null;
                const trackDone = members.filter((lesson) => lesson.state === 'done').length;
                return (
                  <Box key={track.id} sx={{ mb: 1.5 }}>
                    <Stack direction="row" justifyContent="space-between" alignItems="baseline">
                      <Typography sx={{ ...FONT.sectionTitle, color: 'text.secondary' }}>{track.title || track.id}</Typography>
                      <Typography sx={{ ...FONT.caption, color: 'text.secondary' }}>{t('hub.progress', { done: trackDone, total: members.length })}</Typography>
                    </Stack>
                    {PHASES.map((phaseId) => {
                      const rows = members.filter((lesson) => lesson.phase === phaseId);
                      if (rows.length === 0) return null;
                      return (
                        <Stack key={phaseId} spacing={0.75} sx={{ mt: 0.75 }}>
                          <Typography sx={{ ...FONT.caption, color: 'text.secondary' }}>{t(`hub.phase.${phaseId}`)}</Typography>
                          {rows.map((lesson) => (
                            <LessonRow key={lesson.id} lesson={lesson} selected={lesson.id === lessonId} onOpen={onOpen} quiet />
                          ))}
                        </Stack>
                      );
                    })}
                  </Box>
                );
              })}
            </AccordionDetails>
          </Accordion>
        )}
      </Stack>
    </Box>
  );
}

StageGuide.propTypes = {
  appId: PropTypes.string.isRequired,
  lessons: PropTypes.arrayOf(PropTypes.shape({})).isRequired,
  tracks: PropTypes.arrayOf(PropTypes.shape({})).isRequired,
  lessonId: PropTypes.string,
  lang: PropTypes.string,
  onOpen: PropTypes.func.isRequired,
  onClose: PropTypes.func.isRequired,
  onChanged: PropTypes.func.isRequired,
};

StageGuide.defaultProps = { lessonId: undefined, lang: 'en' };

/** A person's guide for one domain app: tracks, lessons grouped gathering-first, and the coach. */
export default function GuideHub({ appId, lessonId, onOpen, onClose }) {
  const { t } = useTranslation('guide');
  const { phase, data, reload, lang } = useGuide(appId);
  const [params] = useSearchParams();
  const stayOnHub = params.get('list') === '1';

  useEffect(() => {
    if (phase !== 'loaded' || lessonId || stayOnHub) return;
    const entry = (data?.lessons || []).filter((lesson) => lesson.stage);
    if (entry.length) {
      const id = pickEntryLesson(entry);
      if (id) onOpen(id, { replace: true });
      return;
    }
    if (data?.resume?.id) onOpen(data.resume.id, { replace: true });
  }, [phase, lessonId, stayOnHub, data, onOpen]);

  if (phase === 'loading') return <LoadingSkeleton variant="card" />;
  if (phase === 'error') return <ErrorAlert message={t('hub.loadFailed')} onRetry={reload} />;
  const lessons = data?.lessons || [];
  if (lessons.length === 0) {
    return <EmptyState title={t('hub.emptyTitle')} description={t('hub.emptyBody')} />;
  }
  const next = lessons.find((l) => l.id === data.next_id);
  if (lessons.some((lesson) => lesson.stage)) {
    return (
      <StageGuide
        appId={appId}
        lessons={lessons}
        tracks={data.tracks || []}
        lessonId={lessonId}
        lang={lang}
        onOpen={onOpen}
        onClose={onClose}
        onChanged={reload}
      />
    );
  }
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
