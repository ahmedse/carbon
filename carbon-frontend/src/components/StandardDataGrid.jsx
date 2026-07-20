// src/components/StandardDataGrid.jsx
// Shared MUI DataGrid wrapper for consistent table layout and styling.

import React, { useState } from 'react';
import { Box, Paper } from '@mui/material';
import { DataGrid, GridToolbar } from '@mui/x-data-grid';

export default function StandardDataGrid({
  rows = [],
  columns = [],
  loading = false,
  pageSize = 25,
  rowsPerPageOptions = [25, 50, 100],
  checkboxSelection = false,
  hideFooterSelectedRowCount = true,
  toolbar = false,
  initialState = {
    pagination: { paginationModel: { pageSize: 25, page: 0 } },
  },
  sx = {},
  ...props
}) {
  const [paginationModel, setPaginationModel] = useState({ pageSize, page: 0 });

  return (
    <Paper variant="outlined" sx={{ width: '100%', borderRadius: 2, overflow: 'hidden', ...sx }}>
      <Box sx={{ width: '100%' }}>
        <DataGrid
          autoHeight
          rows={rows}
          columns={columns}
          loading={loading}
          pageSizeOptions={rowsPerPageOptions}
          paginationModel={paginationModel}
          onPaginationModelChange={setPaginationModel}
          disableSelectionOnClick
          checkboxSelection={checkboxSelection}
          hideFooterSelectedRowCount={hideFooterSelectedRowCount}
          components={toolbar ? { Toolbar: GridToolbar } : undefined}
          componentsProps={toolbar ? { toolbar: { showQuickFilter: true, quickFilterProps: { debounceMs: 250 } } } : undefined}
          sx={{ border: 'none', minHeight: 420, '& .MuiDataGrid-cell': { outline: 'none' } }}
          {...props}
        />
      </Box>
    </Paper>
  );
}
