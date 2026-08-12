// Shared theme tokens and non-component helpers.

export const SPACING = {
  xs: 1,
  sm: 1.5,
  md: 2,
  lg: 3,
  xl: 4,
};

export const FONT = {
  pageTitle:   { fontSize: '1rem', fontWeight: 700, lineHeight: 1.3 },
  sectionTitle:{ fontSize: '0.6875rem', fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase' },
  cardTitle:   { fontSize: '0.75rem', fontWeight: 600, lineHeight: 1.3 },
  body:        { fontSize: '0.6875rem', lineHeight: 1.5 },
  bodySmall:   { fontSize: '0.625rem', lineHeight: 1.5 },
  caption:     { fontSize: '0.5625rem', lineHeight: 1.4 },
  statValue:   { fontSize: '1.125rem', fontWeight: 700, lineHeight: 1.2 },
  statLabel:   { fontSize: '0.5625rem', fontWeight: 500, letterSpacing: '0.02em', textTransform: 'uppercase' },
  chip:        { fontSize: '0.5625rem', fontWeight: 500 },
  tab:         { fontSize: '0.625rem', fontWeight: 600 },
};

export const BORDER = {
  light: '1px solid',
  card: '1px solid',
  radius: 1.5,
};

import {
  NatureRounded,
  BoltRounded,
  LocalShippingRounded,
} from '@mui/icons-material';

export const SCOPE_META = {
  1: { bg: '#e8f5e9', color: '#2e7d32', label: 'Scope 1', icon: NatureRounded },
  2: { bg: '#e3f2fd', color: '#1565c0', label: 'Scope 2', icon: BoltRounded },
  3: { bg: '#fff3e0', color: '#e65100', label: 'Scope 3', icon: LocalShippingRounded },
};

import {
  CheckCircle as PassIcon,
  Warning as WarningIcon,
  Error as FailIcon,
  Info as InfoIcon,
} from '@mui/icons-material';

export const QUALITY_CONFIG = {
  passing: { color: 'success', icon: PassIcon, label: 'Passing' },
  warning: { color: 'warning', icon: WarningIcon, label: 'Warning' },
  failing: { color: 'error', icon: FailIcon, label: 'Failing' },
  unknown: { color: 'default', icon: InfoIcon, label: 'Unknown' },
};