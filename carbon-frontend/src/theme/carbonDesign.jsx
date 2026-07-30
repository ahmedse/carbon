// src/theme/carbonDesign.js
// Unified Carbon Design System — compact, enterprise-grade, next-gen
//
// Principles:
//   - Full-width content (no maxWidth containers)
//   - Compact typography (13px body, 11px captions)
//   - Consistent 16px/24px spacing rhythm
//   - Subtle borders over heavy shadows
//   - All tokens in one place — no scattered magic numbers

import { Box, Paper, Typography, Accordion, AccordionSummary, AccordionDetails } from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';

// ── Spacing Scale ──────────────────────────────────────────────────────────
export const SPACING = {
  xs: 1,    // 8px
  sm: 1.5,  // 12px
  md: 2,    // 16px
  lg: 3,    // 24px
  xl: 4,    // 32px
};

// ── Typography Scale (compact, Linear/Vercel-inspired) ─────────────────────
export const FONT = {
  pageTitle:   { fontSize: '1rem', fontWeight: 700, lineHeight: 1.3 },   // ~16px
  sectionTitle:{ fontSize: '0.6875rem', fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase' }, // ~11px
  cardTitle:   { fontSize: '0.75rem', fontWeight: 600, lineHeight: 1.3 },   // ~12px
  body:        { fontSize: '0.6875rem', lineHeight: 1.5 },                    // ~11px
  bodySmall:   { fontSize: '0.625rem', lineHeight: 1.5 },                      // ~10px
  caption:     { fontSize: '0.5625rem', lineHeight: 1.4 },                    // ~9px
  statValue:   { fontSize: '1.125rem', fontWeight: 700, lineHeight: 1.2 },     // ~18px
  statLabel:   { fontSize: '0.5625rem', fontWeight: 500, letterSpacing: '0.02em', textTransform: 'uppercase' }, // ~9px
  chip:        { fontSize: '0.5625rem', fontWeight: 500 },                    // ~9px
  tab:         { fontSize: '0.625rem', fontWeight: 600 },                      // ~10px
};

// ── Border & Shadow Tokens ──────────────────────────────────────────────────
export const BORDER = {
  light: '1px solid',
  card: '1px solid',
  radius: 1.5,  // 12px border radius for cards
};

// ── Shared Page Wrapper — full-width, consistent padding ────────────────────
export function PageWrapper({ children, sx = {} }) {
  return (
    <Box
      sx={{
        px: SPACING.md,    // 16px horizontal
        py: SPACING.sm,    // 12px vertical
        height: '100%',
        overflow: 'auto',
        ...sx,
      }}
    >
      {children}
    </Box>
  );
}

// ── Page Header — compact title + optional subtitle ─────────────────────────
export function PageHeader({ title, subtitle, action }) {
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'space-between',
        mb: SPACING.lg,
        gap: SPACING.md,
      }}
    >
      <Box>
        <Typography sx={{ ...FONT.pageTitle, color: 'text.primary', mb: 0.25 }}>
          {title}
        </Typography>
        {subtitle && (
          <Typography sx={{ ...FONT.body, color: 'text.secondary' }}>
            {subtitle}
          </Typography>
        )}
      </Box>
      {action && <Box sx={{ flexShrink: 0 }}>{action}</Box>}
    </Box>
  );
}

// ── Section Header — uppercase label for content sections ───────────────────
export function SectionHeader({ label, action }) {
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        mb: SPACING.md,
      }}
    >
      <Typography sx={{ ...FONT.sectionTitle, color: 'text.secondary' }}>
        {label}
      </Typography>
      {action}
    </Box>
  );
}

// ── Collapsible Section — System-wide standard for bulky content ────────────
export function CollapsibleSection({ label, defaultExpanded = true, children, action }) {
  return (
    <Accordion
      defaultExpanded={defaultExpanded}
      elevation={0}
      sx={{ 
        mb: SPACING.sm, 
        borderRadius: 2,
        border: '1px solid',
        borderColor: 'divider',
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
        '&:before': { display: 'none' },
        transition: 'box-shadow 0.25s ease',
        '&.Mui-expanded': {
          boxShadow: '0 2px 8px rgba(0,0,0,0.08)'
        }
      }}
    >
      <AccordionSummary 
        expandIcon={<ExpandMoreIcon sx={{ color: 'primary.main', fontSize: 18 }} />}
        sx={{
          minHeight: 40,
          '& .MuiAccordionSummary-content': {
            my: 0.75
          },
          '&:hover': {
            bgcolor: 'action.hover'
          },
          transition: 'background-color 0.2s ease'
        }}
      >
        <Box sx={{ display: 'flex', width: '100%', alignItems: 'center', justifyContent: 'space-between' }}>
          <Typography sx={{ fontSize: '0.6875rem', fontWeight: 700, color: 'text.primary', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            {label}
          </Typography>
          {action && <Box onClick={(e) => e.stopPropagation()}>{action}</Box>}
        </Box>
      </AccordionSummary>
      <AccordionDetails sx={{ p: SPACING.sm, pt: 0.5 }}>
        {children}
      </AccordionDetails>
    </Accordion>
  );
}

// ── Stat Card — compact metric display ──────────────────────────────────────
export function StatCard({ label, value, color, icon: Icon }) {
  return (
    <Paper
      variant="outlined"
      sx={{
        p: SPACING.md,
        display: 'flex',
        alignItems: 'center',
        gap: SPACING.sm,
        borderLeft: `3px solid ${color}`,
        borderRadius: BORDER.radius,
        height: '100%',
      }}
    >
      {Icon && (
        <Box
          sx={{
            bgcolor: `${color}14`,
            borderRadius: 1,
            p: 0.75,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}
        >
          <Icon sx={{ fontSize: 18, color }} />
        </Box>
      )}
      <Box sx={{ minWidth: 0 }}>
        <Typography sx={{ ...FONT.statValue, color: 'text.primary' }}>
          {value}
        </Typography>
        <Typography sx={{ ...FONT.statLabel, color: 'text.secondary' }}>
          {label}
        </Typography>
      </Box>
    </Paper>
  );
}

// ── Empty State — centered placeholder ──────────────────────────────────────
export function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <Paper
      variant="outlined"
      sx={{
        p: SPACING.xl,
        textAlign: 'center',
        borderRadius: BORDER.radius,
      }}
    >
      {Icon && (
        <Icon sx={{ fontSize: 40, color: 'text.disabled', mb: SPACING.md }} />
      )}
      <Typography sx={{ ...FONT.cardTitle, color: 'text.secondary', mb: 0.5 }}>
        {title}
      </Typography>
      {description && (
        <Typography sx={{ ...FONT.bodySmall, color: 'text.disabled', mb: SPACING.md }}>
          {description}
        </Typography>
      )}
      {action}
    </Paper>
  );
}

// ── Scope Constants (shared across all carbon pages) ────────────────────────
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

// ── Quality Constants (shared across all carbon pages) ──────────────────────
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
