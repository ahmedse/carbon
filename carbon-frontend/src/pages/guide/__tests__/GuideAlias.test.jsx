import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useParams } from 'react-router-dom';

import GuidePage from '../GuidePage';

// Carbon's standalone hub UI is retired. /guide/carbon and /guide/carbon/<id>
// (the load-bearing D2 alias) redirect to the Journey surfaces — station page or
// lesson reader — and never 404. The lesson id is preserved, so D2 stays D2.
// Other apps still get the generic guide hub.
vi.mock('../../../components/AppEnabledRoute', () => ({
  default: ({ children }) => <>{children}</>,
}));
vi.mock('../../../components/guide/GuideHub', () => ({
  default: ({ appId, lessonId }) => (
    <div data-testid="guide-hub">{`${appId}:${lessonId || 'none'}`}</div>
  ),
}));

function JourneyReaderProbe() {
  const { appId, lessonId } = useParams();
  return <div data-testid="journey-reader">{`${appId}:${lessonId}`}</div>;
}

function renderAt(entry) {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route path="/guide/:appId" element={<GuidePage />} />
        <Route path="/guide/:appId/:lessonId" element={<GuidePage />} />
        <Route path="/journey/:appId" element={<div data-testid="journey-hub" />} />
        <Route path="/journey/:appId/:lessonId" element={<JourneyReaderProbe />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('Journey is the alias for the retired guide route', () => {
  it('redirects /guide/carbon/D2 to the Journey reader with the same lesson id', () => {
    renderAt('/guide/carbon/D2');
    expect(screen.getByTestId('journey-reader')).toHaveTextContent('carbon:D2');
    expect(screen.queryByTestId('guide-hub')).not.toBeInTheDocument();
  });

  it('redirects the /guide/carbon hub to the Journey station page, not a 404', () => {
    renderAt('/guide/carbon');
    expect(screen.getByTestId('journey-hub')).toBeInTheDocument();
    expect(screen.queryByTestId('guide-hub')).not.toBeInTheDocument();
  });

  it('keeps the generic guide hub for a non-carbon app', () => {
    renderAt('/guide/other/D9');
    expect(screen.getByTestId('guide-hub')).toHaveTextContent('other:D9');
  });
});
