// src/pages/admin/ai/control/LegacyAiRedirect.jsx
// Redirect legacy /admin/ai/* panel URLs to Control Plane hubs (ADR-0036).
import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { LEGACY_REDIRECTS, legacyRedirectTo } from './pulseControlIa';

export default function LegacyAiRedirect() {
  const { pathname } = useLocation();
  const entry = LEGACY_REDIRECTS[pathname];
  return <Navigate to={legacyRedirectTo(entry)} replace />;
}
