// useDomainManifests — fetch + cache all domain-app manifests.
// Silent failure: returns [] (UI degrades to no entry points).
import { useEffect, useState } from 'react';
import { listDomainManifests } from '../api/aiPulse';

let cache = null;

export function useDomainManifests(token) {
  const [manifests, setManifests] = useState(cache || []);

  useEffect(() => {
    let active = true;
    if (cache) {
      setManifests(cache);
      return undefined;
    }
    listDomainManifests(token)
      .then((data) => {
        cache = data?.apps || [];
        if (active) setManifests(cache);
      })
      .catch(() => {
        if (active) setManifests([]);
      });
    return () => {
      active = false;
    };
  }, [token]);

  return { manifests };
}
