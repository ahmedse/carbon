// src/utils/webVitals.js
//
// Dependency-free Core Web Vitals collector. Uses `PerformanceObserver` to
// report LCP, CLS, INP and FCP. If the observer API is unavailable it returns
// a no-op — it never throws.

export const VITALS_THRESHOLDS = {
  LCP: { good: 2500, poor: 4000 },
  CLS: { good: 0.1, poor: 0.25 },
  INP: { good: 200, poor: 500 },
  FCP: { good: 1800, poor: 3000 },
};

const OBSERVERS = [
  { name: 'LCP', type: 'largest-contentful-paint' },
  { name: 'CLS', type: 'layout-shift' },
  { name: 'INP', type: 'event' },
  { name: 'FCP', type: 'paint' },
];

function metricValue(name, entry) {
  switch (name) {
    case 'LCP':
      return entry.startTime;
    case 'CLS':
      return entry.value;
    case 'INP':
      return entry.duration;
    case 'FCP':
      // 'paint' entries share one observer; only report first-contentful-paint.
      return entry.name === 'first-contentful-paint' ? entry.startTime : null;
    default:
      return null;
  }
}

function rateMetric(name, value) {
  const { good, poor } = VITALS_THRESHOLDS[name];
  if (value <= good) return 'good';
  if (value > poor) return 'poor';
  return 'needs-improvement';
}

/**
 * Start observing web vitals. Calls `onMetric({ name, value, rating })` once
 * per reported metric. Returns a cleanup function that disconnects observers.
 * @param {(metric: { name: string, value: number, rating: string }) => void} onMetric
 */
export function initWebVitals(onMetric) {
  if (typeof PerformanceObserver === 'undefined') return () => {};
  if (typeof onMetric !== 'function') return () => {};

  const disconnectFns = [];

  OBSERVERS.forEach(({ name, type }) => {
    try {
      const observer = new PerformanceObserver((list) => {
        list.getEntries().forEach((entry) => {
          const value = metricValue(name, entry);
          if (value == null) return;
          onMetric({ name, value, rating: rateMetric(name, value) });
        });
      });

      const options = { type };
      // Buffered observers replay entries that fired before init (LCP/CLS/INP).
      if (name !== 'FCP') options.buffered = true;
      observer.observe(options);
      disconnectFns.push(() => observer.disconnect());
    } catch {
      // Some browsers reject certain entry types — skip them gracefully.
    }
  });

  return () => disconnectFns.forEach((fn) => fn());
}

export default initWebVitals;
