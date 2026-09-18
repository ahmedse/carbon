// TrustStewardshipNudge — explainable stewardship tips from Trust Index breakdown (ADR-0039).
// Status = severity chip/alert + label (RULE 5). Actionable missing ingredients only.
import React, { useMemo } from 'react';
import PropTypes from 'prop-types';
import { Alert, AlertTitle, Stack, Typography, Button } from '@mui/material';
import { useTranslation } from 'react-i18next';

/**
 * Build ordered list of missing trust ingredients from breakdown.
 */
export function missingTrustActions(breakdown, t) {
  if (!breakdown || typeof breakdown !== 'object') return [];
  const actions = [];
  const q = breakdown.quality || {};
  const o = breakdown.ownership || {};
  const c = breakdown.context || {};
  const f = breakdown.freshness || {};

  if (q.quality_score == null || q.points === 0) {
    actions.push(t('stewardship.needQuality', {
      defaultValue: 'Run DQ rules so a quality score is written back',
    }));
  }
  if (!o.owner) {
    actions.push(t('stewardship.needOwner', {
      defaultValue: 'Assign an owner (steward alone only scores half ownership)',
    }));
  }
  if (!c.description) {
    actions.push(t('stewardship.needDescription', { defaultValue: 'Add a description' }));
  }
  if (!c.glossary_term) {
    actions.push(t('stewardship.needGlossary', { defaultValue: 'Link a glossary term' }));
  }
  if (!c.domain) {
    actions.push(t('stewardship.needDomain', { defaultValue: 'Assign a domain' }));
  }
  if (!c.tags) {
    actions.push(t('stewardship.needTags', { defaultValue: 'Add at least one tag' }));
  }
  if (f.status === 'stale') {
    actions.push(t('stewardship.needFreshness', {
      defaultValue: 'Data is stale vs the freshness SLA — refresh the source',
    }));
  } else if (f.status === 'unknown') {
    actions.push(t('stewardship.needFreshnessPolicy', {
      defaultValue: 'Optional: enable a freshness policy to earn full freshness points',
    }));
  }
  return actions;
}

/**
 * @param {object} props
 * @param {string} [props.tier]
 * @param {number} [props.score]
 * @param {object} [props.breakdown]
 * @param {function} [props.onImprove] — optional CTA (e.g. scroll to edit / open governance)
 * @param {string} [props.improveLabel]
 */
export default function TrustStewardshipNudge({
  tier,
  score,
  breakdown,
  onImprove,
  improveLabel,
}) {
  const { t } = useTranslation('catalog');

  const actions = useMemo(
    () => missingTrustActions(breakdown, t),
    [breakdown, t],
  );

  if (!tier || tier === 'trusted') return null;
  if (actions.length === 0 && score == null) return null;

  const severity = tier === 'untrustworthy' ? 'error' : 'warning';
  const title = tier === 'untrustworthy'
    ? t('stewardship.untrustworthyTitle', { defaultValue: 'Untrustworthy — improve metadata & quality' })
    : t('stewardship.limitedTitle', { defaultValue: 'Limited trust — stewardship tips' });

  return (
    <Alert
      severity={severity}
      sx={{ mb: 2 }}
      action={onImprove ? (
        <Button color="inherit" size="small" onClick={onImprove}>
          {improveLabel || t('stewardship.improve', { defaultValue: 'Improve' })}
        </Button>
      ) : undefined}
    >
      <AlertTitle>{title}</AlertTitle>
      {score != null && (
        <Typography variant="body2" sx={{ mb: 1 }}>
          {t('stewardship.scoreLine', {
            score,
            tier: t(`trustTier.${tier}`, { defaultValue: tier }),
            defaultValue: `Trust Index ${score} (${tier})`,
          })}
        </Typography>
      )}
      {actions.length > 0 && (
        <Stack component="ul" spacing={0.5} sx={{ m: 0, pl: 2 }}>
          {actions.slice(0, 5).map((text) => (
            <Typography component="li" variant="body2" key={text}>
              {text}
            </Typography>
          ))}
        </Stack>
      )}
    </Alert>
  );
}

TrustStewardshipNudge.propTypes = {
  tier: PropTypes.string,
  score: PropTypes.number,
  breakdown: PropTypes.object,
  onImprove: PropTypes.func,
  improveLabel: PropTypes.string,
};
