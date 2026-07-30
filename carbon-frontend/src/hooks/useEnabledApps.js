// File: src/hooks/useEnabledApps.js
// Shared hook — fetches enabled platform apps from backend.
// Used by PlatformHome and ActivityBar to hide disabled apps.

import { useState, useEffect } from 'react';
import { API_BASE_URL } from '../config';

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
      }).catch((err) => {
        if (!cancelled) {
          setError(err.message);
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

    cachedPromise = fetch(`${API_BASE_URL.replace(/\/$/, '')}/accounts/platform-apps/`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    });

    let cancelled = false;
    cachedPromise.then((data) => {
      if (!cancelled) {
        cachedApps = data;
        setApps(data);
        setLoading(false);
      }
    }).catch((err) => {
      if (!cancelled) {
        // On error, fall back to showing all apps
        cachedPromise = null;
        setError(err.message);
        setLoading(false);
      }
    });

    return () => { cancelled = true; };
  }, []);

  /** Returns true if an app_id is enabled (defaults to true if not loaded yet). */
  const isAppEnabled = (appId) => {
    if (!cachedApps) return true; // not loaded yet → show all
    const config = cachedApps.find((a) => a.app_id === appId);
    return config ? config.is_enabled : true; // unknown apps are enabled by default
  };

  return { apps, loading, error, isAppEnabled };
}
