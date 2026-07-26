import React from 'react';
import PropTypes from 'prop-types';
import { DataGrid, GridToolbar } from '@mui/x-data-grid';
import { useTheme, Box, Typography, Paper } from '@mui/material';

function NoRowsOverlay({ message }) {
  return (
    <Paper variant="outlined" sx={{ p: 3, textAlign: 'center', borderColor: 'divider' }}>
      <Typography sx={{ fontSize: '0.875rem', color: 'text.secondary' }}>{message}</Typography>
    </Paper>
  );
}

function CarbonDataGrid({
  columns,
  rows,
  loading,
  getRowId,
  checkboxSelection,
  onSelectionChange,
  pageSize,
  pageSizeOptions,
  stickyHeader,
  density,
  height,
  emptyMessage,
  onRowClick,
  highlightRow,
  showColumnToggle,
}) {
  const theme = useTheme();
  const stripedBg = theme.palette.mode === 'dark' ? theme.palette.grey[900] : theme.palette.grey[50];
  const stripedAlt = theme.palette.mode === 'dark' ? theme.palette.grey[800] : theme.palette.grey[100];

  const components = {
    ...(showColumnToggle ? { Toolbar: GridToolbar } : {}),
    NoRowsOverlay: () => <NoRowsOverlay message={emptyMessage} />,
  };

  return (
    <Box sx={{ width: '100%', height: height || 'auto' }}>
      <DataGrid
        rows={rows}
        columns={columns}
        loading={loading}
        getRowId={getRowId}
        checkboxSelection={checkboxSelection}
        onSelectionModelChange={(selection) => onSelectionChange?.(selection)}
        pageSize={pageSize}
        rowsPerPageOptions={pageSizeOptions}
        density={density}
        rowHeight={24}
        headerHeight={42}
        onRowClick={onRowClick}
        autoHeight={!height}
        disableSelectionOnClick
        components={components}
        sx={{
          border: 'none',
          '& .MuiDataGrid-columnHeaders': {
            position: stickyHeader ? 'sticky' : 'static',
            top: 0,
            zIndex: 1,
            backgroundColor: theme.palette.action.hover,
            color: theme.palette.text.secondary,
            fontSize: '0.75rem',
            fontWeight: 600,
            textTransform: 'uppercase',
          },
          '& .MuiDataGrid-cell': {
            fontSize: '0.8125rem',
          },
          '& .MuiDataGrid-row:nth-of-type(odd)': {
            backgroundColor: stripedBg,
          },
          '& .MuiDataGrid-row:nth-of-type(even)': {
            backgroundColor: stripedAlt,
          },
          '& .highlighted-row': {
            backgroundColor: theme.palette.warning.light,
          },
          '& .MuiDataGrid-virtualScrollerRenderZone': {
            alignContent: 'start',
          },
        }}
        getRowClassName={(params) => {
          if (highlightRow?.(params.row)) return 'highlighted-row';
          return '';
        }}
      />
    </Box>
  );
}

CarbonDataGrid.propTypes = {
  columns: PropTypes.arrayOf(PropTypes.object).isRequired,
  rows: PropTypes.arrayOf(PropTypes.object).isRequired,
  loading: PropTypes.bool,
  getRowId: PropTypes.func,
  checkboxSelection: PropTypes.bool,
  onSelectionChange: PropTypes.func,
  pageSize: PropTypes.number,
  pageSizeOptions: PropTypes.arrayOf(PropTypes.number),
  stickyHeader: PropTypes.bool,
  density: PropTypes.oneOf(['compact', 'standard', 'comfortable']),
  height: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
  emptyMessage: PropTypes.string,
  onRowClick: PropTypes.func,
  highlightRow: PropTypes.func,
  showColumnToggle: PropTypes.bool,
};

CarbonDataGrid.defaultProps = {
  loading: false,
  getRowId: (row) => row.id,
  checkboxSelection: false,
  onSelectionChange: undefined,
  pageSize: 25,
  pageSizeOptions: [10, 25, 50, 100],
  stickyHeader: true,
  density: 'compact',
  height: 'auto',
  emptyMessage: 'No data found',
  onRowClick: undefined,
  highlightRow: undefined,
  showColumnToggle: true,
};

export default React.memo(CarbonDataGrid);
