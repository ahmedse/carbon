// src/components/StandardDataGrid.jsx
// Shared MUI DataGrid wrapper for consistent table layout and styling.

import React, { useState } from 'react';
import { Paper } from '@mui/material';
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
  _initialState = {
    pagination: { paginationModel: { pageSize: 25, page: 0 } },
  },
  sx = {},
  ...props
}) {
  const [paginationModel, setPaginationModel] = useState({ pageSize, page: 0 });

  return (
    <Paper
      variant="outlined"
      sx={{
        flex: 1,
        minHeight: 0,
        borderRadius: 2,
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        ...sx,
      }}
    >
      <DataGrid
        rows={rows}
        columns={columns}
        loading={loading}
        pageSizeOptions={rowsPerPageOptions}
        paginationModel={paginationModel}
        onPaginationModelChange={setPaginationModel}
        disableSelectionOnClick
        checkboxSelection={checkboxSelection}
        hideFooterSelectedRowCount={hideFooterSelectedRowCount}
        slots={toolbar ? { toolbar: GridToolbar } : undefined}
        slotProps={toolbar ? { toolbar: { showQuickFilter: true, quickFilterProps: { debounceMs: 250 } } } : undefined}
        sx={{ border: 'none', flex: 1, '& .MuiDataGrid-cell': { outline: 'none' } }}
        {...props}
      />
    </Paper>
  );
}
