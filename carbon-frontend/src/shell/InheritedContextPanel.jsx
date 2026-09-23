// PV2-5C — outcome-facing Chat details carried into Agent (RULE_23).
import React, { useMemo } from 'react';
import PropTypes from 'prop-types';
import { Box, Chip, Stack, Typography } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { inheritedContextItems } from './activePlans';

function InheritedContextPanel({ plan }) {
  const { t } = useTranslation('ai');
  const items = useMemo(() => inheritedContextItems(plan), [plan]);
  if (!items.length) return null;
  return (
    <Box
      data-testid="agent-run-inherited-context"
      sx={{
        px: 0.75,
        py: 0.5,
        border: 1,
        borderColor: 'divider',
        borderRadius: 1,
        bgcolor: 'background.paper',
      }}
    >
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{ fontSize: '0.625rem', fontWeight: 600, letterSpacing: '0.03em' }}
      >
        {t('continuity.inheritedTitle')}
      </Typography>
      <Stack direction="row" spacing={0.5} useFlexGap flexWrap="wrap" sx={{ mt: 0.5 }}>
        {items.map((item) => (
          <Chip
            key={item.key}
            size="small"
            variant="outlined"
            label={`${t(`inherited.${item.key}`, item.key)} · ${item.value}`}
            sx={{ height: 20, fontSize: '0.625rem' }}
          />
        ))}
      </Stack>
    </Box>
  );
}

InheritedContextPanel.propTypes = {
  plan: PropTypes.object,
};

export default InheritedContextPanel;
