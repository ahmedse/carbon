import React from 'react';
import { Alert, Chip } from '@mui/material';
import { useTranslation } from 'react-i18next';
export function marketBasedFrom(payload) {
  return payload?.by_scope2_method?.market_based || payload?.market_based || payload?.stats?.by_scope2_method?.market_based;
}

export function isMarketBasedPresent(payload) {
  return Boolean(marketBasedFrom(payload)?.present);
}

export function scope2MethodLabel(method, t) {
  const raw = String(method ?? '').trim().toLowerCase().replace(/-/g, '_');
  if (raw === 'market_based') return t('scope2MarketBased');
  if (raw === 'location_based') return t('scope2LocationBased');
  return t('chairman.scope2Unlabelled');
}

export function Scope2MethodChip({ method, scope }) {
  const { t } = useTranslation('emissions');
  if (scope != null && Number(scope) !== 2) return null;
  return <Chip label={scope2MethodLabel(method, t)} size="small" variant="outlined" />;
}

export function MarketBasedAbsentAlert({ payload }) {
  const { t } = useTranslation('emissions');
  if (isMarketBasedPresent(payload)) return null;
  return (
    <Alert severity="info">
      {t('scope2MarketBasedAbsent')}
    </Alert>
  );
}

export default Scope2MethodChip;
