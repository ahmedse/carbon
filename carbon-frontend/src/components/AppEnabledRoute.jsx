// File: src/components/AppEnabledRoute.jsx
// Brand/isolation route guard for domain-app routes that are NOT admin-gated.
//
// Gates on useEnabledApps()/isAppEnabled(appId) — the same FAIL-CLOSED,
// brand-scoped check the shell uses to hide app studios. While the app list is
// loading we render a spinner (never the page, never a redirect) so we don't
// flash disabled apps or bounce enabled-brand users on first paint (ADR-0015).
//
// Unlike AdminRoute (which gates on can(user, 'manage'|'access_route', ...)),
// this guard is for app routes that are open to any user of the app — e.g. the
// carbon chairman / console / dashboard pages — and must simply be hidden for
// brands where the app is not enabled (e.g. Nibras must never reach /carbon/*).

import React from 'react';
import { Navigate } from 'react-router-dom';
import { useEnabledApps } from '../hooks/useEnabledApps';
import { LoadingSpinner } from '../shell/LoadingFallback';

export default function AppEnabledRoute({ appId, children, redirectTo = '/' }) {
  const { loading, isAppEnabled } = useEnabledApps();

  // Fail-closed while the brand-scoped app list is still loading — never flash
  // the app page before we know whether it's enabled for this instance.
  if (loading) {
    return <LoadingSpinner />;
  }

  if (!isAppEnabled(appId)) {
    return <Navigate to={redirectTo} replace />;
  }

  return children;
}
