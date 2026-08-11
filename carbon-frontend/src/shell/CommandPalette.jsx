// File: src/shell/CommandPalette.jsx
// Ctrl+K command palette for quick navigation and actions
// VSCode-inspired fuzzy search interface

import { useState, useEffect, useRef, useMemo } from 'react';
import {
  Dialog,
  Box,
  TextField,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Typography,
  Chip,
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import SearchIcon from '@mui/icons-material/Search';
import DashboardIcon from '@mui/icons-material/Dashboard';
import Co2Icon from '@mui/icons-material/Co2';
import StorageIcon from '@mui/icons-material/Storage';
import AdminPanelSettingsIcon from '@mui/icons-material/AdminPanelSettings';
import SettingsIcon from '@mui/icons-material/Settings';
import HelpIcon from '@mui/icons-material/Help';
import AssessmentIcon from '@mui/icons-material/Assessment';
import BarChartIcon from '@mui/icons-material/BarChart';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import DescriptionIcon from '@mui/icons-material/Description';
import PeopleIcon from '@mui/icons-material/People';
import SecurityIcon from '@mui/icons-material/Security';
import BusinessIcon from '@mui/icons-material/Business';

// Command registry - all available commands
const COMMANDS = [
  // Dashboard commands
  {
    id: 'dashboard-executive',
    label: 'Executive Summary',
    description: 'View high-level carbon footprint overview',
    path: '/dashboard',
    icon: DashboardIcon,
    keywords: ['dashboard', 'executive', 'summary', 'overview', 'home'],
  },
  {
    id: 'dashboard-analytics',
    label: 'Analytics Dashboard',
    description: 'Detailed analytics and trends',
    path: '/dashboards/analytics',
    icon: BarChartIcon,
    keywords: ['analytics', 'dashboard', 'charts', 'trends', 'analysis'],
  },
  {
    id: 'dashboard-targets',
    label: 'Targets & Progress',
    description: 'Track emission reduction targets',
    path: '/dashboards/targets',
    icon: AssessmentIcon,
    keywords: ['targets', 'goals', 'progress', 'reduction', 'objectives'],
  },
  {
    id: 'dashboard-quality',
    label: 'DQ Workspace',
    description: 'Data quality rules, jobs, suggestions and monitoring',
    path: '/dq',
    icon: CheckCircleIcon,
    keywords: ['quality', 'validation', 'data', 'accuracy', 'completeness', 'dq', 'workspace', 'rules'],
  },
  {
    id: 'dashboard-reporting',
    label: 'Reporting Dashboard',
    description: 'Generate and view reports',
    path: '/dashboards/reporting',
    icon: DescriptionIcon,
    keywords: ['reports', 'reporting', 'export', 'documents'],
  },

  // Emissions commands
  {
    id: 'emissions-dashboard',
    label: 'Emissions Dashboard',
    description: 'View emissions by scope and source',
    path: '/emissions/dashboard',
    icon: Co2Icon,
    keywords: ['emissions', 'carbon', 'co2', 'scope', 'sources'],
  },
  {
    id: 'emissions-report',
    label: 'Emissions Report',
    description: 'Generate detailed emissions report',
    path: '/emissions/report',
    icon: DescriptionIcon,
    keywords: ['report', 'emissions', 'export', 'ghg'],
  },

  // Carbon Data Entry commands
  {
    id: 'data-entry',
    label: 'Data Entry',
    description: 'Enter and manage emissions data',
    path: '/carbon/data-entry',
    icon: StorageIcon,
    keywords: ['data', 'entry', 'input', 'schema', 'records'],
  },

  // Admin commands
  {
    id: 'admin-users',
    label: 'User Management',
    description: 'Manage users and permissions',
    path: '/admin/users',
    icon: PeopleIcon,
    keywords: ['users', 'admin', 'people', 'accounts', 'permissions'],
  },
  {
    id: 'admin-access',
    label: 'Access Control',
    description: 'Configure roles and permissions',
    path: '/admin/access',
    icon: SecurityIcon,
    keywords: ['access', 'roles', 'permissions', 'security', 'rbac'],
  },
  {
    id: 'admin-orgunits',
    label: 'Organization Units',
    description: 'Manage organizational structure',
    path: '/admin/org-units',
    icon: BusinessIcon,
    keywords: ['organization', 'units', 'structure', 'hierarchy', 'orgs'],
  },

  // Settings commands
  {
    id: 'settings',
    label: 'Settings',
    description: 'Application settings and preferences',
    path: '/settings',
    icon: SettingsIcon,
    keywords: ['settings', 'preferences', 'configuration', 'profile'],
  },

  // Help commands
  {
    id: 'help',
    label: 'Help & Documentation',
    description: 'View help and documentation',
    path: '/help',
    icon: HelpIcon,
    keywords: ['help', 'documentation', 'docs', 'guide', 'support'],
  },
  {
    id: 'feedback',
    label: 'Send Feedback',
    description: 'Send feedback to the team',
    path: '/feedback',
    icon: HelpIcon,
    keywords: ['feedback', 'bug', 'report', 'suggestion', 'contact'],
  },
];

// Fuzzy search implementation
function fuzzyMatch(text, query) {
  const textLower = text.toLowerCase();
  const queryLower = query.toLowerCase();
  
  if (textLower.includes(queryLower)) {
    return true;
  }
  
  // Check if query characters appear in order
  let queryIndex = 0;
  for (let i = 0; i < textLower.length && queryIndex < queryLower.length; i++) {
    if (textLower[i] === queryLower[queryIndex]) {
      queryIndex++;
    }
  }
  return queryIndex === queryLower.length;
}

function searchCommands(query) {
  if (!query.trim()) {
    return COMMANDS;
  }

  return COMMANDS.filter((cmd) => {
    // Search in label, description, and keywords
    return (
      fuzzyMatch(cmd.label, query) ||
      fuzzyMatch(cmd.description, query) ||
      cmd.keywords.some((kw) => fuzzyMatch(kw, query))
    );
  });
}

export default function CommandPalette({ open, onClose }) {
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef(null);
  const listRef = useRef(null);
  const navigate = useNavigate();

  const filteredCommands = useMemo(() => searchCommands(query), [query]);

  // Reset state when dialog opens
  useEffect(() => {
    if (open) {
      setQuery('');
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [open]);

  // Handle keyboard navigation
  useEffect(() => {
    if (!open) return;

    const handleKeyDown = (e) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex((prev) => 
          prev < filteredCommands.length - 1 ? prev + 1 : 0
        );
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex((prev) => 
          prev > 0 ? prev - 1 : filteredCommands.length - 1
        );
      } else if (e.key === 'Enter' && filteredCommands.length > 0) {
        e.preventDefault();
        handleCommandSelect(filteredCommands[selectedIndex]);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [open, filteredCommands, selectedIndex]);

  // Auto-scroll to selected item
  useEffect(() => {
    if (listRef.current) {
      const selectedElement = listRef.current.children[selectedIndex];
      if (selectedElement) {
        selectedElement.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      }
    }
  }, [selectedIndex]);

  const handleCommandSelect = (command) => {
    navigate(command.path);
    onClose();
  };

  const handleQueryChange = (e) => {
    setQuery(e.target.value);
    setSelectedIndex(0);
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="sm"
      fullWidth
      aria-labelledby="command-palette-title"
      aria-describedby="command-palette-description"
      PaperProps={{
        sx: {
          position: 'fixed',
          top: '20%',
          m: 0,
          maxHeight: '60vh',
          borderRadius: 2,
          overflow: 'hidden',
        },
      }}
    >
      <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        {/* Search Input */}
        <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
          <TextField
            inputRef={inputRef}
            fullWidth
            placeholder="Type a command or search..."
            value={query}
            onChange={handleQueryChange}
            variant="standard"
            inputProps={{
              'aria-label': 'Search commands',
              'role': 'combobox',
              'aria-expanded': filteredCommands.length > 0,
              'aria-controls': 'command-list',
              'aria-activedescendant': filteredCommands[selectedIndex]?.id,
            }}
            InputProps={{
              startAdornment: (
                <SearchIcon sx={{ mr: 1, color: 'text.secondary', fontSize: 20 }} aria-hidden="true" />
              ),
              disableUnderline: true,
              sx: { fontSize: '0.9375rem' },
            }}
            autoComplete="off"
          />
        </Box>

        {/* Results List */}
        <List
          ref={listRef}
          id="command-list"
          role="listbox"
          aria-label="Command results"
          sx={{
            flex: 1,
            overflow: 'auto',
            py: 0.5,
            maxHeight: 'calc(60vh - 80px)',
          }}
        >
          {filteredCommands.length === 0 ? (
            <Box sx={{ p: 4, textAlign: 'center' }}>
              <Typography variant="body2" color="text.secondary">
                No commands found
              </Typography>
            </Box>
          ) : (
            filteredCommands.map((command, index) => {
              const Icon = command.icon;
              const isSelected = index === selectedIndex;

              return (
                <ListItem
                  key={command.id}
                  id={command.id}
                  role="option"
                  aria-selected={isSelected}
                  button
                  selected={isSelected}
                  onClick={() => handleCommandSelect(command)}
                  sx={{
                    py: 1.5,
                    px: 2,
                    cursor: 'pointer',
                    bgcolor: isSelected ? 'action.selected' : 'transparent',
                    '&:hover': {
                      bgcolor: 'action.hover',
                    },
                    '&:focus-visible': {
                      outline: '2px solid',
                      outlineColor: 'primary.main',
                      outlineOffset: '-2px',
                    },
                  }}
                >
                  <ListItemIcon sx={{ minWidth: 40 }}>
                    <Icon sx={{ fontSize: 20, color: 'primary.main' }} aria-hidden="true" />
                  </ListItemIcon>
                  <ListItemText
                    primary={
                      <Typography variant="body2" sx={{ fontWeight: 500 }}>
                        {command.label}
                      </Typography>
                    }
                    secondary={
                      <Typography variant="caption" color="text.secondary">
                        {command.description}
                      </Typography>
                    }
                  />
                </ListItem>
              );
            })
          )}
        </List>

        {/* Footer hint */}
        <Box
          sx={{
            p: 1.5,
            borderTop: 1,
            borderColor: 'divider',
            bgcolor: 'background.default',
            display: 'flex',
            gap: 1,
            alignItems: 'center',
            justifyContent: 'flex-end',
          }}
        >
          <Chip label="↑↓" size="small" sx={{ height: 20, fontSize: '0.625rem' }} />
          <Typography variant="caption" color="text.secondary">
            Navigate
          </Typography>
          <Chip label="Enter" size="small" sx={{ height: 20, fontSize: '0.625rem' }} />
          <Typography variant="caption" color="text.secondary">
            Select
          </Typography>
          <Chip label="Esc" size="small" sx={{ height: 20, fontSize: '0.625rem' }} />
          <Typography variant="caption" color="text.secondary">
            Close
          </Typography>
        </Box>
      </Box>
    </Dialog>
  );
}
