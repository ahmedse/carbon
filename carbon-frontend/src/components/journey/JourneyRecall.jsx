import React, { useState } from 'react';
import PropTypes from 'prop-types';
import {
  Box, Button, FormControlLabel, Radio, RadioGroup, Stack, Typography,
} from '@mui/material';
import HistoryEduIcon from '@mui/icons-material/HistoryEdu';
import { useTranslation } from 'react-i18next';

import { FONT } from '../../theme/themeTokens';
import { useAuth } from '../../auth/AuthContext';
import { fetchGuideLesson } from '../../api/guide';
import MixedText from './MixedText';

/**
 * A spaced-review check-in: it resurfaces the question of an earlier lesson the
 * caller genuinely finished, lets them retrieve the answer, and then shows the
 * pack's own reasoning.
 *
 * Read-only by construction: the check only ever GETs the lesson. It never posts
 * an answer and never changes progress, so the copy says so plainly. It appears
 * only when journeyVoice.recallLesson maps to a real finished choice-graded
 * lesson; a host-graded lesson has no question to revisit and is skipped.
 */
export default function JourneyRecall({ appId, lesson, glossary }) {
  const { t } = useTranslation('journey');
  const { i18n } = useTranslation();
  const { token } = useAuth();
  const lang = i18n.language?.startsWith('ar') ? 'ar' : 'en';

  const [phase, setPhase] = useState('idle');
  const [detail, setDetail] = useState(null);
  const [choice, setChoice] = useState(null);

  if (!lesson) return null;

  const start = async () => {
    setPhase('loading');
    try {
      const body = await fetchGuideLesson(appId, lesson.id, { lang, token });
      const options = body?.copy?.options || [];
      if (!body?.copy?.question || options.length === 0) {
        setPhase('idle');
        return;
      }
      setDetail(body);
      setChoice(null);
      setPhase('ready');
    } catch {
      setDetail(null);
      setPhase('error');
    }
  };

  const options = detail?.copy?.options || [];

  return (
    <Box
      data-testid="journey-recall"
      sx={{ mt: 1.5, pt: 1, borderTop: '1px solid', borderColor: 'divider' }}
    >
      <Stack direction="row" spacing={0.75} alignItems="center">
        <HistoryEduIcon sx={{ fontSize: 16, color: 'text.secondary' }} aria-hidden="true" />
        <Typography sx={FONT.cardTitle}>{t('recall.title')}</Typography>
      </Stack>
      <Typography sx={{ ...FONT.caption, color: 'text.secondary', mt: 0.25 }}>
        {t('recall.body', { lesson: lesson.title })}
      </Typography>

      {phase === 'idle' && (
        <Button
          size="small"
          variant="outlined"
          onClick={start}
          data-testid="journey-recall-start"
          sx={{ mt: 0.75, textTransform: 'none' }}
        >
          {t('recall.start')}
        </Button>
      )}

      {phase === 'loading' && (
        <Typography sx={{ ...FONT.bodySmall, color: 'text.secondary', mt: 0.75 }}>{t('recall.loading')}</Typography>
      )}

      {phase === 'error' && (
        <Typography sx={{ ...FONT.bodySmall, color: 'text.secondary', mt: 0.75 }}>{t('recall.failed')}</Typography>
      )}

      {phase !== 'idle' && phase !== 'loading' && phase !== 'error' && detail && (
        <Box sx={{ mt: 0.75 }}>
          <MixedText
            text={detail.copy.question}
            glossary={glossary}
            component="p"
            sx={{ ...FONT.body2, m: 0 }}
          />
          <RadioGroup
            name={`journey-recall-${lesson.id}`}
            value={choice}
            onChange={(event) => setChoice(Number(event.target.value))}
            sx={{ mt: 0.5 }}
          >
            {options.map((option, index) => (
              <FormControlLabel
                key={option}
                value={index}
                control={<Radio size="small" />}
                disabled={phase === 'revealed'}
                data-testid={`journey-recall-option-${index}`}
                label={<MixedText text={option} glossary={glossary} sx={FONT.bodySmall} />}
              />
            ))}
          </RadioGroup>

          {phase === 'ready' && (
            <Button
              size="small"
              variant="contained"
              disabled={choice === null}
              onClick={() => setPhase('revealed')}
              data-testid="journey-recall-reveal"
              sx={{ mt: 0.5, textTransform: 'none' }}
            >
              {t('recall.reveal')}
            </Button>
          )}

          {phase === 'revealed' && (
            <Box sx={{ mt: 0.75 }} data-testid="journey-recall-reasoning">
              <Typography sx={FONT.sectionTitle} color="text.secondary">{t('recall.reasoning')}</Typography>
              <MixedText
                text={detail.copy.explain}
                glossary={glossary}
                component="p"
                sx={{ ...FONT.bodySmall, color: 'text.secondary', m: 0 }}
              />
              <Typography sx={{ ...FONT.caption, color: 'text.secondary', mt: 0.5 }}>
                {t('recall.unchanged')}
              </Typography>
            </Box>
          )}
        </Box>
      )}
    </Box>
  );
}

JourneyRecall.propTypes = {
  appId: PropTypes.string.isRequired,
  lesson: PropTypes.shape({
    id: PropTypes.string.isRequired,
    title: PropTypes.string,
  }),
  glossary: PropTypes.arrayOf(PropTypes.string),
};

JourneyRecall.defaultProps = { lesson: null, glossary: [] };
