import React from 'react';
import PropTypes from 'prop-types';
import { Box, Button, Typography } from '@mui/material';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import { useTranslation } from 'react-i18next';

import { FONT } from '../../theme/themeTokens';
import MixedText from './MixedText';
import { routeLabel } from './journeyStages';

/**
 * A lesson as a vertical timeline of step nodes. Each node is one step with a
 * title, an imperative "exactly what to do" line and a button that opens the
 * real host page for that step. No fabricated numbers appear here.
 *
 * The lesson reader owns which node is active: `activeIndex` highlights it and
 * `onSelectStep` (optional) turns the node marker into a button the reader can
 * focus a step with. Without those props this is a plain read-only timeline.
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
    <Box data-testid="lesson-steps" sx={{ mt: 1 }}>
      {rows.map((step, index) => {
        const last = index === rows.length - 1;
        const active = activeIndex === index;
        return (
          <Box
            key={`${step.title}-${index}`}
            data-testid={`lesson-step-${index}`}
            data-active={active ? 'true' : 'false'}
            sx={{
              display: 'flex',
              gap: 1.5,
              position: 'relative',
              pb: last ? 0 : 2,
              borderRadius: 1,
              bgcolor: active ? 'action.hover' : 'transparent',
            }}
          >
            <Box sx={{ position: 'relative', flexShrink: 0, width: 16, display: 'flex', justifyContent: 'center' }}>
              {onSelectStep ? (
                <Box
                  component="button"
                  type="button"
                  aria-label={t('step.focus', { n: index + 1 })}
                  aria-pressed={active}
                  data-testid={`lesson-step-focus-${index}`}
                  onClick={() => onSelectStep(index)}
                  sx={{
                    mt: '3px',
                    zIndex: 1,
                    width: 12,
                    height: 12,
                    p: 0,
                    borderRadius: '50%',
                    border: 0,
                    cursor: 'pointer',
                    bgcolor: active ? 'primary.dark' : 'primary.main',
                    '&:focus-visible': { outline: '2px solid', outlineColor: 'primary.main', outlineOffset: 2 },
                  }}
                />
              ) : (
                <Box
                  sx={{
                    width: 12,
                    height: 12,
                    borderRadius: '50%',
                    bgcolor: 'primary.main',
                    color: 'primary.contrastText',
                    mt: '3px',
                    zIndex: 1,
                  }}
                />
              )}
              {!last && (
                <Box
                  aria-hidden="true"
                  sx={{ position: 'absolute', top: 14, bottom: -8, width: '2px', bgcolor: 'divider' }}
                />
              )}
            </Box>
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Typography sx={{ ...FONT.caption, color: 'text.secondary' }}>
                {t('step.stepOf', { n: index + 1, total: rows.length })}
              </Typography>
              <MixedText text={step.title} glossary={glossary} component="div" sx={FONT.cardTitle} />
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
                  startIcon={<OpenInNewIcon sx={{ fontSize: 14 }} />}
                  sx={{ mt: 0.75, textTransform: 'none' }}
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
