import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../api', () => ({ apiFetch: vi.fn() }));

import { apiFetch } from '../api';
import { fetchDataRows } from '../dataschema';

describe('fetchDataRows', () => {
  beforeEach(() => {
    apiFetch.mockReset();
  });

  it('DE-PAGE follows next until every row of the count is loaded', async () => {
    apiFetch
      .mockResolvedValueOnce({ count: 2, next: '/p2', results: [{ id: 1 }] })
      .mockResolvedValueOnce({ count: 2, next: null, results: [{ id: 2 }] });

    const rows = await fetchDataRows('tok', 62, {}, 1, 53);

    expect(rows.map((row) => row.id)).toEqual([1, 2]);
    expect(apiFetch.mock.calls[0][0]).toContain('page_size=200');
    expect(apiFetch.mock.calls[0][0]).toContain('page=1');
    expect(apiFetch.mock.calls[1][0]).toContain('page=2');
  });

  it('DE-SEARCH sends the term to the server', async () => {
    apiFetch.mockResolvedValueOnce({ count: 0, next: null, results: [] });

    await fetchDataRows('tok', 62, { _search: 'zzzz-no-such-month' }, 1, 53);

    expect(apiFetch.mock.calls[0][0]).toContain('search=zzzz-no-such-month');
  });

  it('DE-PAGE rejects when the cap is still short of the count', async () => {
    apiFetch.mockResolvedValue({ count: 99999, next: '/more', results: [{ id: 1 }] });

    await expect(fetchDataRows('tok', 62, {}, 1, 53)).rejects.toMatchObject({
      code: 'rows_truncated',
    });
  });
});
