import React, { useCallback, useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert, Box, Button, FormControlLabel, Radio, RadioGroup, Stack, Step, StepLabel, Stepper, Typography,
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { useAuth } from '../../auth/AuthContext';
import { fetchGuideLesson, postGuideEvent } from '../../api/guide';
import { FONT } from '../../theme/themeTokens';
import LoadingSkeleton from '../Page/LoadingSkeleton';
import ErrorAlert from '../Page/ErrorAlert';

const STEPS = ['know', 'do', 'check', 'after'];

/**
 * One lesson in four cards: Know, Do, Check, After.
 * The text comes from the pack; the server decides right or wrong and whether the host check holds.
 */
export default function LessonCoach({ appId, lessonId, lang, onChanged, onNext, onExit }) {
  const { t } = useTranslation('guide');
  const { token } = useAuth();
  const navigate = useNavigate();
  const [phase, setPhase] = useState('loading');
  const [lesson, setLesson] = useState(null);
  const [step, setStep] = useState(0);
  const [choice, setChoice] = useState(null);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const body = await fetchGuideLesson(appId, lessonId, { lang, token });
      setLesson(body);
      if (Number.isInteger(body?.step)) {
        setStep(Math.max(0, Math.min(STEPS.length - 1, body.step)));
      }
      if (body?.state === 'done') {
        setResult({ correct: true, state: 'done', waiting: null });
      }
      setPhase('loaded');
    } catch {
      setPhase('error');
    }
  }, [appId, lessonId, lang, token]);

  useEffect(() => {
    setChoice(null);
    setResult(null);
    setPhase('loading');
    load();
  }, [load]);

  const goTo = useCallback((nextStep) => {
    const clamped = Math.max(0, Math.min(STEPS.length - 1, nextStep));
    setStep(clamped);
    postGuideEvent(appId, lessonId, { event: 'opened', step: clamped }, token).catch(() => {});
  }, [appId, lessonId, token]);

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

  useEffect(() => {
    if (phase === 'loaded' && lesson && lesson.state === 'offered') {
      // Opening a lesson starts it. This is the only write a read of the card makes.
      postGuideEvent(appId, lessonId, { event: 'started' }, token).then(() => onChanged && onChanged({})).catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, lessonId]);

  if (phase === 'loading') return <LoadingSkeleton variant="card" />;
  if (phase === 'error' || !lesson) {
    return <ErrorAlert message={t('coach.loadFailed')} onRetry={load} />;
  }

  const copy = lesson.copy || {};
  const done = lesson.state === 'done';
  const waiting = result?.waiting === 'host' || (lesson.state === 'started' && lesson.host_required && result?.correct);
  const blocker = lesson.blocker;

  return (
    <Box data-testid="guide-coach" sx={{ border: 1, borderColor: 'divider', borderRadius: 1.5, p: 2, bgcolor: 'background.paper' }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
        <Typography component="h2" sx={FONT.heading}>{copy.title}</Typography>
        <Typography sx={{ ...FONT.caption, color: 'text.secondary' }}>{t('coach.minutes', { count: lesson.minutes })}</Typography>
      </Stack>
      <Stepper activeStep={step} alternativeLabel sx={{ mb: 2 }}>
        {STEPS.map((key, index) => (
          <Step key={key} completed={done || index < step}>
            <StepLabel onClick={() => goTo(index)} sx={{ cursor: 'pointer' }}>{t(`coach.step.${key}`)}</StepLabel>
          </Step>
        ))}
      </Stepper>

      {blocker && (
        <Alert
          severity="warning"
          sx={{ mb: 1.5 }}
          action={blocker.path ? (
            <Button color="inherit" size="small" onClick={() => navigate(blocker.path)}>{t('coach.fix')}</Button>
          ) : null}
        >
          <strong>{blocker.title || blocker.code}</strong>
          {blocker.body ? ` ${blocker.body}` : ''}
        </Alert>
      )}

      {step === 0 && <Typography sx={FONT.body2}>{copy.know}</Typography>}

      {step === 1 && (
        <Stack spacing={1.5}>
          <Typography sx={FONT.body2}>{copy.do}</Typography>
          <Alert severity="info" icon={false} sx={{ py: 0 }}>
            <Typography sx={FONT.bodySmall}><strong>{t('coach.dont')}</strong> {copy.dont}</Typography>
          </Alert>
          {lesson.route && (
            <Box>
              <Button size="small" variant="outlined" onClick={() => navigate(lesson.route)}>{t('coach.openScreen')}</Button>
            </Box>
          )}
        </Stack>
      )}

      {step === 2 && (
        <Stack spacing={1.5}>
          <Typography sx={FONT.body2}>{copy.question}</Typography>
          <RadioGroup value={choice ?? ''} onChange={(event) => setChoice(Number(event.target.value))}>
            {(copy.options || []).map((label, index) => (
              <FormControlLabel key={label} value={index} control={<Radio size="small" />} label={label} disabled={done} />
            ))}
          </RadioGroup>
          <Box>
            <Button
              variant="contained"
              size="small"
              disabled={choice == null || busy || done}
              onClick={() => send({ event: 'answered', choice })}
            >
              {t('coach.submit')}
            </Button>
          </Box>
          {result?.correct === false && <Alert severity="error">{t('coach.wrong')}</Alert>}
          {(result?.correct || done) && <Alert severity="success">{copy.explain}</Alert>}
          {waiting && !done && (
            <Alert
              severity="info"
              action={<Button color="inherit" size="small" disabled={busy} onClick={() => send({ event: 'check' })}>{t('coach.checkAgain')}</Button>}
            >
              {t('coach.waitingHost')}
            </Alert>
          )}
        </Stack>
      )}

      {step === 3 && (
        <Stack spacing={1.5}>
          <Alert severity={done ? 'success' : 'info'}>{done ? t('coach.done') : t('coach.notDone')}</Alert>
          <Stack direction="row" spacing={1}>
            {onNext && <Button variant="contained" size="small" onClick={onNext}>{t('coach.next')}</Button>}
            <Button size="small" onClick={onExit}>{t('coach.backToHub')}</Button>
          </Stack>
        </Stack>
      )}

      <Stack direction="row" justifyContent="space-between" sx={{ mt: 2 }}>
        <Button size="small" disabled={step === 0} onClick={() => goTo(step - 1)}>{t('coach.back')}</Button>
        {step < STEPS.length - 1 && (
          <Button size="small" variant="outlined" onClick={() => goTo(step + 1)}>{t('coach.continue')}</Button>
        )}
      </Stack>
    </Box>
  );
}

LessonCoach.propTypes = {
  appId: PropTypes.string.isRequired,
  lessonId: PropTypes.string.isRequired,
  lang: PropTypes.string,
  onChanged: PropTypes.func,
  onNext: PropTypes.func,
  onExit: PropTypes.func,
};

LessonCoach.defaultProps = { lang: 'en', onChanged: undefined, onNext: undefined, onExit: undefined };
