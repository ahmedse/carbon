// src/components/journey/useReducedMotion.js
// True when the OS asks for reduced motion. Test/SSR safe (matchMedia may be
// absent) and live-updates when the preference changes. Journey animations read
// this so completion transitions are opt-out, never forced.
import { useEffect, useState } from 'react';

const QUERY = '(prefers-reduced-motion: reduce)';

function read() {
  try {
    return (
      typeof window !== 'undefined'
      && typeof window.matchMedia === 'function'
      && window.matchMedia(QUERY).matches
    );
  } catch {
    return false;
  }
}

export default function useReducedMotion() {
  const [reduced, setReduced] = useState(read);

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return undefined;
    const mql = window.matchMedia(QUERY);
    const onChange = () => setReduced(Boolean(mql.matches));
    onChange();
    if (typeof mql.addEventListener === 'function') mql.addEventListener('change', onChange);
    else if (typeof mql.addListener === 'function') mql.addListener(onChange);
    return () => {
      if (typeof mql.removeEventListener === 'function') mql.removeEventListener('change', onChange);
      else if (typeof mql.removeListener === 'function') mql.removeListener(onChange);
    };
  }, []);

  return reduced;
}
