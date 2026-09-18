// File: src/pages/PlatformHome.jsx
// Platform Home — full-bleed domain entry surface for the traditional workspace.
// Dual-workspace model: domains here; Pulse beside/expanded for AI.
// RULE: Never add emissions-specific dashboards here; they live inside domain apps.

import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Stack,
  useTheme,
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import Co2Icon from '@mui/icons-material/Co2';
import DashboardIcon from '@mui/icons-material/Dashboard';
import LayersIcon from '@mui/icons-material/Layers';
import GroupsIcon from '@mui/icons-material/Groups';
import PersonIcon from '@mui/icons-material/Person';
import SupervisorAccountIcon from '@mui/icons-material/SupervisorAccount';
import MonitorHeartIcon from '@mui/icons-material/MonitorHeart';
import SchoolIcon from '@mui/icons-material/School';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import { APP_REGISTRY } from '../apps/registry';
import { useAuth } from '../auth/AuthContext';
import { hasAppAccess } from '../authz';
import { useEnabledApps } from '../hooks/useEnabledApps';
import useDocumentTitle from '../hooks/useDocumentTitle';
import PageContainer from '../components/layout/PageContainer';
import { FONT } from '../theme/themeTokens';
import { PLATFORM_TITLE, PLATFORM_TAGLINE } from '../config/branding';

const APP_ICONS = {
  Co2: Co2Icon,
  Dashboard: DashboardIcon,
  Layers: LayersIcon,
  Groups: GroupsIcon,
  Person: PersonIcon,
  SupervisorAccount: SupervisorAccountIcon,
  MonitorHeart: MonitorHeartIcon,
  Diversity3: GroupsIcon,
  School: SchoolIcon,
};

function DomainStrip({ app }) {
  const navigate = useNavigate();
  const theme = useTheme();
  const { t } = useTranslation('shell');
  const isRtl = theme.direction === 'rtl';
  const Icon = APP_ICONS[app.icon] || DashboardIcon;
  const name = t(`ui.apps.${app.id}.name`, { defaultValue: app.name });
  const description = t(`ui.apps.${app.id}.description`, { defaultValue: app.description });
  const accent = app.color || theme.palette.primary.main;

  const handleOpen = () => {
    navigate(app.routePrefix || `/${app.id}`);
  };

  const handleKeyDown = (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      handleOpen();
    }
  };

  return (
    <Box
      role="button"
      tabIndex={0}
      onClick={handleOpen}
      onKeyDown={handleKeyDown}
      aria-label={t('ui.openDomain', { name })}
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 2,
        width: '100%',
        minHeight: 72,
        px: { xs: 1.5, sm: 2 },
        py: 1.75,
        cursor: 'pointer',
        borderBottom: 1,
        borderColor: 'divider',
        bgcolor: 'transparent',
        transition: 'background-color 140ms ease',
        '&:hover': { bgcolor: 'action.hover' },
        '&:focus-visible': {
          outline: '2px solid',
          outlineColor: 'primary.main',
          outlineOffset: -2,
        },
      }}
    >
      <Box
        aria-hidden
        sx={{
          width: 4,
          alignSelf: 'stretch',
          borderRadius: 1,
          bgcolor: accent,
          flexShrink: 0,
        }}
      />
      <Box
        sx={{
          width: 40,
          height: 40,
          borderRadius: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          bgcolor: 'action.selected',
          color: accent,
          flexShrink: 0,
        }}
      >
        <Icon sx={{ fontSize: 22 }} />
      </Box>
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography
          component="span"
          sx={{
            ...FONT.heading,
            display: 'block',
            fontWeight: 650,
            color: 'text.primary',
            mb: 0.25,
          }}
        >
          {name}
        </Typography>
        <Typography
          sx={{
            ...FONT.body2,
            color: 'text.secondary',
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
          }}
        >
          {description}
        </Typography>
      </Box>
      <ArrowForwardIcon
        sx={{
          fontSize: 18,
          color: 'text.secondary',
          flexShrink: 0,
          opacity: 0.55,
          transform: isRtl ? 'scaleX(-1)' : undefined,
        }}
      />
    </Box>
  );
}

function NoAppsPlaceholder() {
  const { t } = useTranslation('shell');
  return (
    <Box sx={{ textAlign: 'center', py: 8 }}>
      <Typography variant="h5" color="text.secondary" gutterBottom>
        {t('ui.noAppsAvailable')}
      </Typography>
      <Typography variant="body2" color="text.secondary">
        {t('ui.noAppsSubtext')}
      </Typography>
    </Box>
  );
}

export default function PlatformHome() {
  const { t } = useTranslation('shell');
  useDocumentTitle(t('ui.platformTitle'));
  const { availablePerspectives, user, context, loading, userCapabilities, isGlobalAdminFlag } = useAuth();
  const { isAppEnabled } = useEnabledApps();

  const accessibleApps = APP_REGISTRY.filter((app) => {
    if (loading) return false;
    if (!isAppEnabled(app.id)) return false;
    return hasAppAccess(app.id, user, {
      perspectives: availablePerspectives,
      capabilities: userCapabilities,
      modules: context?.modules,
      isGlobalAdminFlag,
    });
  });

  return (
    <PageContainer
      sx={{
        maxWidth: 'none',
        width: '100%',
        mx: 0,
        px: { xs: 1.5, sm: 2.5, md: 3 },
        py: { xs: 2, md: 3 },
      }}
    >
      <Box sx={{ mb: { xs: 2.5, md: 3.5 }, maxWidth: 720 }}>
        <Typography
          component="h1"
          sx={{
            fontWeight: 700,
            fontSize: { xs: '1.5rem', md: '1.75rem' },
            letterSpacing: '-0.02em',
            color: 'text.primary',
            mb: 0.75,
          }}
        >
          {PLATFORM_TITLE}
        </Typography>
        <Typography sx={{ ...FONT.body, color: 'text.secondary', mb: 1.5 }}>
          {PLATFORM_TAGLINE}
        </Typography>
        <Typography
          sx={{
            ...FONT.bodySmall,
            color: 'text.secondary',
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            fontWeight: 600,
            mb: 0.5,
          }}
        >
          {t('ui.domainsHeading')}
        </Typography>
        <Typography sx={{ ...FONT.body2, color: 'text.secondary' }}>
          {t('ui.domainsSubheading')}
        </Typography>
      </Box>

      {accessibleApps.length > 0 ? (
        <Stack
          component="nav"
          aria-label={t('ui.domainsHeading')}
          spacing={0}
          sx={{
            width: '100%',
            borderTop: 1,
            borderColor: 'divider',
            bgcolor: 'background.paper',
          }}
        >
          {accessibleApps.map((app) => (
            <DomainStrip key={app.id} app={app} />
          ))}
        </Stack>
      ) : (
        <NoAppsPlaceholder />
      )}
    </PageContainer>
  );
}
