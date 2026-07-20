// src/components/FilteredDataGrid.jsx
// Shared grid page shell with search, filter controls, and a standard data grid.

import React from 'react';
import {
  Box,
  Button,
  Grid,
  Stack,
  Paper,
  TextField,
  Typography,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import StandardDataGrid from './StandardDataGrid';
import PageContainer from './layout/PageContainer';
import PageHeader from './layout/PageHeader';

export default function FilteredDataGrid({
  title,
  subtitle,
  actions,
  rows = [],
  columns = [],
  loading = false,
  countLabel = '',
  searchValue = '',
  onSearchChange,
  filterDefs = [],
  filterValues = {},
  onFilterChange,
  onClearFilters,
  pageSize = 25,
  rowsPerPageOptions = [25, 50, 100],
  emptyMessage = 'No records found',
  emptySubtext = 'Try adjusting your filters.',
  toolbar = false,
}) {
  const hasFilters = Boolean(
    searchValue || filterDefs.some((def) => filterValues[def.key])
  );

  return (
    <PageContainer>
      <PageHeader title={title} subtitle={subtitle} actions={actions} />

      <Paper sx={{ p: 2, mb: 3, bgcolor: 'background.alt' }}>
        <Stack spacing={2}>
          <TextField
            placeholder="Search by name or description..."
            value={searchValue}
            onChange={(e) => onSearchChange?.(e.target.value)}
            fullWidth
            size="small"
            InputProps={{
              startAdornment: <SearchIcon sx={{ mr: 1, color: 'text.secondary' }} />,
            }}
          />

          {filterDefs.length > 0 && (
            <Grid container spacing={2}>
              {filterDefs.map((def) => (
                <Grid item xs={12} sm={6} md={3} key={def.key}>
                  <FormControl fullWidth size="small">
                    <InputLabel>{def.label}</InputLabel>
                    <Select
                      value={filterValues[def.key] || ''}
                      label={def.label}
                      onChange={(e) => onFilterChange?.(def.key, e.target.value)}
                    >
                      <MenuItem value="">{def.emptyLabel || `All ${def.label}`}</MenuItem>
                      {Array.isArray(def.options)
                        ? def.options.map((option) => (
                            <MenuItem key={option.value} value={option.value}>
                              {option.label}
                            </MenuItem>
                          ))
                        : null}
                    </Select>
                  </FormControl>
                </Grid>
              ))}
            </Grid>
          )}

          {hasFilters && (
            <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
              <Button size="small" onClick={onClearFilters}>
                Clear Filters
              </Button>
            </Box>
          )}
        </Stack>
      </Paper>

      {countLabel && (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {countLabel}
        </Typography>
      )}

      <StandardDataGrid
        rows={rows}
        columns={columns}
        loading={loading}
        pageSize={pageSize}
        rowsPerPageOptions={rowsPerPageOptions}
        hideFooterSelectedRowCount
        toolbar
      />

      {rows.length === 0 && !loading && (
        <Paper sx={{ p: 4, mt: 2, textAlign: 'center' }}>
          <Typography color="text.secondary" gutterBottom>
            {emptyMessage}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {hasFilters ? emptySubtext : 'No data is available yet.'}
          </Typography>
        </Paper>
      )}
    </PageContainer>
  );
}
