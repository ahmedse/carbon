// src/hooks/useReferenceOptions.js
// Fetch a governed enum (mdm.ReferenceSet) as { value: code, label } options
// for an Autocomplete/select — the replacement for free-text enum fields.
// Returns the four data states (design-system RULE 4): loading / error /
// empty / loaded.

import { useEffect, useState } from 'react';
import { fetchReferenceSets } from '../api/catalog';

function toArray(data) {
  if (Array.isArray(data)) return data;
  return data?.results || [];
}

/**
 * useReferenceOptions(setName) -> { options, loading, error, refetch }
 * Matches a ReferenceSet by `name` (case-insensitive) or `slug`, then maps its
 * active values to { value: code, label }.
 */
export function useReferenceOptions(setName) {
  const [options, setOptions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const token = localStorage.getItem('access');
        const data = await fetchReferenceSets(token);
        if (cancelled) return;
        const sets = toArray(data);
        const target = (setName || '').toLowerCase();
        const set = sets.find(
          (s) =>
            (s.name || '').toLowerCase() === target ||
            (s.slug || '').toLowerCase() === target,
        );
        const values = (set && set.values) || [];
        setOptions(
          values
            .filter((v) => v.is_active !== false)
            .map((v) => ({ value: v.code, label: v.label || v.code })),
        );
      } catch (err) {
        if (!cancelled) setError(err?.message || 'Failed to load options');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [setName, nonce]);

  return {
    options,
    loading,
    error,
    refetch: () => setNonce((n) => n + 1),
  };
}

export default useReferenceOptions;
