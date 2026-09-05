// File: src/hooks/useEnabledApps.js
// Shared hook — fetches enabled platform apps from backend.
// Used by PlatformHome and ActivityBar to hide disabled apps.

import { useState, useEffect } from 'react';
import { apiFetch } from '../api/api';

let cachedPromise = null;
let cachedApps = null;

export function useEnabledApps() {
  const [apps, setApps] = useState(cachedApps || []);
  const [loading, setLoading] = useState(!cachedApps);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (cachedApps) {
      setApps(cachedApps);
      setLoading(false);
      return;
    }

    if (cachedPromise) {
      let cancelled = false;
      cachedPromise.then((data) => {
        if (!cancelled) {
          cachedApps = data;
          setApps(data);
          setLoading(false);
        }
      }).catch((_err) => {
        if (!cancelled) {
          setLoading(false);
        }
      });
      return () => { cancelled = true; };
    }

    const token = localStorage.getItem('access');
    if (!token) {
      setLoading(false);
      return;
    }

    // Use apiFetch for JWT auto-refresh (was raw fetch → 401 on expired tokens)
    cachedPromise = apiFetch('/accounts/platform-apps/');

    let cancelled = false;
    cachedPromise.then((data) => {
      if (!cancelled) {
        cachedApps = data;
        setApps(data);
        setLoading(false);
      }
    }).catch((err) => {
      if (!cancelled) {
        // On error, keep the app list unknown → fail-closed (hide domain apps).
        // Never fall back to showing all apps: on a multi-brand instance that
        // would leak other brands' domain apps (ADR-0015).
        cachedPromise = null;
        setError(err.message);
        setLoading(false);
      }
    });

    return () => { cancelled = true; };
  }, []);

  /**
   * Returns true if an app_id is enabled.
   * FAIL-CLOSED: while the brand-scoped app list is still loading (or if the
   * fetch failed), returns false so unrelated domain apps are hidden — never
   * flashed — on a per-brand instance (ADR-0015).
   */
  const isAppEnabled = (appId) => {
    if (!cachedApps) return false; // not loaded yet → hide (fail-closed)
    const config = cachedApps.find((a) => a.app_id === appId);
    // Apps omitted by the brand-scoped endpoint are not installed for this
    // instance — hide them instead of defaulting to enabled.
    return config ? config.is_enabled : false;
  };

  return { apps, loading, error, isAppEnabled };
}
