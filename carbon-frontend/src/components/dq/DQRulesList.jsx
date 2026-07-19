// carbon-frontend/src/components/dq/DQRulesList.jsx
import React from 'react';
import {
  Box,
  List,
  ListItem,
  ListItemText,
  Chip,
  Typography,
  Divider,
  Alert,
} from '@mui/material';
import {
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
} from '@mui/icons-material';

/**
 * DQRulesList
 * Displays active DQ rules for a table or field
 * Shows rule type, severity, and which fields are covered
 */

function getSeverityColor(severity) {
  switch (severity) {
    case 'error':
      return '#f44336';
    case 'warn':
      return '#ff9800';
    case 'info':
      return '#2196f3';
    default:
      return '#9e9e9e';
  }
}

function getSeverityIcon(severity) {
  switch (severity) {
    case 'error':
      return <ErrorIcon sx={{ color: '#f44336', fontSize: '1.2rem' }} />;
    case 'warn':
      return <WarningIcon sx={{ color: '#ff9800', fontSize: '1.2rem' }} />;
    case 'info':
      return <CheckCircleIcon sx={{ color: '#2196f3', fontSize: '1.2rem' }} />;
    default:
      return null;
  }
}

function formatRuleType(ruleType) {
  return ruleType
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

export default function DQRulesList({ rules, loading, error }) {
  if (loading) {
    return <Typography variant="body2">Loading rules...</Typography>;
  }

  if (error) {
    return <Alert severity="error">Failed to load rules: {error}</Alert>;
  }

  if (!rules || rules.length === 0) {
    return <Alert severity="info">No active DQ rules configured for this table.</Alert>;
  }

  return (
    <Box>
      <List sx={{ width: '100%', bgcolor: 'background.paper' }}>
        {rules.map((rule, index) => (
          <Box key={rule.id}>
            <ListItem
              sx={{
                display: 'flex',
                alignItems: 'flex-start',
                py: 2,
                px: 0,
              }}
            >
              <Box sx={{ mr: 2, display: 'flex', mt: 0.5 }}>
                {getSeverityIcon(rule.severity)}
              </Box>
              <ListItemText
                primary={
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                    <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                      {formatRuleType(rule.rule_type)}
                    </Typography>
                    <Chip
                      label={rule.is_active ? 'Active' : 'Inactive'}
                      size="small"
                      variant="outlined"
                      sx={{
                        borderColor: rule.is_active ? '#4caf50' : '#bdbdbd',
                        color: rule.is_active ? '#4caf50' : '#9e9e9e',
                      }}
                    />
                    <Chip
                      label={rule.severity.toUpperCase()}
                      size="small"
                      sx={{
                        backgroundColor: getSeverityColor(rule.severity),
                        color: 'white',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                      }}
                    />
                  </Box>
                }
                secondary={
                  <Box sx={{ mt: 1 }}>
                    <Typography variant="caption" display="block" sx={{ mb: 0.5 }}>
                      <strong>Scope:</strong> {rule.scope === 'table' ? 'Entire Table' : 'Field-Level'}
                    </Typography>
                    {rule.data_field && (
                      <Typography variant="caption" display="block" sx={{ mb: 0.5 }}>
                        <strong>Field:</strong> {rule.data_field}
                      </Typography>
                    )}
                    {rule.params && Object.keys(rule.params).length > 0 && (
                      <Typography variant="caption" display="block">
                        <strong>Parameters:</strong> {JSON.stringify(rule.params)}
                      </Typography>
                    )}
                  </Box>
                }
              />
            </ListItem>
            {index < rules.length - 1 && <Divider />}
          </Box>
        ))}
      </List>
    </Box>
  );
}
