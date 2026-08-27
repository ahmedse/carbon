// src/pages/carbon/CarbonDashboardPage.jsx
// Tabbed hub — consolidates "Emissions Dashboard" (current period) and
// "Analytics & Trends" (date-range comparison) under one sidebar item (R1).
//
// The Analytics tab is only shown to users with CARBON_VIEW_ANALYTICS so the
// single "*"-role menu item stays correct for non-analyst roles.

import React, { useMemo, useState } from 'react';
import { Box, Tabs, Tab } from '@mui/material';
import BarChartIcon from '@mui/icons-material/BarChart';
import InsightsIcon from '@mui/icons-material/Insights';

import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { can } from '../../authz';
import EmissionsDashboard from '../EmissionsDashboard';
import AnalyticsDashboard from '../dashboards/AnalyticsDashboard';

export default function CarbonDashboardPage() {
  useDocumentTitle('Emissions Dashboard');
  const { user, availablePerspectives, isGlobalAdminFlag, userCapabilities, context } = useAuth();
  const [tab, setTab] = useState(0);

  const authCtx = useMemo(
    () => ({
      perspectives: availablePerspectives,
      isGlobalAdminFlag,
      capabilities: userCapabilities,
      modules: context?.modules || [],
    }),
    [availablePerspectives, isGlobalAdminFlag, userCapabilities, context]
  );

  const canViewAnalytics = can(user, 'access_route', '/carbon/analytics', authCtx);

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <Tabs
        value={tab}
        onChange={(_e, v) => setTab(v)}
        sx={{ flexShrink: 0, borderBottom: 1, borderColor: 'divider', px: 2 }}
      >
        <Tab label="Dashboard" icon={<BarChartIcon />} iconPosition="start" />
        {canViewAnalytics ? (
          <Tab label="Analytics & Trends" icon={<InsightsIcon />} iconPosition="start" />
        ) : null}
      </Tabs>
      <Box sx={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'auto' }}>
        {tab === 0 ? <EmissionsDashboard /> : <AnalyticsDashboard />}
      </Box>
    </Box>
  );
}
