// Shared mobile breakpoint hooks (ADR-0035 / compact-ui §Mobile).
// Phone portrait = theme.breakpoints.down('sm') (<600).
// Landscape phones are often ≥600 wide but short — keep the mobile shell so
// Pulse/nav do not flip to desktop mid-rotation.
//
// Tablets (sm+, not short-landscape) keep Pulse docked beside domain.

import { useTheme, useMediaQuery } from '@mui/material';

function useShortLandscape() {
  return useMediaQuery(
    '(max-height: 500px) and (max-width: 960px) and (orientation: landscape)',
  );
}

export function useIsMobile() {
  const theme = useTheme();
  const narrow = useMediaQuery(theme.breakpoints.down('sm'));
  return narrow || useShortLandscape();
}

/** True phone portrait (< sm). Tablets at sm+ are false. */
export function useIsPhone() {
  const theme = useTheme();
  return useMediaQuery(theme.breakpoints.down('sm'));
}

/**
 * Pulse uses fullscreen Dialog on phones (portrait or short landscape).
 * Tablets keep the desktop alongside dock (ADR-0035 tablet dock).
 */
export function usePulseFullscreen() {
  return useIsPhone() || useShortLandscape();
}

export default useIsMobile;
