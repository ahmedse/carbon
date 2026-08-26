// src/pages/catalog/tabs/FreshnessChip.jsx
// Read-only freshness chip (EPH-3B) surfaced in the schema-detail header.
// 404 (no FreshnessPolicy) → renders nothing; invalid timestamps → grey "unknown".
import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Chip } from '@mui/material';
import { useAuth } from '../../../auth/AuthContext';
import { getTableFreshness } from '../../../api/profiling';

// Relative-time helper (duplicated locally per the shared-pattern convention).
// Safe for SSR/tests: invalid/missing ISO resolves to the "na" translation.
function formatAge(iso, t) {
  if (!iso) return t('freshnessUnknown');
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return t('freshnessUnknown');
  const diffMs = Date.now() - date.getTime();
  if (diffMs < 60_000) return t('justNow');
  const minutes = Math.floor(diffMs / 60_000);
  if (minutes < 60) return t('minutesAgo', { count: minutes });
  const hours = Math.floor(minutes / 60);
  if (hours < 48) return t('hoursAgo', { count: hours });
  const days = Math.floor(hours / 24);
  return t('daysAgo', { count: days });
}

export default function FreshnessChip({ tableId }) {
  const { token } = useAuth();
  const { t } = useTranslation('catalog');
  const [policy, setPolicy] = useState(null);

  useEffect(() => {
    let cancelled = false;
    if (!tableId) return undefined;

    getTableFreshness(tableId, token)
      .then((data) => {
        if (!cancelled) setPolicy(data);
      })
      .catch(() => {
        // 404 (no policy) or any other error → hide the chip entirely.
        if (!cancelled) setPolicy(null);
      });

    return () => {
      cancelled = true;
    };
  }, [tableId, token]);

  if (!policy) return null;

  const lastUpdated = policy.last_data_updated_at;
  const date = lastUpdated ? new Date(lastUpdated) : null;
  const isValid = date && !Number.isNaN(date.getTime());
  const maxAgeHours = policy.max_age_hours;

  let color = 'default';
  let label = t('freshnessUnknown');

  if (isValid && maxAgeHours != null) {
    const ageHours = (Date.now() - date.getTime()) / 3_600_000;
    const ageLabel = formatAge(lastUpdated, t);
    if (ageHours <= maxAgeHours) {
      color = 'success';
      label = `${t('fresh')} · ${ageLabel}`;
    } else {
      color = 'warning';
      label = `${t('stale')} · ${ageLabel}`;
    }
  }

  return <Chip size="small" color={color} label={label} />;
}
