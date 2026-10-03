import React from 'react';
import PropTypes from 'prop-types';
import { Box, Button, Chip, LinearProgress, Stack, Typography } from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import { useTranslation } from 'react-i18next';

import { FONT } from '../../theme/themeTokens';
import MixedText from './MixedText';
import {
  lessonsMinutes, missionFirstMove, missionLesson, sceneOf,
} from './journeyVoice';
import { overallProgress } from './journeyProgress';
import { stageArt } from './journeyArt';

const ROLES = [
  { track: 'L', key: 'role.lead' },
  { track: 'D', key: 'role.owner' },
  { track: 'C', key: 'role.observer' },
];

/**
 * The camp hero: the one camp you are on, framed as a scene with one clear
 * mission and the real opening move, rather than a screen tour.
 *
 * Everything here is engine or pack data — the camp position is the station's
 * place on the spine, the mission is the lesson the engine put next on this
 * caller's path, the move is that lesson's first declared step, and the time is
 * the lesson's own `minutes`. The slim line above names the one honest number:
 * outcomes the app has actually proven. The button opens the lesson reader; the
 * real host action stays the labelled "Go to <page>" inside the lesson steps.
 * When the caller has never chosen a seat, a one-time prompt sets the path.
 */
export default function JourneyScenario({
  journey, station, role, compact, onOpenLesson, showRolePrompt, onRoleChange,
}) {
  const { t } = useTranslation('journey');
  if (!station) return null;

  const scene = sceneOf(journey, station);
  const mission = missionLesson(station);
  const move = missionFirstMove(mission);
  const minutes = mission ? lessonsMinutes(station.lessons) : 0;
  const progress = overallProgress(journey);
  const { Icon: StageIcon, color: stageColor } = stageArt(station);
  const outcomesPct = progress.outcomesTotal > 0
    ? Math.round((progress.outcomesProven / progress.outcomesTotal) * 100)
    : 0;

  return (
    <Box
      data-testid="journey-scenario-card"
      data-compact={compact ? 'true' : 'false'}
      sx={{
        position: 'relative',
        overflow: 'hidden',
        border: '1px solid',
        borderColor: 'divider',
        borderInlineStartWidth: 3,
        borderInlineStartColor: `${stageColor}.main`,
        borderRadius: 1.5,
        p: compact ? 1 : 2,
        mb: 1.5,
      }}
    >
      {!compact && (
        <Typography
          aria-hidden="true"
          sx={{
            position: 'absolute',
            insetInlineEnd: 8,
            top: -18,
            fontSize: '5.5rem',
            fontWeight: 800,
            lineHeight: 1,
            color: `${stageColor}.main`,
            opacity: 0.08,
            pointerEvents: 'none',
            userSelect: 'none',
          }}
        >
          {scene.n}
        </Typography>
      )}

      <Stack direction="row" spacing={0.75} alignItems="center" flexWrap="wrap" sx={{ position: 'relative' }}>
        <Chip
          size="small"
          color={stageColor}
          variant="outlined"
          icon={<StageIcon sx={{ fontSize: 15 }} />}
          label={t('scenario.camp', { n: scene.n, total: scene.total })}
          sx={FONT.chip}
        />
        {role && !compact && (
          <Typography sx={{ ...FONT.caption, color: 'text.secondary' }} data-testid="journey-scenario-role">
            {t(`scenario.${role}`)}
          </Typography>
        )}
      </Stack>

      <MixedText
        text={station.title}
        glossary={journey?.glossary}
        component={compact ? 'h4' : 'h2'}
        sx={{ ...FONT.pageTitle, mt: 0.75, position: 'relative' }}
      />

      {!compact && station.what && (
        <MixedText
          text={station.what}
          glossary={journey?.glossary}
          component="p"
          testId="journey-camp-what"
          sx={{
            ...FONT.body2,
            color: 'text.secondary',
            mt: 0.25,
            position: 'relative',
            display: '-webkit-box',
            WebkitBoxOrient: 'vertical',
            WebkitLineClamp: 3,
            overflow: 'hidden',
          }}
        />
      )}

      {!compact && station.voice && (
        <Box
          data-testid="journey-voice"
          sx={{
            position: 'relative',
            mt: 1,
            borderInlineStartWidth: 3,
            borderInlineStartStyle: 'solid',
            borderInlineStartColor: 'primary.main',
            paddingInlineStart: 1.25,
          }}
        >
          <Typography sx={FONT.caption} color="text.secondary">
            {t('scenario.voice')}
          </Typography>
          <MixedText
            text={station.voice}
            glossary={journey?.glossary}
            component="p"
            sx={{ ...FONT.body2, fontStyle: 'italic', m: 0 }}
          />
        </Box>
      )}

      {mission ? (
        <Box sx={{ mt: 1.5, position: 'relative' }} data-testid="journey-mission">
          <Typography sx={FONT.sectionTitle} color="text.secondary">{t('scenario.mission')}</Typography>
          <MixedText text={mission.title} glossary={journey?.glossary} component="div" sx={{ ...FONT.cardTitle, mt: 0.25 }} />
          {move && (move.action || move.title) && (
            <MixedText
              text={move.action || move.title}
              glossary={journey?.glossary}
              component="div"
              sx={{ ...FONT.bodySmall, color: 'text.secondary', mt: 0.25 }}
            />
          )}
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" sx={{ mt: 1 }}>
            <Button
              size={compact ? 'small' : 'medium'}
              variant="contained"
              startIcon={<PlayArrowIcon sx={{ fontSize: 18 }} />}
              onClick={() => onOpenLesson(mission.id)}
              data-testid="journey-mission-open"
              sx={{ textTransform: 'none' }}
            >
              {t('scenario.startLesson')}
            </Button>
            {minutes > 0 && (
              <Typography sx={{ ...FONT.caption, color: 'text.secondary' }} data-testid="journey-mission-minutes">
                {t('scenario.aboutMinutes', { minutes })}
              </Typography>
            )}
          </Stack>
        </Box>
      ) : (
        <Typography sx={{ ...FONT.bodySmall, color: 'text.secondary', mt: 0.75 }} data-testid="journey-no-mission">
          {t('scenario.noMission')}
        </Typography>
      )}

      {!compact && progress.outcomesTotal > 0 && (
        <Stack
          direction="row"
          spacing={1}
          alignItems="center"
          sx={{ mt: 1.5, position: 'relative' }}
          data-testid="journey-scenario-progress"
        >
          <Typography sx={{ ...FONT.caption, color: 'text.secondary', whiteSpace: 'nowrap' }}>
            {t('progress.outcomes', { done: progress.outcomesProven, total: progress.outcomesTotal })}
          </Typography>
          <LinearProgress
            variant="determinate"
            value={outcomesPct}
            aria-hidden="true"
            sx={{ flex: 1, height: 5, borderRadius: 3, minWidth: 60 }}
          />
        </Stack>
      )}

      {showRolePrompt && (
        <Box sx={{ mt: 1.25, pt: 1, borderTop: '1px solid', borderColor: 'divider' }} data-testid="journey-role-prompt">
          <Typography sx={FONT.cardTitle}>{t('scenario.roleTitle')}</Typography>
          <Typography sx={{ ...FONT.caption, color: 'text.secondary', mt: 0.25 }}>{t('scenario.roleBody')}</Typography>
          <Stack direction="row" spacing={0.75} flexWrap="wrap" sx={{ mt: 0.75 }}>
            {ROLES.map((option) => (
              <Button
                key={option.track}
                size="small"
                variant="outlined"
                onClick={() => onRoleChange(option.track)}
                data-testid={`journey-role-${option.track}`}
                sx={{ textTransform: 'none' }}
              >
                {t(option.key)}
              </Button>
            ))}
          </Stack>
        </Box>
      )}
    </Box>
  );
}

JourneyScenario.propTypes = {
  journey: PropTypes.shape({ stages: PropTypes.arrayOf(PropTypes.shape({})), glossary: PropTypes.arrayOf(PropTypes.string) }),
  station: PropTypes.shape({}),
  role: PropTypes.string,
  compact: PropTypes.bool,
  onOpenLesson: PropTypes.func.isRequired,
  showRolePrompt: PropTypes.bool,
  onRoleChange: PropTypes.func,
};

JourneyScenario.defaultProps = {
  journey: null,
  station: null,
  role: '',
  compact: false,
  showRolePrompt: false,
  onRoleChange: undefined,
};
