// Carbon Data Trust Platform — MUI theme
// Design language adopted from the Gigacast platform (zinc/blue palette,
// compact spacing, subtle borders over heavy shadows). Light + dark modes.
import { createTheme } from '@mui/material/styles';

// Brand Colors — zinc/blue palette
const brandColors = {
  primary: {
    main: '#2563eb',
    light: '#3b82f6',
    dark: '#1d4ed8',
    contrastText: '#FFFFFF',
  },
  secondary: {
    main: '#475569',
    light: '#64748b',
    dark: '#334155',
    contrastText: '#FFFFFF',
  },
  success: {
    main: '#10b981',
    light: '#34d399',
    dark: '#059669',
  },
  warning: {
    main: '#f59e0b',
    light: '#fbbf24',
    dark: '#d97706',
  },
  error: {
    main: '#ef4444',
    light: '#f87171',
    dark: '#dc2626',
  },
  info: {
    main: '#0ea5e9',
    light: '#38bdf8',
    dark: '#0284c7',
  },
};

// Light Theme Colors — zinc palette
const lightColors = {
  ...brandColors,
  background: {
    default: '#ffffff',
    paper: '#fafafa',
    dark: '#f4f4f5',
  },
  text: {
    primary: '#18181b',
    secondary: '#71717a',
    disabled: '#a1a1aa',
  },
  divider: '#e4e4e7',
  action: {
    hover: 'rgba(0, 0, 0, 0.04)',
    selected: 'rgba(37, 99, 235, 0.08)',
    disabled: 'rgba(0, 0, 0, 0.26)',
    disabledBackground: 'rgba(0, 0, 0, 0.12)',
  },
};

// Dark Theme Colors — zinc-950/zinc-900 palette
const darkColors = {
  ...brandColors,
  background: {
    default: '#09090b',
    paper: '#18181b',
    dark: '#27272a',
  },
  text: {
    primary: '#f4f4f5',
    secondary: '#a1a1aa',
    disabled: '#71717a',
  },
  divider: '#27272a',
  action: {
    hover: 'rgba(255, 255, 255, 0.05)',
    selected: 'rgba(37, 99, 235, 0.15)',
    disabled: 'rgba(255, 255, 255, 0.3)',
    disabledBackground: 'rgba(255, 255, 255, 0.12)',
  },
};

// Create Theme Function
const createCarbonTheme = (mode = 'light') => {
  const colors = mode === 'light' ? lightColors : darkColors;

  return createTheme({
    palette: {
      mode,
      ...colors,
    },

    typography: {
      fontFamily: '"Inter", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      fontSize: 13,
      h1: {
        fontSize: '1.95rem',
        fontWeight: 700,
        letterSpacing: '-0.02em',
        color: colors.text.primary,
      },
      h2: {
        fontSize: '1.75rem',
        fontWeight: 700,
        letterSpacing: '-0.01em',
        color: colors.text.primary,
      },
      h3: {
        fontSize: '1.5rem',
        fontWeight: 600,
        letterSpacing: '-0.01em',
        color: colors.text.primary,
      },
      h4: {
        fontSize: '1.25rem',
        fontWeight: 600,
        color: colors.text.primary,
      },
      h5: {
        fontSize: '1.25rem',
        fontWeight: 600,
        color: colors.text.primary,
      },
      h6: {
        fontSize: '1rem',
        fontWeight: 600,
        color: colors.text.primary,
      },
      subtitle1: {
        fontSize: '0.875rem',
        fontWeight: 500,
        letterSpacing: '0.01em',
        color: colors.text.secondary,
      },
      subtitle2: {
        fontSize: '0.8125rem',
        fontWeight: 500,
        letterSpacing: '0.01em',
        color: colors.text.secondary,
      },
      body1: {
        fontSize: '0.875rem',
        lineHeight: 1.5,
        color: colors.text.primary,
      },
      body2: {
        fontSize: '0.8125rem',
        lineHeight: 1.5,
        color: colors.text.secondary,
      },
      button: {
        textTransform: 'none',
        fontWeight: 600,
        letterSpacing: '0.02em',
      },
      caption: {
        fontSize: '0.6875rem',
        color: colors.text.secondary,
      },
    },

    shape: {
      borderRadius: 8,
    },

    spacing: 8,

    shadows: [
      'none',
      '0 1px 2px rgba(0, 0, 0, 0.05)',
      '0 1px 3px rgba(0, 0, 0, 0.08), 0 1px 2px rgba(0, 0, 0, 0.04)',
      '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
      '0 6px 12px rgba(0, 0, 0, 0.12)',
      '0 8px 16px rgba(0, 0, 0, 0.14)',
      '0 10px 20px rgba(0, 0, 0, 0.16)',
      '0 12px 24px rgba(0, 0, 0, 0.18)',
      '0 16px 32px rgba(0, 0, 0, 0.2)',
      '0 18px 36px rgba(0, 0, 0, 0.22)',
      '0 20px 40px rgba(0, 0, 0, 0.24)',
      ...Array(14).fill('0 20px 40px rgba(0, 0, 0, 0.24)'),
    ],

    transitions: {
      duration: {
        shortest: 100,
        shorter: 150,
        short: 200,
        standard: 250,
        complex: 300,
        enteringScreen: 200,
        leavingScreen: 150,
      },
      easing: {
        easeInOut: 'cubic-bezier(0.4, 0, 0.2, 1)',
        easeOut: 'cubic-bezier(0.0, 0, 0.2, 1)',
        easeIn: 'cubic-bezier(0.4, 0, 1, 1)',
        sharp: 'cubic-bezier(0.4, 0, 0.6, 1)',
      },
    },

    components: {
      MuiCssBaseline: {
        styleOverrides: {
          'html, body, #root': {
            height: '100%',
          },
          body: {
            fontSize: 13,
            lineHeight: 1.45,
            letterSpacing: '-0.011em',
            WebkitFontSmoothing: 'antialiased',
            MozOsxFontSmoothing: 'grayscale',
            scrollbarColor: `${mode === 'light' ? '#d4d4d8' : '#3f3f46'} transparent`,
            '&::-webkit-scrollbar, & *::-webkit-scrollbar': {
              width: 6,
              height: 6,
            },
            '&::-webkit-scrollbar-thumb, & *::-webkit-scrollbar-thumb': {
              borderRadius: 9999,
              backgroundColor: mode === 'light' ? '#d4d4d8' : '#3f3f46',
              minHeight: 24,
            },
            '&::-webkit-scrollbar-thumb:hover, & *::-webkit-scrollbar-thumb:hover': {
              backgroundColor: mode === 'light' ? '#a1a1aa' : '#52525b',
            },
            '&::-webkit-scrollbar-track, & *::-webkit-scrollbar-track': {
              backgroundColor: 'transparent',
            },
          },
        },
      },
      MuiButton: {
        styleOverrides: {
          root: {
            borderRadius: 4,
            padding: '4px 12px',
            fontSize: '0.8125rem',
            fontWeight: 500,
            textTransform: 'none',
            boxShadow: 'none',
            minHeight: '28px',
            transition: 'all 150ms ease',
            '&:hover': {
              boxShadow: '0 2px 4px rgba(0, 0, 0, 0.08)',
            },
          },
          contained: {
            '&:hover': {
              boxShadow: '0 4px 8px rgba(0, 0, 0, 0.12)',
            },
          },
          outlined: {
            borderWidth: '1px',
            '&:hover': {
              borderWidth: '1px',
              backgroundColor: colors.action.hover,
            },
          },
          text: {
            '&:hover': {
              backgroundColor: colors.action.hover,
            },
          },
          sizeLarge: {
            padding: '6px 16px',
            fontSize: '0.875rem',
            minHeight: '32px',
          },
          sizeSmall: {
            padding: '2px 8px',
            fontSize: '0.75rem',
            minHeight: '24px',
          },
        },
        defaultProps: { disableElevation: true },
      },
      MuiCard: {
        styleOverrides: {
          root: {
            boxShadow: 'none',
            borderRadius: 8,
            border: `1px solid ${colors.divider}`,
            backgroundColor: colors.background.paper,
            transition: 'border-color 150ms ease',
            '&:hover': {
              boxShadow: 'none',
            },
          },
        },
        defaultProps: { elevation: 0 },
      },
      MuiPaper: {
        styleOverrides: {
          root: {
            borderRadius: 8,
            backgroundImage: 'none',
            boxShadow: 'none',
          },
          elevation1: {
            boxShadow: '0 1px 3px rgba(0, 0, 0, 0.08), 0 1px 2px rgba(0, 0, 0, 0.04)',
          },
          elevation2: {
            boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
          },
          elevation3: {
            boxShadow: '0 6px 12px rgba(0, 0, 0, 0.12)',
          },
        },
      },
      MuiAccordion: {
        styleOverrides: {
          root: {
            boxShadow: 'none',
            border: `1px solid ${colors.divider}`,
            borderRadius: '4px !important',
            marginBottom: 8,
            '&:before': {
              display: 'none',
            },
            '&.Mui-expanded': {
              margin: '0 0 8px 0',
              boxShadow: '0px 2px 6px rgba(0, 0, 0, 0.06)',
            },
          },
        },
      },
      MuiAccordionSummary: {
        styleOverrides: {
          root: {
            padding: '0 12px',
            minHeight: 40,
            '&.Mui-expanded': {
              minHeight: 40,
              borderBottom: `1px solid ${colors.divider}`,
            },
          },
          content: {
            margin: '8px 0',
            '&.Mui-expanded': {
              margin: '8px 0',
            },
          },
        },
      },
      MuiAccordionDetails: {
        styleOverrides: {
          root: {
            padding: '12px',
          },
        },
      },
      MuiChip: {
        styleOverrides: {
          root: {
            borderRadius: 4,
            fontWeight: 500,
            fontSize: '0.75rem',
            height: '20px',
          },
          colorSuccess: {
            backgroundColor: mode === 'light' ? '#e7f9f3' : 'rgba(16, 185, 129, 0.15)',
            color: mode === 'light' ? colors.success.dark : '#34d399',
            border: 'none',
          },
          colorError: {
            backgroundColor: mode === 'light' ? '#fdeef2' : 'rgba(239, 68, 68, 0.15)',
            color: mode === 'light' ? colors.error.dark : '#f87171',
            border: 'none',
          },
          colorWarning: {
            backgroundColor: mode === 'light' ? '#fff4e6' : 'rgba(245, 158, 11, 0.15)',
            color: mode === 'light' ? colors.warning.dark : '#fbbf24',
            border: 'none',
          },
          colorInfo: {
            backgroundColor: mode === 'light' ? '#e8f4f8' : 'rgba(14, 165, 233, 0.15)',
            color: mode === 'light' ? colors.info.dark : '#38bdf8',
            border: 'none',
          },
          colorPrimary: {
            backgroundColor: mode === 'light' ? 'rgba(37, 99, 235, 0.1)' : 'rgba(37, 99, 235, 0.2)',
            color: colors.primary.main,
            border: 'none',
          },
        },
      },
      MuiTableHead: {
        styleOverrides: {
          root: {
            '& .MuiTableCell-head': {
              backgroundColor: colors.background.dark,
              color: colors.text.primary,
              fontWeight: 600,
              fontSize: '0.6875rem',
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              padding: '8px 12px',
              borderBottom: `2px solid ${colors.divider}`,
            },
          },
        },
      },
      MuiTableCell: {
        styleOverrides: {
          root: {
            padding: '6px 10px',
            fontSize: '0.75rem',
            borderBottom: `1px solid ${colors.divider}`,
          },
        },
      },
      MuiTableRow: {
        styleOverrides: {
          root: {
            transition: 'background-color 150ms ease',
            '&:hover': {
              backgroundColor: mode === 'light' ? 'rgba(37, 99, 235, 0.04)' : 'rgba(255, 255, 255, 0.03)',
            },
            '&:last-child td': {
              borderBottom: 0,
            },
          },
        },
      },
      MuiIconButton: {
        styleOverrides: {
          root: {
            borderRadius: 4,
            padding: 6,
            transition: 'all 120ms ease',
            '&:hover': {
              backgroundColor: mode === 'light' ? 'rgba(37, 99, 235, 0.06)' : 'rgba(37, 99, 235, 0.12)',
            },
          },
          sizeSmall: {
            padding: 4,
            fontSize: '1.125rem',
          },
        },
      },
      MuiToggleButton: {
        styleOverrides: {
          root: {
            borderRadius: 4,
            padding: '4px 12px',
            textTransform: 'none',
            fontWeight: 500,
            fontSize: '0.8125rem',
            lineHeight: 1.5,
            transition: 'all 120ms ease',
            '&.Mui-selected': {
              backgroundColor: colors.primary.main,
              color: colors.primary.contrastText,
              '&:hover': {
                backgroundColor: colors.primary.dark,
              },
            },
          },
          sizeSmall: {
            padding: '2px 8px',
            fontSize: '0.75rem',
          },
        },
      },
      MuiAlert: {
        styleOverrides: {
          root: {
            borderRadius: 4,
            padding: '6px 12px',
            fontSize: '0.8125rem',
            border: `1px solid`,
          },
          standardSuccess: {
            backgroundColor: mode === 'light' ? '#e7f9f3' : 'rgba(16, 185, 129, 0.12)',
            color: mode === 'light' ? colors.success.dark : '#34d399',
            borderColor: mode === 'light' ? colors.success.light : 'rgba(16, 185, 129, 0.3)',
          },
          standardError: {
            backgroundColor: mode === 'light' ? '#fdeef2' : 'rgba(239, 68, 68, 0.12)',
            color: mode === 'light' ? colors.error.dark : '#f87171',
            borderColor: mode === 'light' ? colors.error.light : 'rgba(239, 68, 68, 0.3)',
          },
          standardWarning: {
            backgroundColor: mode === 'light' ? '#fff4e6' : 'rgba(245, 158, 11, 0.12)',
            color: mode === 'light' ? colors.warning.dark : '#fbbf24',
            borderColor: mode === 'light' ? colors.warning.light : 'rgba(245, 158, 11, 0.3)',
          },
          standardInfo: {
            backgroundColor: mode === 'light' ? '#e8f4f8' : 'rgba(14, 165, 233, 0.12)',
            color: mode === 'light' ? colors.info.dark : '#38bdf8',
            borderColor: mode === 'light' ? colors.info.light : 'rgba(14, 165, 233, 0.3)',
          },
        },
      },
      MuiDivider: {
        styleOverrides: {
          root: {
            borderColor: colors.divider,
          },
        },
      },
      MuiTextField: {
        defaultProps: { size: 'small' },
        styleOverrides: {
          root: {
            '& .MuiOutlinedInput-root': {
              borderRadius: 4,
              transition: 'all 150ms ease',
              '&:hover .MuiOutlinedInput-notchedOutline': {
                borderColor: mode === 'light' ? colors.text.secondary : 'rgba(255, 255, 255, 0.2)',
              },
              '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
                borderWidth: '2px',
              },
            },
          },
        },
      },
      MuiSelect: {
        defaultProps: { size: 'small' },
      },
      MuiTooltip: {
        styleOverrides: {
          tooltip: {
            backgroundColor: mode === 'light' ? colors.text.primary : colors.background.dark,
            fontSize: '0.75rem',
            padding: '4px 8px',
            borderRadius: 4,
            boxShadow: '0 2px 8px rgba(0, 0, 0, 0.12)',
          },
          arrow: {
            color: mode === 'light' ? colors.text.primary : colors.background.dark,
          },
        },
      },
      MuiDrawer: {
        styleOverrides: {
          paper: { border: 'none' },
        },
      },
      MuiListItemButton: {
        styleOverrides: {
          root: {
            borderRadius: 4,
            marginBottom: 2,
            '&.Mui-selected': {
              backgroundColor: colors.action.selected,
            },
          },
        },
      },
      MuiListItemText: {
        styleOverrides: {
          primary: { fontSize: '0.8125rem', fontWeight: 500 },
          secondary: { fontSize: '0.75rem' },
        },
      },
      MuiDataGrid: {
        styleOverrides: {
          root: {
            border: 'none',
            fontSize: '0.75rem',
            '& .MuiDataGrid-columnHeaders': {
              backgroundColor: colors.background.dark,
              borderBottom: `2px solid ${colors.divider}`,
            },
            '& .MuiDataGrid-cell': {
              borderBottom: `1px solid ${colors.divider}`,
            },
            '& .MuiDataGrid-row:hover': {
              backgroundColor: mode === 'light' ? 'rgba(37, 99, 235, 0.04)' : 'rgba(255, 255, 255, 0.03)',
            },
          },
        },
      },
      MuiTabs: {
        styleOverrides: {
          root: {
            minHeight: 36,
          },
          indicator: {
            height: 2,
          },
        },
      },
      MuiTab: {
        styleOverrides: {
          root: {
            textTransform: 'none',
            fontSize: '0.8125rem',
            fontWeight: 500,
            minHeight: 36,
            padding: '6px 12px',
          },
        },
      },
      MuiDialogTitle: {
        styleOverrides: {
          root: {
            fontSize: '1rem',
            fontWeight: 600,
            padding: '12px 16px',
          },
        },
      },
      MuiDialogContent: {
        styleOverrides: {
          root: {
            padding: '12px 16px',
          },
        },
      },
      MuiDialogActions: {
        styleOverrides: {
          root: {
            padding: '8px 16px',
          },
        },
      },
    },
  });
};

export default createCarbonTheme;
export { brandColors, lightColors, darkColors };
