// src/hooks/useVisualViewportHeight.js
// Mobile keyboard-safe height: prefer visualViewport, fall back to 100dvh.
import { useEffect, useState } from 'react';

/**
 * @returns {{ height: number|null, cssHeight: string }}
 * height is px when visualViewport is available; cssHeight is always usable in sx.
 */
export function useVisualViewportHeight(enabled = true) {
  const [height, setHeight] = useState(null);

  useEffect(() => {
    if (!enabled || typeof window === 'undefined') return undefined;
    const vv = window.visualViewport;
    if (!vv) {
      setHeight(null);
      return undefined;
    }
    const update = () => setHeight(Math.round(vv.height));
    update();
    vv.addEventListener('resize', update);
    vv.addEventListener('scroll', update);
    return () => {
      vv.removeEventListener('resize', update);
      vv.removeEventListener('scroll', update);
    };
  }, [enabled]);

  return {
    height,
    cssHeight: height != null ? `${height}px` : '100dvh',
  };
}
