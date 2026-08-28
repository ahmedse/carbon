// src/pages/carbon/CarbonDashboardPage.jsx
// Emissions Dashboard — period-scoped operational emissions view.
// Chairman Overview lives at /carbon/chairman. Analytics at /carbon/analytics.

import React from 'react';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import EmissionsDashboard from '../EmissionsDashboard';

export default function CarbonDashboardPage() {
  useDocumentTitle('Emissions Dashboard');
  return <EmissionsDashboard />;
}
