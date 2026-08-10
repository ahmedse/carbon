// src/components/StandardDataGrid.jsx
// Shared MUI DataGrid wrapper for consistent table layout and styling.

import React, { useState, useRef, useEffect } from 'react';
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
  _initialState = {
    pagination: { paginationModel: { pageSize: 25, page: 0 } },
  },
  sx = {},
  ...props
}) {
  const [paginationModel, setPaginationModel] = useState({ pageSize, page: 0 });
  const paperRef = useRef(null);
  const [gridHeight, setGridHeight] = useState(400);

  useEffect(() => {
    const el = paperRef.current;
    if (!el) return;

    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const h = entry.contentRect.height;
        if (h > 0) setGridHeight(h);
      }
    });

    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return (
    <Paper
      ref={paperRef}
      variant="outlined"
      sx={{
        flex: 1,
        minHeight: 0,
        borderRadius: 2,
        overflow: 'hidden',
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
        sx={{ border: 'none', height: gridHeight, '& .MuiDataGrid-cell': { outline: 'none' } }}
        {...props}
      />
    </Paper>
  );
}
