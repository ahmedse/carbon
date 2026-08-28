// src/pages/emissions/FactorsHubPage.jsx
// Tabbed hub — consolidates "Emission Factors" and "GWP Reference" under one
// "Emission Factors" sidebar item (R3). GWP is a subset of reference data.
//
// The GWP tab is only shown to users with CARBON_MANAGE_GWP so the single
// admin menu item stays correct for admins without the GWP capability.

import React, { useMemo, useState } from 'react';
import { Box, Tabs, Tab } from '@mui/material';
import ScienceIcon from '@mui/icons-material/Science';
import EnergySavingsLeafIcon from '@mui/icons-material/EnergySavingsLeaf';
import { useTranslation } from 'react-i18next';

import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { can } from '../../authz';
import EmissionFactorsPage from './EmissionFactorsPage';
import GWPReferencePage from './GWPReferencePage';

export default function FactorsHubPage() {
  const { t } = useTranslation('emissions');
  useDocumentTitle(t('title'));
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

  const canManageGwp = can(user, 'access_route', '/carbon/admin/gwp', authCtx);

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <Tabs
        value={tab}
        onChange={(_e, v) => setTab(v)}
        sx={{ flexShrink: 0, borderBottom: 1, borderColor: 'divider', px: 2 }}
      >
        <Tab label={t('tabEmissionFactors')} icon={<ScienceIcon />} iconPosition="start" />
        {canManageGwp ? (
          <Tab label={t('tabGwpReference')} icon={<EnergySavingsLeafIcon />} iconPosition="start" />
        ) : null}
      </Tabs>
      <Box sx={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'auto' }}>
        {tab === 0 ? <EmissionFactorsPage /> : <GWPReferencePage />}
      </Box>
    </Box>
  );
}
