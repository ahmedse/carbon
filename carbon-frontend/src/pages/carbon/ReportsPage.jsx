// src/pages/carbon/ReportsPage.jsx
// Tabbed hub — consolidates "Generate Report" and "Saved Reports" under one
// "Reports" sidebar item (R4). Both views share CARBON_GENERATE_REPORTS.

import React, { useState } from 'react';
import { Box, Tabs, Tab } from '@mui/material';
import AssessmentIcon from '@mui/icons-material/Assessment';
import FolderIcon from '@mui/icons-material/Folder';

import useDocumentTitle from '../../hooks/useDocumentTitle';
import ReportGeneratorPage from '../emissions/ReportGeneratorPage';
import SavedReportsPage from '../emissions/SavedReportsPage';

export default function ReportsPage() {
  useDocumentTitle('Reports');
  const [tab, setTab] = useState(0);

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <Tabs
        value={tab}
        onChange={(_e, v) => setTab(v)}
        sx={{ flexShrink: 0, borderBottom: 1, borderColor: 'divider', px: 2 }}
      >
        <Tab label="Generate Report" icon={<AssessmentIcon />} iconPosition="start" />
        <Tab label="Saved Reports" icon={<FolderIcon />} iconPosition="start" />
      </Tabs>
      <Box sx={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
        {tab === 0 ? <ReportGeneratorPage /> : <SavedReportsPage />}
      </Box>
    </Box>
  );
}
