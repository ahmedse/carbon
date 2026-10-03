import React from 'react';
import PropTypes from 'prop-types';
import { Box, Button, Typography } from '@mui/material';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import { alpha } from '@mui/material/styles';
import { useTranslation } from 'react-i18next';

import { FONT } from '../../theme/themeTokens';
import MixedText from './MixedText';
import { routeLabel } from './journeyStages';

// One hue per node, rotating, so a lesson reads as a bright sequence of beads
// rather than a grey list. Every tone is a real MUI palette slot.
const TONES = ['primary', 'info', 'secondary', 'success', 'warning'];
const toneAt = (index) => TONES[index % TONES.length];

/**
 * A lesson as a vertical timeline of step nodes. Each node is one step with a
 * title, an imperative "exactly what to do" line and a button that opens the
 * real host page for that step. No fabricated numbers appear here.
 *
 * The lesson reader owns which node is active: `activeIndex` highlights it and
 * `onSelectStep` (optional) turns the node marker into a button the reader can
 * focus a step with. Without those props this is a plain read-only timeline.
 *
 * Candy: a coloured, gradient-connected rail, numbered beads per hue, a subtle
 * tint on reached nodes and a glowing card on the active step.
 */
export default function LessonStepTimeline({
  steps, glossary, onGo, activeIndex, onSelectStep,
}) {
  const { t } = useTranslation('journey');
  const rows = Array.isArray(steps) ? steps : [];
  if (rows.length === 0) {
    return (
      <Typography sx={{ ...FONT.bodySmall, color: 'text.secondary', mt: 1 }} data-testid="lesson-no-steps">
        {t('lesson.noSteps')}
      </Typography>
    );
  }

  return (
    <Box data-testid="lesson-steps" sx={{ mt: 1.5 }}>
      {rows.map((step, index) => {
        const last = index === rows.length - 1;
        const active = activeIndex === index;
        const visited = activeIndex != null && index < activeIndex;
        const reached = active || visited;
        const tone = toneAt(index);
        const nextTone = toneAt(index + 1);

        const marker = (
          <Box
            aria-hidden={!onSelectStep}
            sx={{
              width: 28,
              height: 28,
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 700,
              fontSize: 13,
              lineHeight: 1,
              zIndex: 1,
              transition: 'transform 120ms ease, box-shadow 120ms ease',
              bgcolor: reached ? `${tone}.main` : 'background.paper',
              color: reached ? 'common.white' : `${tone}.main`,
              border: '2px solid',
              borderColor: reached ? `${tone}.main` : (theme) => alpha(theme.palette[tone].main, 0.45),
              boxShadow: active
                ? (theme) => `0 0 0 4px ${alpha(theme.palette[tone].main, 0.18)}`
                : 'none',
              transform: active ? 'scale(1.12)' : 'none',
            }}
          >
            {index + 1}
          </Box>
        );

        return (
          <Box
            key={`${step.title}-${index}`}
            data-testid={`lesson-step-${index}`}
            data-active={active ? 'true' : 'false'}
            data-tone={tone}
            sx={{ display: 'flex', gap: 1.5, position: 'relative', pb: last ? 0 : 2 }}
          >
            <Box sx={{ position: 'relative', flexShrink: 0, width: 28, display: 'flex', justifyContent: 'center' }}>
              {onSelectStep ? (
                <Box
                  component="button"
                  type="button"
                  aria-label={t('step.focus', { n: index + 1 })}
                  aria-pressed={active}
                  data-testid={`lesson-step-focus-${index}`}
                  onClick={() => onSelectStep(index)}
                  sx={{
                    p: 0,
                    mt: '1px',
                    border: 0,
                    bgcolor: 'transparent',
                    cursor: 'pointer',
                    borderRadius: '50%',
                    '&:focus-visible': { outline: '2px solid', outlineColor: `${tone}.main`, outlineOffset: 3 },
                  }}
                >
                  {marker}
                </Box>
              ) : marker}
              {!last && (
                <Box
                  aria-hidden="true"
                  sx={{
                    position: 'absolute',
                    top: 30,
                    bottom: -8,
                    width: 3,
                    borderRadius: 3,
                    opacity: reached ? 0.9 : 0.4,
                    background: (theme) => `linear-gradient(180deg, ${theme.palette[tone].main} 0%, ${theme.palette[nextTone].main} 100%)`,
                  }}
                />
              )}
            </Box>

            <Box
              sx={{
                flex: 1,
                minWidth: 0,
                mt: '-2px',
                p: 1,
                borderRadius: 2,
                border: '1px solid',
                borderColor: active
                  ? (theme) => alpha(theme.palette[tone].main, 0.35)
                  : 'transparent',
                bgcolor: active
                  ? (theme) => alpha(theme.palette[tone].main, 0.055)
                  : 'transparent',
              }}
            >
              <Typography
                component="span"
                sx={{
                  ...FONT.caption,
                  fontWeight: 700,
                  color: `${tone}.main`,
                  bgcolor: (theme) => alpha(theme.palette[tone].main, 0.12),
                  borderRadius: 999,
                  px: 0.75,
                  py: 0.125,
                  display: 'inline-block',
                }}
              >
                {t('step.stepOf', { n: index + 1, total: rows.length })}
              </Typography>
              <MixedText text={step.title} glossary={glossary} component="div" sx={{ ...FONT.cardTitle, mt: 0.25 }} />
              {step.do && (
                <MixedText
                  text={step.do}
                  glossary={glossary}
                  component="div"
                  sx={{ ...FONT.bodySmall, color: 'text.secondary', mt: 0.25 }}
                />
              )}
              {step.route && (
                <Button
                  size="small"
                  variant="outlined"
                  color={tone}
                  startIcon={<OpenInNewIcon sx={{ fontSize: 14 }} />}
                  sx={{ mt: 0.75, textTransform: 'none', borderRadius: 999 }}
                  onClick={() => onGo(step.route)}
                >
                  {t('step.goTo', { page: routeLabel(step.route) })}
                </Button>
              )}
            </Box>
          </Box>
        );
      })}
    </Box>
  );
}

LessonStepTimeline.propTypes = {
  steps: PropTypes.arrayOf(PropTypes.shape({
    title: PropTypes.string,
    do: PropTypes.string,
    route: PropTypes.string,
    target: PropTypes.string,
  })),
  glossary: PropTypes.arrayOf(PropTypes.string),
  onGo: PropTypes.func.isRequired,
  activeIndex: PropTypes.number,
  onSelectStep: PropTypes.func,
};

LessonStepTimeline.defaultProps = {
  steps: [], glossary: [], activeIndex: null, onSelectStep: undefined,
};
