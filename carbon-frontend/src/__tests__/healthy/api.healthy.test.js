// src/__tests__/healthy/api.healthy.test.js
// API helper wiring tests — verify every helper calls apiFetch with the
// correct endpoint + method (never raw fetch()).

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { apiFetch } from '../../api/api';
import * as healthy from '../../api/healthy';

vi.mock('../../api/api', () => ({ apiFetch: vi.fn() }));

describe('healthy API helpers', () => {
  beforeEach(() => {
    apiFetch.mockReset();
    apiFetch.mockResolvedValue({});
  });

  it('fetchHealthySummary hits dashboards/summary', () => {
    healthy.fetchHealthySummary('tok');
    expect(apiFetch).toHaveBeenCalledWith('healthy/dashboards/summary/', { token: 'tok' });
  });

  it('fetchARQueue hits dashboards/ar-queue', () => {
    healthy.fetchARQueue('tok');
    expect(apiFetch).toHaveBeenCalledWith('healthy/dashboards/ar-queue/', { token: 'tok' });
  });

  it('fetchSlowMovers hits dashboards/slow-movers', () => {
    healthy.fetchSlowMovers('tok');
    expect(apiFetch).toHaveBeenCalledWith('healthy/dashboards/slow-movers/', { token: 'tok' });
  });

  it('fetchHealthySnapshots hits snapshots list', () => {
    healthy.fetchHealthySnapshots('tok');
    expect(apiFetch).toHaveBeenCalledWith('healthy/snapshots/', { token: 'tok' });
  });

  it('triggerHealthySnapshot POSTs to snapshots', () => {
    healthy.triggerHealthySnapshot({ source_view: 'ar' }, 'tok');
    expect(apiFetch).toHaveBeenCalledWith('healthy/snapshots/', {
      method: 'POST',
      body: { source_view: 'ar' },
      token: 'tok',
    });
  });

  it('fetchLoadoutSheets applies the week filter', () => {
    healthy.fetchLoadoutSheets({ week: '2026-01-05' }, 'tok');
    expect(apiFetch).toHaveBeenCalledWith('healthy/loadout/?week=2026-01-05', { token: 'tok' });
  });

  it('fetchLoadoutWeek targets the week', () => {
    healthy.fetchLoadoutWeek('2026-01-05', 'tok');
    expect(apiFetch).toHaveBeenCalledWith('healthy/loadout/2026-01-05/', { token: 'tok' });
  });

  it('fetchLoadoutRep targets week + rep', () => {
    healthy.fetchLoadoutRep('2026-01-05', 'R1', 'tok');
    expect(apiFetch).toHaveBeenCalledWith('healthy/loadout/2026-01-05/R1/', { token: 'tok' });
  });

  it('submitLoadoutActuals POSTs actuals', () => {
    healthy.submitLoadoutActuals('2026-01-05', 'R1', [{ item_code: 'A1', qty_actual: 9 }], 'tok');
    expect(apiFetch).toHaveBeenCalledWith('healthy/loadout/2026-01-05/R1/actuals/', {
      method: 'POST',
      body: [{ item_code: 'A1', qty_actual: 9 }],
      token: 'tok',
    });
  });

  it('fetchRepHealth and fetchRepHealthDetail target rep-health', () => {
    healthy.fetchRepHealth({ week: '2026-01-05' }, 'tok');
    expect(apiFetch).toHaveBeenCalledWith('healthy/rep-health/?week=2026-01-05', { token: 'tok' });

    healthy.fetchRepHealthDetail('2026-01-05', 'R1', 'tok');
    expect(apiFetch).toHaveBeenCalledWith('healthy/rep-health/2026-01-05/R1/', { token: 'tok' });
  });
});
