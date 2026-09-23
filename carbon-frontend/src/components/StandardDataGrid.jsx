// src/components/StandardDataGrid.jsx
// Shared MUI DataGrid wrapper for consistent table layout and styling.

import React, { useState } from 'react';
import { Paper } from '@mui/material';
import { DataGrid, GridToolbar } from '@mui/x-data-grid';
import { arSD, enUS } from '@mui/x-data-grid/locales';
import { useLanguage } from '../i18n/useLanguage';

export default function StandardDataGrid({
  rows = [],
  columns = [],
  loading = false,
  pageSize = 25,
  rowsPerPageOptions = [25, 50, 100],
  checkboxSelection = false,
  hideFooterSelectedRowCount = true,
  toolbar = false,
  height = 480,
  _initialState = {
    pagination: { paginationModel: { pageSize: 25, page: 0 } },
  },
  sx = {},
  ...props
}) {
  const { lang } = useLanguage();
  const [paginationModel, setPaginationModel] = useState({ pageSize, page: 0 });
  const localeText = {
    ...(lang === 'ar' ? arSD : enUS).components.MuiDataGrid.defaultProps.localeText,
    ...(lang === 'ar' ? {
      // arSD leaves this commented, so the footer falls back to English "of".
      paginationDisplayedRows: ({ from, to, count, estimated }) => {
        if (!estimated) {
          return `${from}–${to} من ${count !== -1 ? count : `أكثر من ${to}`}`;
        }
        const estimatedLabel = estimated > to ? `حوالي ${estimated}` : `أكثر من ${to}`;
        return `${from}–${to} من ${count !== -1 ? count : estimatedLabel}`;
      },
    } : {}),
  };

  return (
    <Paper
      variant="outlined"
      sx={{
        height,
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
        disableRowSelectionOnClick
        checkboxSelection={checkboxSelection}
        hideFooterSelectedRowCount={hideFooterSelectedRowCount}
        slots={toolbar ? { toolbar: GridToolbar } : undefined}
        slotProps={toolbar ? { toolbar: { showQuickFilter: true, quickFilterProps: { debounceMs: 250 } } } : undefined}
        sx={{ border: 'none', flex: 1, '& .MuiDataGrid-cell': { outline: 'none', display: 'flex', alignItems: 'center' } }}
        {...props}
        localeText={{ ...localeText, ...props.localeText }}
      />
    </Paper>
  );
}
