// src/components/FilteredDataGrid.jsx
// Shared grid page shell with search, a collapsible "Filters" panel, and a
// standard data grid. Unified filter UX: search always visible; filters collapse
// behind a Tune button and surface as removable chips.
// RULE 13: filter pickers use platform SearchSelect (not raw MUI Select).

import React, { useState } from 'react';
import {
  Box,
  Button,
  Grid,
  Stack,
  Paper,
  TextField,
  Typography,
  Chip,
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import SearchIcon from '@mui/icons-material/Search';
import TuneIcon from '@mui/icons-material/Tune';
import StandardDataGrid from './StandardDataGrid';
import PageContainer from './layout/PageContainer';
import PageHeader from './Page/PageHeader';
import { SearchSelect } from './Form';

export default function FilteredDataGrid({
  title,
  subtitle,
  description,
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
  emptyMessage,
  emptySubtext,
  getRowId,
  _toolbar = false,
}) {
  const { t } = useTranslation('common');
  const [showFilters, setShowFilters] = useState(false);

  const resolvedEmptyMessage = emptyMessage ?? t('noRecordsFound');
  const resolvedEmptySubtext = emptySubtext ?? t('tryAdjustingFilters');

  const activeFilters = filterDefs
    .map((def) => {
      const value = filterValues[def.key];
      if (!value) return null;
      const option = Array.isArray(def.options)
        ? def.options.find((o) => String(o.value) === String(value))
        : null;
      return { key: def.key, label: option?.label || String(value) };
    })
    .filter(Boolean);

  const hasFilters = Boolean(searchValue || activeFilters.length > 0);

  return (
    <PageContainer>
      <PageHeader title={title} subtitle={subtitle} description={description} actions={actions} />

      <Paper sx={{ p: 2, mb: 3, bgcolor: 'background.paper' }}>
        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
          <TextField
            placeholder={t('searchByName')}
            value={searchValue}
            onChange={(e) => onSearchChange?.(e.target.value)}
            size="small"
            sx={{ flex: '1 1 240px', minWidth: 200 }}
            InputProps={{
              startAdornment: <SearchIcon sx={{ mr: 1, color: 'text.secondary' }} />,
            }}
          />

          {filterDefs.length > 0 && (
            <Button
              variant="outlined"
              size="small"
              startIcon={<TuneIcon />}
              onClick={() => setShowFilters((v) => !v)}
              color={activeFilters.length > 0 ? 'primary' : 'inherit'}
            >
              {t('filters')}{activeFilters.length > 0 ? ` (${activeFilters.length})` : ''}
            </Button>
          )}

          {activeFilters.map((f) => (
            <Chip
              key={f.key}
              size="small"
              variant="outlined"
              color="primary"
              label={f.label}
              onDelete={() => onFilterChange?.(f.key, '')}
            />
          ))}

          {hasFilters && (
            <Box sx={{ flexGrow: 1, display: 'flex', justifyContent: 'flex-end' }}>
              <Button size="small" onClick={onClearFilters}>
                {t('clear')}
              </Button>
            </Box>
          )}
        </Stack>

        {showFilters && filterDefs.length > 0 && (
          <Grid container spacing={2} sx={{ mt: 2 }}>
            {filterDefs.map((def) => {
              const options = [
                { value: '', label: def.emptyLabel || t('allX', { label: def.label }) },
                ...(Array.isArray(def.options) ? def.options : []),
              ];
              return (
                <Grid size={{ xs: 12, sm: 6, md: 3 }} key={def.key}>
                  <SearchSelect
                    options={options}
                    valueKey="value"
                    labelKey="label"
                    label={def.label}
                    value={filterValues[def.key] ?? ''}
                    onChange={(v) => onFilterChange?.(def.key, v?.value ?? '')}
                    clearable={false}
                    size="small"
                  />
                </Grid>
              );
            })}
          </Grid>
        )}
      </Paper>

      {countLabel && (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          {countLabel}
        </Typography>
      )}

      <Box sx={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
        <StandardDataGrid
          rows={rows}
          columns={columns}
          loading={loading}
          pageSize={pageSize}
          rowsPerPageOptions={rowsPerPageOptions}
          hideFooterSelectedRowCount
          toolbar
          getRowId={getRowId}
        />

        {rows.length === 0 && !loading && (
          <Paper sx={{ p: 4, mt: 2, textAlign: 'center' }}>
            <Typography color="text.secondary" gutterBottom>
              {resolvedEmptyMessage}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {hasFilters ? resolvedEmptySubtext : t('noDataAvailable')}
            </Typography>
          </Paper>
        )}
      </Box>
    </PageContainer>
  );
}
