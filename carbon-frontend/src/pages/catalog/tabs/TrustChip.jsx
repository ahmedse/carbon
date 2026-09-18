// TrustChip — Data Trust Index badge (ADR-0039).
// One consumer-facing score; do not invent a second quality ring.
// Pass score/tier from AssetProfile payloads, or tableId to fetch the table profile.
import React, { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import { Chip, Tooltip } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../../auth/AuthContext';
import { fetchTableAssetProfile } from '../../../api/catalog';

const TIER_COLOR = {
  trusted: 'success',
  limited: 'warning',
  untrustworthy: 'error',
};

function unwrap(data) {
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.results)) return data.results;
  return [];
}

/**
 * @param {object} props
 * @param {number|null|undefined} props.score — 0–100 trust_index
 * @param {string|null|undefined} props.tier — trusted | limited | untrustworthy
 * @param {object} [props.breakdown] — optional explainability for tooltip
 * @param {string|number} [props.tableId] — fetch table AssetProfile when score not provided
 * @param {'small'|'medium'} [props.size]
 */
export default function TrustChip({ score, tier, breakdown, tableId, size = 'small' }) {
  const { t } = useTranslation('catalog');
  const { token } = useAuth();
  const [fetched, setFetched] = useState(null);

  useEffect(() => {
    let cancelled = false;
    if (score != null || !tableId || !token) {
      setFetched(null);
      return undefined;
    }
    fetchTableAssetProfile(token, tableId)
      .then((data) => {
        if (cancelled) return;
        const tableAsset = unwrap(data).find((a) => !a.data_field) || null;
        setFetched(tableAsset);
      })
      .catch(() => {
        if (!cancelled) setFetched(null);
      });
    return () => { cancelled = true; };
  }, [score, tableId, token]);

  const resolvedScore = score != null ? score : fetched?.trust_index;
  const resolvedTier = tier || fetched?.trust_tier || (
    resolvedScore == null ? null
      : resolvedScore >= 70 ? 'trusted'
        : resolvedScore >= 20 ? 'limited' : 'untrustworthy'
  );
  const resolvedBreakdown = breakdown || fetched?.trust_breakdown;

  if (resolvedScore == null && !resolvedTier) return null;

  const color = TIER_COLOR[resolvedTier] || 'default';
  const tierLabel = t(`trustTier.${resolvedTier}`, { defaultValue: resolvedTier });
  const label = resolvedScore != null
    ? `${t('trustIndex')} ${resolvedScore} · ${tierLabel}`
    : tierLabel;

  let title = label;
  if (resolvedBreakdown) {
    const q = resolvedBreakdown.quality?.points ?? '—';
    const o = resolvedBreakdown.ownership?.points ?? '—';
    const c = resolvedBreakdown.context?.points ?? '—';
    const f = resolvedBreakdown.freshness?.points ?? '—';
    const fStatus = resolvedBreakdown.freshness?.status;
    title = t('trustBreakdownHint', {
      quality: q,
      ownership: o,
      context: c,
      freshness: f,
      freshnessStatus: fStatus || '—',
      defaultValue: `Quality ${q}/35 · Ownership ${o}/20 · Context ${c}/35 · Freshness ${f}/10`,
    });
  }

  return (
    <Tooltip title={title}>
      <Chip size={size} color={color} label={label} variant="outlined" />
    </Tooltip>
  );
}

TrustChip.propTypes = {
  score: PropTypes.number,
  tier: PropTypes.string,
  breakdown: PropTypes.object,
  tableId: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  size: PropTypes.oneOf(['small', 'medium']),
};
