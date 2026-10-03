import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

import AppHelp from '../../pages/AppHelp';
import { getAppGuides, getAppHelpDoc } from '../helpDocs';
import manifest from '../../apps/carbon/manifest';

function renderAppHelp(entry = '/help/carbon') {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route path="/help/:appId" element={<AppHelp />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('Carbon guides — the full detail behind the Journey', () => {
  it('offers an overview plus a Lead guide and a Field guide', () => {
    const guides = getAppGuides('carbon');
    expect(guides.map((row) => row.label)).toEqual(['Overview', 'Lead guide', 'Field guide']);
    expect(guides.every((row) => row.doc && row.doc.title)).toBe(true);
  });

  it('keeps the single-doc apps on the plain renderer (no switcher)', () => {
    expect(getAppGuides('people')).toEqual([]);
    expect(getAppHelpDoc('people').title).toContain('People');
  });

  it('switches between the guides on the app help page', () => {
    renderAppHelp();
    // Overview is the default tab, and its document is on screen.
    expect(screen.getByRole('tab', { name: 'Overview' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Welcome to Carbon Footprint/ })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: 'Lead guide' }));
    expect(screen.getByRole('heading', { name: 'Carbon Lead guide' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: 'Field guide' }));
    expect(screen.getByRole('heading', { name: 'Carbon Field guide' })).toBeInTheDocument();
  });

  it('deep-links a guide through ?guide=', () => {
    renderAppHelp('/help/carbon?guide=field');
    expect(screen.getByRole('heading', { name: 'Carbon Field guide' })).toBeInTheDocument();
  });

  it('puts the Journey guides help item at the bottom of the Carbon menu', () => {
    const labelled = manifest.navigation.items.filter((item) => item.label);
    const last = labelled[labelled.length - 1];
    expect(last.label).toBe('Journey guides');
    expect(last.path).toBe('/help/carbon');
    expect(last.role).toBe('*');
  });
});
