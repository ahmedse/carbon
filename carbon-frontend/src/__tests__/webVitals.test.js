// src/__tests__/webVitals.test.js
import { describe, it, expect, vi, afterEach } from 'vitest';
import { initWebVitals, VITALS_THRESHOLDS } from '../utils/webVitals';

describe('initWebVitals', () => {
  const originalPerformanceObserver = globalThis.PerformanceObserver;

  afterEach(() => {
    globalThis.PerformanceObserver = originalPerformanceObserver;
  });

  it('returns a no-op when PerformanceObserver is unavailable', () => {
    globalThis.PerformanceObserver = undefined;
    const onMetric = vi.fn();
    const cleanup = initWebVitals(onMetric);
    expect(cleanup).toBeTypeOf('function');
    cleanup();
    expect(onMetric).not.toHaveBeenCalled();
  });

  it('registers observers and forwards rated metrics', () => {
    const instances = [];
    class FakePerformanceObserver {
      constructor(callback) {
        this.cb = callback;
        this.options = null;
        instances.push(this);
      }

      observe(options) {
        this.options = options;
      }

      disconnect() {}
    }
    globalThis.PerformanceObserver = FakePerformanceObserver;

    const onMetric = vi.fn();
    const cleanup = initWebVitals(onMetric);

    const lcpObserver = instances.find(
      (o) => o.options && o.options.type === 'largest-contentful-paint'
    );
    const fcpObserver = instances.find(
      (o) => o.options && o.options.type === 'paint'
    );
    const clsObserver = instances.find(
      (o) => o.options && o.options.type === 'layout-shift'
    );

    expect(lcpObserver).toBeTruthy();
    expect(fcpObserver).toBeTruthy();
    expect(clsObserver).toBeTruthy();

    lcpObserver.cb({ getEntries: () => [{ startTime: 1000 }] });
    fcpObserver.cb({
      getEntries: () => [
        { name: 'first-paint', startTime: 500 },
        { name: 'first-contentful-paint', startTime: 2000 },
      ],
    });
    clsObserver.cb({ getEntries: () => [{ value: 0.3 }] });

    expect(onMetric).toHaveBeenCalledWith({ name: 'LCP', value: 1000, rating: 'good' });
    expect(onMetric).toHaveBeenCalledWith({ name: 'FCP', value: 2000, rating: 'needs-improvement' });
    expect(onMetric).toHaveBeenCalledWith({ name: 'CLS', value: 0.3, rating: 'poor' });
    // 'first-paint' is not first-contentful-paint, so it must be skipped.
    expect(onMetric).not.toHaveBeenCalledWith(
      expect.objectContaining({ name: 'FCP', value: 500 })
    );

    cleanup();
  });

  it('exposes the documented thresholds', () => {
    expect(VITALS_THRESHOLDS.LCP).toEqual({ good: 2500, poor: 4000 });
    expect(VITALS_THRESHOLDS.CLS).toEqual({ good: 0.1, poor: 0.25 });
    expect(VITALS_THRESHOLDS.INP).toEqual({ good: 200, poor: 500 });
    expect(VITALS_THRESHOLDS.FCP).toEqual({ good: 1800, poor: 3000 });
  });
});
