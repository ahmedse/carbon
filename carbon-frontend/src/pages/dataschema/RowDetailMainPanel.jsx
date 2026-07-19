// File: src/pages/dataschema/RowDetailMainPanel.jsx
// Main content panel with Overview, Edit, and Evidence tabs

import React, { useState } from 'react';
import { Box, CircularProgress, Alert } from '@mui/material';
import { API_BASE_URL } from '../../config';
import RowOverviewTab from './tabs/RowOverviewTab';
import RowEditTab from './tabs/RowEditTab';
import RowEvidenceTab from './tabs/RowEvidenceTab';

export default function RowDetailMainPanel({
  mainTabIndex,
  rowData,
  setRowData,
  tableId,
  rowId,
  token,
  onClose,
}) {
  const [tabLoading, setTabLoading] = useState(false);
  const [tabError, setTabError] = useState(null);

  const handleRefresh = async () => {
    setTabLoading(true);
    setTabError(null);

    try {
      const response = await fetch(
        `${API_BASE_URL}dataschema/rows/${rowId}/?data_table=${tableId}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) {
        throw new Error('Failed to refresh row data');
      }

      const data = await response.json();
      setRowData(data);
    } catch (err) {
      setTabError(err.message);
    } finally {
      setTabLoading(false);
    }
  };

  // Render tab content
  const renderTabContent = () => {
    if (tabLoading) {
      return (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
          <CircularProgress />
        </Box>
      );
    }

    if (tabError) {
      return (
        <Box sx={{ p: 2 }}>
          <Alert severity="error">{tabError}</Alert>
        </Box>
      );
    }

    switch (mainTabIndex) {
      case 0:
        return (
          <RowOverviewTab
            rowData={rowData}
            onRefresh={handleRefresh}
            onClose={onClose}
          />
        );
      case 1:
        return (
          <RowEditTab
            rowData={rowData}
            setRowData={setRowData}
            tableId={tableId}
            rowId={rowId}
            token={token}
            onClose={onClose}
          />
        );
      case 2:
        return (
          <RowEvidenceTab
            rowId={rowId}
            token={token}
          />
        );
      default:
        return null;
    }
  };

  return (
    <Box
      sx={{
        p: 3,
        overflow: 'auto',
        height: '100%',
      }}
    >
      {renderTabContent()}
    </Box>
  );
}
