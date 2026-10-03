import React, { useCallback, useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert, Box, Button, FormControlLabel, Radio, RadioGroup, Typography,
} from '@mui/material';
import { alpha } from '@mui/material/styles';
import MenuBookRoundedIcon from '@mui/icons-material/MenuBookRounded';
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded';
import QuizRoundedIcon from '@mui/icons-material/QuizRounded';
import StickyNote2RoundedIcon from '@mui/icons-material/StickyNote2Rounded';
import { useTranslation } from 'react-i18next';

import { FONT } from '../../theme/themeTokens';
import { useAuth } from '../../auth/AuthContext';
import { fetchGuideLesson, postGuideEvent } from '../../api/guide';
import MixedText from './MixedText';

const ICON_BOX = {
  width: 26,
  height: 26,
  borderRadius: '8px',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  flexShrink: 0,
};

/**
 * One tinted mission card — a candy-coloured header (icon + label) over its
 * copy, so briefing, check and field note each read as a distinct beat of the
 * loop instead of grey blocks of prose.
 */
function MissionSection({
  testId, tone, icon: Icon, label, children,
}) {
  return (
    <Box
      data-testid={testId}
      sx={{
        mt: 1.25,
        p: 1.25,
        borderRadius: 2.5,
        border: '1px solid',
        borderColor: (theme) => alpha(theme.palette[tone].main, 0.28),
        bgcolor: (theme) => alpha(theme.palette[tone].main, 0.045),
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
        <Box
          aria-hidden="true"
          sx={{
            ...ICON_BOX,
            bgcolor: (theme) => alpha(theme.palette[tone].main, 0.16),
            color: `${tone}.main`,
          }}
        >
          <Icon sx={{ fontSize: 16 }} />
        </Box>
        <Typography sx={{ ...FONT.sectionTitle, color: `${tone}.main` }}>
          {label}
        </Typography>
      </Box>
      <Box sx={{ mt: 0.5 }}>{children}</Box>
    </Box>
  );
}

MissionSection.propTypes = {
  testId: PropTypes.string.isRequired,
  tone: PropTypes.string.isRequired,
  icon: PropTypes.elementType.isRequired,
  label: PropTypes.string.isRequired,
  children: PropTypes.node,
};

MissionSection.defaultProps = { children: null };

/**
 * The lesson loop, in one mission: Briefing, Hazard, Field check, Field note.
 *
 * The pack's `know` / `dont` / `question` / `options` / `explain` live on the
 * lesson-detail endpoint, not on the journey listing. Without this fetch the
 * journey reader showed only step waypoints, so an answer-graded lesson could
 * never be finished from Journey. The server still grades every answer and
 * decides whether a host check holds; this component only renders the cards.
 *
 * Read honesty: a wrong answer explains, it does not fail the learner. A host
 * lesson waits for the real action. Nothing here awards progress — the engine's
 * GuideProgress write is the only state, and the parent reloads the listing.
 *
 * When the detail cannot be loaded the component renders nothing: the waypoint
 * timeline above stays readable rather than locking the lesson.
 */
export default function LessonMission({
  appId, lessonId, glossary, onChanged, compact,
}) {
  const { t } = useTranslation('journey');
  const { i18n } = useTranslation();
  const { token } = useAuth();
  const lang = i18n.language?.startsWith('ar') ? 'ar' : 'en';

  const [detail, setDetail] = useState(null);
  const [choice, setChoice] = useState(null);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const body = await fetchGuideLesson(appId, lessonId, { lang, token });
      setDetail(body && typeof body === 'object' ? body : null);
    } catch {
      // Degrade to the waypoint timeline only — never block the lesson.
      setDetail(null);
    }
  }, [appId, lessonId, lang, token]);

  useEffect(() => {
    setChoice(null);
    setResult(null);
    setDetail(null);
    load();
  }, [load]);

  const send = useCallback(async (body) => {
    setBusy(true);
    try {
      const out = await postGuideEvent(appId, lessonId, body, token);
      setResult(out);
      await load();
      if (onChanged) onChanged(out);
      return out;
    } finally {
      setBusy(false);
    }
  }, [appId, lessonId, token, load, onChanged]);

  if (!detail || !detail.copy) return null;

  const copy = detail.copy;
  const done = detail.state === 'done';
  const hostCheck = detail.question?.kind === 'host';
  const wrong = result?.correct === false && !done;
  const waiting = !done && !wrong
    && (result?.waiting === 'host' || (result?.correct === true && detail.host_required));
  const correct = !done && !wrong && !waiting && result?.correct === true;
  const answered = done || Boolean(result && result.correct != null);

  return (
    <Box
      data-testid="lesson-mission"
      data-compact={compact ? 'true' : 'false'}
      sx={{ mt: 1.5 }}
    >
      {copy.know && (
        <MissionSection
          testId="lesson-mission-briefing"
          tone="info"
          icon={MenuBookRoundedIcon}
          label={t('mission.briefing')}
        >
          <MixedText text={copy.know} glossary={glossary} component="p" sx={FONT.body2} />
        </MissionSection>
      )}

      {copy.dont && (
        <Box sx={{ mt: 1.25 }} data-testid="lesson-mission-hazard">
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 0.5 }}>
            <Box
              aria-hidden="true"
              sx={{
                ...ICON_BOX,
                bgcolor: (theme) => alpha(theme.palette.warning.main, 0.16),
                color: 'warning.main',
              }}
            >
              <WarningAmberRoundedIcon sx={{ fontSize: 16 }} />
            </Box>
            <Typography sx={{ ...FONT.sectionTitle, color: 'warning.main' }}>
              {t('mission.hazard')}
            </Typography>
          </Box>
          <Alert severity="warning" variant="outlined" sx={{ py: 0, borderRadius: 2.5 }}>
            <MixedText text={copy.dont} glossary={glossary} component="span" sx={FONT.bodySmall} />
          </Alert>
        </Box>
      )}

      {copy.question && (
        <MissionSection
          testId="lesson-mission-check"
          tone="secondary"
          icon={QuizRoundedIcon}
          label={t('mission.check')}
        >
          <MixedText text={copy.question} glossary={glossary} component="p" sx={FONT.body2} />

          {hostCheck ? (
            !waiting && (
              <Button
                size="small"
                variant="contained"
                disabled={busy}
                onClick={() => send({ event: 'check' })}
                data-testid="lesson-mission-check-row"
                sx={{ mt: 0.5, textTransform: 'none' }}
              >
                {done ? t('mission.checkAgain') : t('mission.checkRow')}
              </Button>
            )
          ) : (
            <>
              {/* Always answerable: a correct or finished answer never dims the
                  choices, so the learner can re-read and answer again. */}
              <RadioGroup
                value={choice ?? ''}
                onChange={(event) => setChoice(Number(event.target.value))}
                sx={{ mt: 0.5 }}
              >
                {(copy.options || []).map((label, index) => (
                  <FormControlLabel
                    key={label}
                    value={index}
                    control={<Radio size="small" />}
                    data-testid={`lesson-mission-option-${index}`}
                    label={<MixedText text={label} glossary={glossary} sx={FONT.bodySmall} />}
                  />
                ))}
              </RadioGroup>
              <Button
                size="small"
                variant={answered ? 'outlined' : 'contained'}
                disabled={choice == null || busy}
                onClick={() => send({ event: 'answered', choice })}
                data-testid="lesson-mission-submit"
                sx={{ mt: 0.5, textTransform: 'none' }}
              >
                {answered ? t('mission.answerAgain') : t('mission.submit')}
              </Button>
            </>
          )}

          {wrong && (
            <Alert severity="error" sx={{ mt: 0.75 }} data-testid="lesson-mission-wrong">
              {t('mission.wrong')}
            </Alert>
          )}
          {waiting && (
            <Alert
              severity="info"
              sx={{ mt: 0.75 }}
              data-testid="lesson-mission-waiting"
              action={hostCheck ? (
                <Button color="inherit" size="small" disabled={busy} onClick={() => send({ event: 'check' })}>
                  {t('mission.checkAgain')}
                </Button>
              ) : undefined}
            >
              {hostCheck ? t('mission.waitingRow') : t('mission.waitingHost')}
            </Alert>
          )}
          {correct && (
            <Alert severity="success" sx={{ mt: 0.75 }} data-testid="lesson-mission-done">
              {t('mission.done')}
            </Alert>
          )}
        </MissionSection>
      )}

      {done && copy.explain && (
        <MissionSection
          testId="lesson-mission-note"
          tone="success"
          icon={StickyNote2RoundedIcon}
          label={t('mission.fieldNote')}
        >
          <MixedText text={copy.explain} glossary={glossary} component="p" sx={{ ...FONT.bodySmall, color: 'text.secondary' }} />
        </MissionSection>
      )}
    </Box>
  );
}

LessonMission.propTypes = {
  appId: PropTypes.string.isRequired,
  lessonId: PropTypes.string.isRequired,
  glossary: PropTypes.arrayOf(PropTypes.string),
  onChanged: PropTypes.func,
  compact: PropTypes.bool,
};

LessonMission.defaultProps = {
  glossary: [], onChanged: undefined, compact: false,
};
