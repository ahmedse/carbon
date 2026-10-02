import React from 'react';
import PropTypes from 'prop-types';
import { Box, Button, Chip, Typography } from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import TimelapseIcon from '@mui/icons-material/Timelapse';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';
import MilitaryTechIcon from '@mui/icons-material/MilitaryTech';
import { useTranslation } from 'react-i18next';

import { FONT } from '../../theme/themeTokens';
import MixedText from './MixedText';

const STATUS = {
  done: { color: 'success', Icon: CheckCircleIcon, labelKey: 'completion.done' },
  inProgress: { color: 'primary', Icon: TimelapseIcon, labelKey: 'completion.inProgress' },
  todo: { color: 'default', Icon: RadioButtonUncheckedIcon, labelKey: 'completion.todo' },
};

/**
 * One checkable outcome. The pack supplies the outcome title and a plain-language
 * "what good looks like" line. An outcome is done only when the engine says its
 * lesson is done. The action goes to the real page the lesson lives on.
 */
export default function CompetencyOutcome({ competency, glossary, onGo }) {
  const { t } = useTranslation('journey');
  const meta = STATUS[competency.status] || STATUS.todo;
  const { Icon } = meta;
  const route = competency.lesson?.route;
  const canGo = Boolean(route && onGo);

  return (
    <Box
      data-testid={`journey-outcome-${competency.key}`}
      data-status={competency.status}
      sx={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: 1,
        py: 0.75,
        borderBottom: '1px solid',
        borderColor: 'divider',
      }}
    >
      <Icon sx={{ fontSize: '1rem', color: `${meta.color}.main`, flexShrink: 0, mt: '2px' }} />
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <MixedText text={competency.title} glossary={glossary} sx={FONT.body2} />
        {competency.good && (
          <Box sx={{ mt: 0.25 }}>
            <Typography component="span" sx={{ ...FONT.caption, color: 'text.secondary' }}>
              {t('sections.outcomes')}:{' '}
            </Typography>
            <MixedText
              text={competency.good}
              glossary={glossary}
              component="span"
              sx={{ ...FONT.caption, color: 'text.secondary' }}
            />
          </Box>
        )}
      </Box>
      {competency.status === 'done' ? (
        // A mastery badge is earned only when the engine proves the outcome —
        // a host probe pass or a correct answer, never a click.
        <Chip
          size="small"
          color="success"
          icon={<MilitaryTechIcon sx={{ fontSize: 14 }} />}
          data-testid={`journey-mastery-${competency.key}`}
          label={t('mastery.badge')}
          sx={FONT.chip}
        />
      ) : (
        <Chip
          size="small"
          color={meta.color}
          variant="outlined"
          label={t(meta.labelKey)}
          sx={FONT.chip}
        />
      )}
      {canGo && (
        <Button size="small" variant="text" onClick={() => onGo(route)}>
          {t('cta.goThere')}
        </Button>
      )}
    </Box>
  );
}

CompetencyOutcome.propTypes = {
  competency: PropTypes.shape({
    key: PropTypes.string.isRequired,
    title: PropTypes.string,
    good: PropTypes.string,
    status: PropTypes.string,
    lesson: PropTypes.shape({ route: PropTypes.string }),
  }).isRequired,
  glossary: PropTypes.arrayOf(PropTypes.string),
  onGo: PropTypes.func,
};

CompetencyOutcome.defaultProps = { glossary: [], onGo: undefined };
