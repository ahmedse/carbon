import React, { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert, Box, Button, Chip, FormControlLabel, Radio, RadioGroup, Stack, Typography,
} from '@mui/material';
import TheatersIcon from '@mui/icons-material/Theaters';
import { useTranslation } from 'react-i18next';

import { FONT } from '../../theme/themeTokens';
import MixedText from './MixedText';

/**
 * The camp drama: the station's staged scene, played one beat at a time.
 *
 * This is teaching, not a gate. The pack writes the scene as a line spoken by
 * the camp's role, one question, and the honest answer's reasoning. The server
 * grades the move; a drama answer writes `GuideScenario` only, so clearing a
 * scene can never mark a lesson or a station done. The next beat appears only
 * after the caller has read why the last one mattered.
 *
 * The correct index never reaches the browser — the caller has to reason from
 * the line, exactly like the field work the scene is about.
 */
export default function CampDrama({ station, glossary, onAnswer }) {
  const { t } = useTranslation('journey');
  const beats = station?.scenario?.beats || [];
  const walked = station?.scenarioBeat || 0;
  const total = beats.length;

  const [choice, setChoice] = useState(null);
  const [phase, setPhase] = useState('idle');
  const [wrong, setWrong] = useState(false);
  // The beat just cleared, held on screen with its reasoning until the caller
  // chooses to move on. Held locally so the parent's reload cannot wipe it.
  const [cleared, setCleared] = useState(null);

  const stationKey = station?.key || '';
  useEffect(() => {
    setChoice(null);
    setPhase('idle');
    setWrong(false);
    setCleared(null);
  }, [stationKey]);

  if (total === 0) return null;

  const done = walked >= total;
  const beat = cleared || (done ? null : beats[walked]);

  const submit = async () => {
    if (choice === null || !beat) return;
    setPhase('sending');
    setWrong(false);
    try {
      const out = await onAnswer(walked, choice);
      setPhase('idle');
      if (out?.correct) setCleared(beat);
      // A stale replay (the server already moved on) is not a wrong answer.
      else if (out?.correct === false) setWrong(true);
    } catch {
      setPhase('failed');
    }
  };

  return (
    <Box
      data-testid="journey-drama"
      data-done={done ? 'true' : 'false'}
      sx={{
        mt: 1.5,
        p: 1.25,
        borderRadius: 1,
        border: '1px dashed',
        borderColor: 'divider',
        bgcolor: 'action.hover',
      }}
    >
      <Stack direction="row" spacing={0.75} alignItems="center" flexWrap="wrap">
        <TheatersIcon sx={{ fontSize: 18, color: 'primary.main' }} aria-hidden="true" />
        <Typography sx={FONT.cardTitle}>{t('drama.title', { n: station?.n ?? '' })}</Typography>
        <Chip
          size="small"
          variant="outlined"
          label={t('drama.progress', { n: walked, total })}
          sx={FONT.chip}
          data-testid="journey-drama-pips"
        />
      </Stack>

      <Stack direction="row" spacing={0.5} sx={{ mt: 0.75 }} aria-hidden="true">
        {beats.map((row, index) => (
          <Box
            key={row.id || index}
            sx={{
              width: 22,
              height: 6,
              borderRadius: 3,
              bgcolor: index < walked ? 'primary.main' : 'divider',
            }}
          />
        ))}
      </Stack>

      {done && !cleared && (
        <Box sx={{ mt: 1 }} data-testid="journey-drama-done">
          <Typography sx={FONT.cardTitle} color="success.main">{t('drama.done')}</Typography>
          <Typography sx={{ ...FONT.bodySmall, color: 'text.secondary', mt: 0.25 }}>
            {t('drama.doneBody')}
          </Typography>
        </Box>
      )}

      {beat && (
        <Box sx={{ mt: 1 }}>
          {beat.cast && (
            <Typography sx={FONT.sectionTitle} color="text.secondary" data-testid="journey-drama-cast">
              {t('drama.cast', { name: beat.cast })}
            </Typography>
          )}
          {beat.line && (
            <MixedText
              text={beat.line}
              glossary={glossary}
              component="p"
              sx={{ ...FONT.body2, fontStyle: 'italic', m: 0, mt: 0.25 }}
              testId="journey-drama-line"
            />
          )}

          {!cleared && (
            <>
              <MixedText
                text={beat.question}
                glossary={glossary}
                component="p"
                sx={{ ...FONT.body2, mt: 0.75, mb: 0 }}
                testId="journey-drama-question"
              />
              <RadioGroup
                name={`journey-drama-${stationKey}-${walked}`}
                value={choice}
                onChange={(event) => setChoice(Number(event.target.value))}
                sx={{ mt: 0.25 }}
              >
                {(beat.choices || []).map((option, index) => (
                  <FormControlLabel
                    key={option}
                    value={index}
                    control={<Radio size="small" />}
                    disabled={phase === 'sending'}
                    data-testid={`journey-drama-option-${index}`}
                    label={<MixedText text={option} glossary={glossary} sx={FONT.bodySmall} />}
                  />
                ))}
              </RadioGroup>

              <Button
                size="small"
                variant="contained"
                disabled={choice === null || phase === 'sending'}
                onClick={submit}
                data-testid="journey-drama-check"
                sx={{ mt: 0.5, textTransform: 'none' }}
              >
                {t('drama.check')}
              </Button>

              {wrong && (
                <Alert severity="warning" sx={{ mt: 0.75 }} data-testid="journey-drama-wrong">
                  {t('drama.wrong')}
                </Alert>
              )}

              {phase === 'failed' && (
                <Alert severity="error" sx={{ mt: 0.75 }} data-testid="journey-drama-failed">
                  {t('drama.failed')}
                </Alert>
              )}
            </>
          )}

          {cleared && (
            <Box sx={{ mt: 0.75 }} data-testid="journey-drama-right" role="status">
              <Typography sx={FONT.sectionTitle} color="success.main">{t('drama.right')}</Typography>
              <Typography sx={{ ...FONT.sectionTitle, mt: 0.5 }} color="text.secondary">
                {t('drama.explain')}
              </Typography>
              <MixedText
                text={cleared.explain}
                glossary={glossary}
                component="p"
                sx={{ ...FONT.bodySmall, color: 'text.secondary', m: 0 }}
                testId="journey-drama-explain"
              />
              <Button
                size="small"
                variant="outlined"
                onClick={() => { setCleared(null); setChoice(null); setWrong(false); }}
                data-testid="journey-drama-next"
                sx={{ mt: 0.75, textTransform: 'none' }}
              >
                {walked >= total ? t('drama.done') : t('drama.next')}
              </Button>
            </Box>
          )}
        </Box>
      )}
    </Box>
  );
}

CampDrama.propTypes = {
  station: PropTypes.shape({
    n: PropTypes.number,
    key: PropTypes.string,
    scenarioBeat: PropTypes.number,
    scenario: PropTypes.shape({
      beats: PropTypes.arrayOf(PropTypes.shape({
        id: PropTypes.string,
        cast: PropTypes.string,
        line: PropTypes.string,
        question: PropTypes.string,
        choices: PropTypes.arrayOf(PropTypes.string),
        explain: PropTypes.string,
      })),
    }),
  }),
  glossary: PropTypes.arrayOf(PropTypes.string),
  onAnswer: PropTypes.func.isRequired,
};

CampDrama.defaultProps = { station: null, glossary: [] };
